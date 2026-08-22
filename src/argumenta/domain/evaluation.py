"""Evaluation result types and the verdict rule.

The verdict is OUR deterministic rule over the scores, never the LLM's opinion:
same scores and ruler always produce the same verdict (PRD reliability rule).
"""

from dataclasses import dataclass

from argumenta.domain.enums import AnnotationType, Dimension, Severity, Verdict
from argumenta.domain.errors import EvaluationFailedError

BASE_DIMENSIONS = (
    Dimension.NORMA_CULTA,
    Dimension.COESAO,
    Dimension.COERENCIA,
    Dimension.REPERTORIO,
    Dimension.PERSUASAO,
)
"""The five dimensions of the game, scored on every submission and the only
ones the verdict is built from. The ruler (floor and minimum average) is
calibrated against exactly these, so an exam-specific dimension must never
join the average: whether the character was convinced cannot depend on which
vestibular the student picked in their profile."""

LANGUAGE_DIMENSIONS = (Dimension.NORMA_CULTA, Dimension.COESAO)
"""Below the floor here the failure is technical: pause and revise."""


@dataclass(frozen=True)
class DimensionScore:
    """Raw engine score; the ruler has not been applied yet."""

    dimension: Dimension
    score: int
    evidence: str
    """Quote from the student's text backing the score; no evidence, no discount."""


@dataclass(frozen=True)
class ScoredDimension:
    """Engine score checked against the frozen ruler (evaluation_scores row)."""

    dimension: Dimension
    score: int
    evidence: str
    passed_floor: bool


@dataclass(frozen=True)
class Annotation:
    span_start: int
    span_end: int
    type: AnnotationType
    severity: Severity
    message: str
    suggestion: str | None
    priority: int
    """1-3 enters the 'para passar' list."""


@dataclass(frozen=True)
class SpellingAnchor:
    """A word the deterministic pt-BR checker does not know, with its span."""

    word: str
    span_start: int
    span_end: int


@dataclass(frozen=True)
class EvaluationRuler:
    dimension_floor: int
    min_average: int


@dataclass(frozen=True)
class VerdictDecision:
    verdict: Verdict
    average_score: float
    scores: tuple[ScoredDimension, ...]


@dataclass(frozen=True)
class EvaluationOutcome:
    verdict: Verdict
    average_score: float
    scores: tuple[ScoredDimension, ...]
    annotations: tuple[Annotation, ...]
    model: str
    prompt_version: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def decide_verdict(scores: tuple[DimensionScore, ...], ruler: EvaluationRuler) -> VerdictDecision:
    """Applies the frozen ruler: language dimension under the floor fails
    technical; content/persuasion under the floor, or average under the
    minimum, fails persuasion; otherwise approved.

    Dimensions outside BASE_DIMENSIONS (today only the ENEM intervention
    proposal in a boss chapter) are scored, stored and shown, but stay out of
    the average and out of the gate."""
    checked = tuple(
        ScoredDimension(
            dimension=s.dimension,
            score=s.score,
            evidence=s.evidence,
            passed_floor=s.score >= ruler.dimension_floor,
        )
        for s in scores
    )
    graded = [s for s in checked if s.dimension in BASE_DIMENSIONS]
    if not graded:
        raise ValueError("cannot decide a verdict without the base dimensions")
    average = sum(s.score for s in graded) / len(graded)
    failed = [s.dimension for s in graded if not s.passed_floor]
    return VerdictDecision(
        verdict=_verdict_for(failed, average, ruler),
        average_score=average,
        scores=checked,
    )


def _verdict_for(failed: list[Dimension], average: float, ruler: EvaluationRuler) -> Verdict:
    if any(dimension in LANGUAGE_DIMENSIONS for dimension in failed):
        return Verdict.FAILED_TECHNICAL
    if failed or average < ruler.min_average:
        return Verdict.FAILED_PERSUASION
    return Verdict.APPROVED


def ensure_graded_exactly(
    scores: tuple[DimensionScore, ...], required: tuple[Dimension, ...]
) -> None:
    """Holds for every engine, not just the Claude adapter: a correction missing
    a required dimension, or answering one twice, would silently distort the
    verdict and the lens. Raises EvaluationFailedError."""
    graded = {score.dimension for score in scores}
    if len(scores) != len(required) or graded != set(required):
        raise EvaluationFailedError(
            f"engine graded {sorted(graded)}, expected {sorted(set(required))}"
        )
