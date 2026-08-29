from typing import Any, ClassVar

import pytest

from argumenta.adapters.llm.evaluation_engine import parse_engine_output
from argumenta.adapters.llm.prompts.evaluation_v1 import PROMPT_VERSION
from argumenta.application.evaluation.ports import (
    EngineRequest,
    EngineResult,
    SpellChecker,
)
from argumenta.application.evaluation.use_cases import (
    EvaluateArgument,
    EvaluateArgumentUseCase,
)
from argumenta.domain.enums import AnnotationType, Dimension, Severity, Verdict
from argumenta.domain.errors import EvaluationFailedError, LlmBudgetExceededError
from argumenta.domain.evaluation import (
    BASE_DIMENSIONS,
    DimensionScore,
    EvaluationRuler,
    SpellingAnchor,
    decide_verdict,
)
from argumenta.domain.lenses import GradingSpec

RULER = EvaluationRuler(dimension_floor=40, min_average=50)


def _scores(**by_dimension: int) -> tuple[DimensionScore, ...]:
    defaults = {
        Dimension.NORMA_CULTA: 70,
        Dimension.COESAO: 70,
        Dimension.COERENCIA: 70,
        Dimension.REPERTORIO: 70,
        Dimension.PERSUASAO: 70,
    }
    for name, score in by_dimension.items():
        defaults[Dimension(name)] = score
    return tuple(
        DimensionScore(dimension=dim, score=score, evidence="trecho citado")
        for dim, score in defaults.items()
    )


class TestVerdictRule:
    def test_good_argument_with_bad_portuguese_fails_technical(self) -> None:
        decision = decide_verdict(_scores(norma_culta=20, persuasao=90), RULER)
        assert decision.verdict == Verdict.FAILED_TECHNICAL

    def test_ok_portuguese_with_weak_argument_fails_persuasion(self) -> None:
        decision = decide_verdict(_scores(persuasao=25), RULER)
        assert decision.verdict == Verdict.FAILED_PERSUASION

    def test_low_average_fails_persuasion_even_above_floors(self) -> None:
        decision = decide_verdict(
            _scores(norma_culta=45, coesao=45, coerencia=45, repertorio=45, persuasao=45),
            RULER,
        )
        assert decision.average_score == 45
        assert decision.verdict == Verdict.FAILED_PERSUASION

    def test_everything_above_ruler_approves(self) -> None:
        decision = decide_verdict(_scores(), RULER)
        assert decision.verdict == Verdict.APPROVED
        assert all(score.passed_floor for score in decision.scores)

    def test_technical_failure_wins_over_persuasion_failure(self) -> None:
        decision = decide_verdict(_scores(norma_culta=10, persuasao=10), RULER)
        assert decision.verdict == Verdict.FAILED_TECHNICAL

    def test_same_scores_always_same_verdict(self) -> None:
        scores = _scores(coerencia=55)
        results = {decide_verdict(scores, RULER).verdict for _ in range(10)}
        assert results == {Verdict.APPROVED}


class TestEngineOutputContract:
    PAYLOAD: ClassVar[dict[str, Any]] = {
        "scores": [
            {"dimension": d.value, "score": 80, "evidence": "trecho"} for d in BASE_DIMENSIONS
        ],
        "annotations": [
            {
                "span_start": 0,
                "span_end": 4,
                "type": "spelling",
                "severity": "error",
                "message": "erro de grafia",
                "suggestion": "algo",
                "priority": 1,
            }
        ],
    }

    def test_valid_payload_parses(self) -> None:
        output = parse_engine_output(self.PAYLOAD, "algo escrito pelo aluno")
        assert len(output.scores) == 5
        assert output.annotations[0].type == AnnotationType.SPELLING
        assert output.annotations[0].severity == Severity.ERROR

    def test_score_out_of_range_is_rejected(self) -> None:
        bad = [{**s, "score": 150} for s in self.PAYLOAD["scores"]]
        with pytest.raises(EvaluationFailedError):
            parse_engine_output({**self.PAYLOAD, "scores": bad}, "texto")

    def test_an_out_of_bounds_span_is_dropped_not_fatal(self) -> None:
        """Caught live: one hallucinated span (LLM offsets are unreliable) was
        throwing away the whole paid correction. A highlight that points outside
        the text is useless; the scores and the other annotations are not."""
        output = parse_engine_output(self.PAYLOAD, "abc")
        assert output.annotations == []
        assert len(output.scores) == 5

    def test_valid_annotations_survive_the_dropped_one(self) -> None:
        bad = {**self.PAYLOAD["annotations"][0], "span_start": 10, "span_end": 99}
        payload = {**self.PAYLOAD, "annotations": [self.PAYLOAD["annotations"][0], bad]}
        output = parse_engine_output(payload, "algo escrito pelo aluno")
        assert [a.span_end for a in output.annotations] == [4]

    def test_empty_evidence_is_rejected(self) -> None:
        bad = [{**s, "evidence": ""} for s in self.PAYLOAD["scores"]]
        with pytest.raises(EvaluationFailedError):
            parse_engine_output({**self.PAYLOAD, "scores": bad}, "texto")


