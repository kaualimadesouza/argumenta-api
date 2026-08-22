from dataclasses import dataclass

from argumenta.application.evaluation.ports import (
    EngineRequest,
    EvaluationEngine,
    LlmBudget,
    SpellChecker,
)
from argumenta.domain.enums import Dimension
from argumenta.domain.errors import EvaluationFailedError
from argumenta.domain.evaluation import (
    DimensionScore,
    EvaluationOutcome,
    EvaluationRuler,
    decide_verdict,
)


@dataclass(frozen=True)
class EvaluateArgument:
    text: str
    chapter_objective: str
    evaluator_brief: str
    persona_brief: str
    min_words: int
    max_words: int
    ruler: EvaluationRuler
    """Floor and minimum average frozen from the story at submission time."""
    required_dimensions: tuple[Dimension, ...]
    full_essay: bool


class EvaluateArgumentUseCase:
    """The correction pipeline: budget gate, deterministic pt-BR anchors, LLM
    scoring, and OUR verdict rule applied over the scores."""

    def __init__(
        self,
        engine: EvaluationEngine,
        spell_checker: SpellChecker,
        budget: LlmBudget,
    ) -> None:
        self._engine = engine
        self._spell_checker = spell_checker
        self._budget = budget

    def execute(self, request: EvaluateArgument) -> EvaluationOutcome:
        self._budget.ensure_within_budget()
        anchors = self._spell_checker.find_unknown_words(request.text)
        result = self._engine.evaluate(
            EngineRequest(
                text=request.text,
                chapter_objective=request.chapter_objective,
                evaluator_brief=request.evaluator_brief,
                persona_brief=request.persona_brief,
                min_words=request.min_words,
                max_words=request.max_words,
                spelling_anchors=anchors,
                required_dimensions=request.required_dimensions,
                full_essay=request.full_essay,
            )
        )
        self._ensure_complete(result.scores, request.required_dimensions)
        decision = decide_verdict(result.scores, request.ruler)
        return EvaluationOutcome(
            verdict=decision.verdict,
            average_score=decision.average_score,
            scores=decision.scores,
            annotations=result.annotations,
            model=result.model,
            prompt_version=result.prompt_version,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    @staticmethod
    def _ensure_complete(
        scores: tuple[DimensionScore, ...], required: tuple[Dimension, ...]
    ) -> None:
        """Holds for every engine, not just the Claude adapter: a correction
        missing a required dimension would silently distort the lens."""
        graded = {score.dimension for score in scores}
        if graded != set(required):
            raise EvaluationFailedError(
                f"engine graded {sorted(graded)}, expected {sorted(set(required))}"
            )
