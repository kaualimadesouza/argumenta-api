"""Evaluation result types and the verdict rule.

The verdict is OUR deterministic rule over the scores, never the LLM's opinion:
same scores and ruler always produce the same verdict (PRD reliability rule).
"""

from dataclasses import dataclass

from argumenta.domain.enums import AnnotationType, Dimension, Severity, Verdict

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
    minimum, fails persuasion; otherwise approved."""
    if not scores:
        raise ValueError("cannot decide a verdict without scores")
    checked = tuple(
        ScoredDimension(
            dimension=s.dimension,
            score=s.score,
            evidence=s.evidence,
            passed_floor=s.score >= ruler.dimension_floor,
        )
        for s in scores
    )
    average = sum(s.score for s in checked) / len(checked)
    failed = [s.dimension for s in checked if not s.passed_floor]

    if any(dimension in LANGUAGE_DIMENSIONS for dimension in failed):
        verdict = Verdict.FAILED_TECHNICAL
    elif failed or average < ruler.min_average:
        verdict = Verdict.FAILED_PERSUASION
    else:
        verdict = Verdict.APPROVED
    return VerdictDecision(verdict=verdict, average_score=average, scores=checked)