class FakeEngine:
    def __init__(self, scores: tuple[DimensionScore, ...]) -> None:
        self._scores = scores
        self.last_request: EngineRequest | None = None

    def evaluate(self, request: EngineRequest) -> EngineResult:
        self.last_request = request
        return EngineResult(
            scores=self._scores,
            annotations=(),
            model="claude-sonnet-5",
            prompt_version=PROMPT_VERSION,
            latency_ms=10,
            input_tokens=100,
            output_tokens=50,
        )


class FakeSpellChecker(SpellChecker):
    def find_unknown_words(self, text: str) -> tuple[SpellingAnchor, ...]:
        return (SpellingAnchor(word="presisa", span_start=9, span_end=16),)


class FakeBudget:
    def __init__(self, exhausted: bool = False) -> None:
        self._exhausted = exhausted

    def ensure_within_budget(self) -> None:
        if self._exhausted:
            raise LlmBudgetExceededError


def _request(
    required: tuple[Dimension, ...] = BASE_DIMENSIONS, full_essay: bool = False
) -> EvaluateArgument:
    return EvaluateArgument(
        text="A escola presisa do festival.",
        chapter_objective="Convencer a diretora.",
        evaluator_brief="Plano concreto conta.",
        persona_brief="Pragmatica.",
        min_words=120,
        max_words=250,
        ruler=RULER,
        spec=GradingSpec(dimensions=required, full_essay=full_essay),
    )


class TestEvaluateArgumentUseCase:
    def test_pipeline_passes_anchors_and_applies_our_verdict(self) -> None:
        engine = FakeEngine(_scores(persuasao=20))
        use_case = EvaluateArgumentUseCase(engine, FakeSpellChecker(), FakeBudget())

        outcome = use_case.execute(_request())

        assert engine.last_request is not None
        assert engine.last_request.spelling_anchors[0].word == "presisa"
        assert outcome.verdict == Verdict.FAILED_PERSUASION
        assert outcome.model == "claude-sonnet-5"
        assert outcome.prompt_version == PROMPT_VERSION

    def test_same_text_evaluated_twice_same_verdict(self) -> None:
        engine = FakeEngine(_scores())
        use_case = EvaluateArgumentUseCase(engine, FakeSpellChecker(), FakeBudget())

        first = use_case.execute(_request())
        second = use_case.execute(_request())

        assert first.verdict == second.verdict == Verdict.APPROVED
        assert first.average_score == second.average_score

    def test_exhausted_budget_blocks_before_the_llm(self) -> None:
        engine = FakeEngine(_scores())
        use_case = EvaluateArgumentUseCase(engine, FakeSpellChecker(), FakeBudget(exhausted=True))

        with pytest.raises(LlmBudgetExceededError):
            use_case.execute(_request())
        assert engine.last_request is None

    def test_boss_request_carries_the_essay_rule_and_the_extra_dimension(self) -> None:
        required = (*BASE_DIMENSIONS, Dimension.PROPOSTA_INTERVENCAO)
        engine = FakeEngine(
            (
                *_scores(),
                DimensionScore(
                    dimension=Dimension.PROPOSTA_INTERVENCAO, score=70, evidence="proposta"
                ),
            )
        )
        use_case = EvaluateArgumentUseCase(engine, FakeSpellChecker(), FakeBudget())

        outcome = use_case.execute(_request(required=required, full_essay=True))

        assert engine.last_request is not None
        assert engine.last_request.full_essay is True
        assert engine.last_request.required_dimensions == required
        assert len(outcome.scores) == 6

    def test_engine_that_ignores_a_required_dimension_is_rejected(self) -> None:
        """Any engine, not just the Claude adapter: an incomplete correction
        would silently distort the exam lens."""
        engine = FakeEngine(_scores())
        use_case = EvaluateArgumentUseCase(engine, FakeSpellChecker(), FakeBudget())

        with pytest.raises(EvaluationFailedError):
            use_case.execute(_request(required=(*BASE_DIMENSIONS, Dimension.PROPOSTA_INTERVENCAO)))
