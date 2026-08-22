from dataclasses import dataclass
from typing import Protocol

from argumenta.domain.enums import Dimension
from argumenta.domain.evaluation import Annotation, DimensionScore, SpellingAnchor


@dataclass(frozen=True)
class EngineRequest:
    text: str
    chapter_objective: str
    evaluator_brief: str
    persona_brief: str
    min_words: int
    max_words: int
    spelling_anchors: tuple[SpellingAnchor, ...]
    """Deterministic pt-BR unknown words; the LLM classifies and explains them."""
    required_dimensions: tuple[Dimension, ...]
    """Exactly the dimensions the engine must score, per chapter kind and lens."""
    full_essay: bool
    """Boss chapters ask for a complete dissertative-argumentative essay."""


@dataclass(frozen=True)
class EngineResult:
    scores: tuple[DimensionScore, ...]
    annotations: tuple[Annotation, ...]
    model: str
    prompt_version: str
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None


class EvaluationEngine(Protocol):
    def evaluate(self, request: EngineRequest) -> EngineResult: ...


class SpellChecker(Protocol):
    def find_unknown_words(self, text: str) -> tuple[SpellingAnchor, ...]: ...


class LlmBudget(Protocol):
    def ensure_within_budget(self) -> None:
        """Raises LlmBudgetExceededError when the monthly token cap is hit;
        logs an alert when approaching it."""
        ...
