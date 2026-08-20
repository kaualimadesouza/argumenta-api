from dataclasses import dataclass

from argumenta.application.evaluation.ports import (
    EngineRequest,
    EvaluationEngine,
    LlmBudget,
    SpellChecker,
)
from argumenta.domain.evaluation import EvaluationOutcome, EvaluationRuler, decide_verdict


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
            )
        )
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
