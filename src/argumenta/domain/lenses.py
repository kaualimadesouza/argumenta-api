"""Exam lenses: how the 5 internal dimensions are shown to a student aiming at
a given exam, and which dimensions the engine must grade.

The correction is ALWAYS the same internally (same dimensions, same ruler, same
verdict rule); the lens is presentation only. The single exception is the boss
essay under the ENEM lens, where the exam itself demands an intervention
proposal, so the engine is asked for one extra dimension.

This mapping is versioned like the prompt (LENS_VERSION): changing a criterion,
a scale or a dimension assignment MUST bump it, so a stored evaluation can
always be replayed into the lens that produced it.
"""

import enum
from dataclasses import dataclass, field

from argumenta.domain.enums import ChapterKind, Dimension, Exam
from argumenta.domain.evaluation import ScoredDimension

LENS_VERSION = "lens-v1.0"

INTERNAL_SCALE_MAX = 100
"""Every dimension is scored 0-100 internally, whatever the lens shows."""


class LensAggregation(enum.StrEnum):
    """How the exam board builds the headline number out of its criteria."""

    SUM = "sum"
    MEAN = "mean"


@dataclass(frozen=True)
class CriterionMapping:
    code: str
    label: str
    dimensions: tuple[Dimension, ...]
    """Internal dimensions averaged into this criterion."""
    scale_max: int
    boss_only: bool = False
    is_argumenta_extra: bool = False
    """Shown next to the official criteria, never counted in the exam total."""


@dataclass(frozen=True)
class ExamLens:
    exam: Exam
    criteria: tuple[CriterionMapping, ...]
    """Official criteria of the board, in display order."""
    aggregation: LensAggregation
    extra_criteria: tuple[CriterionMapping, ...] = field(default_factory=tuple)

    def criteria_for(self, kind: ChapterKind) -> tuple[CriterionMapping, ...]:
        official = tuple(
            criterion
            for criterion in self.criteria
            if not criterion.boss_only or kind == ChapterKind.CHEFE
        )
        return official + self.extra_criteria


@dataclass(frozen=True)
class LensCriterion:
    code: str
    label: str
    score: int
    scale_max: int
    is_argumenta_extra: bool


@dataclass(frozen=True)
class LensView:
    exam: Exam
    version: str
    criteria: tuple[LensCriterion, ...]
    total: int
    total_max: int
    """Official total only: the Argumenta criterion is shown, never added in."""


_PERSUASION_CRITERION = CriterionMapping(
    code="ARG",
    label="Persuasao (criterio Argumenta)",
    dimensions=(Dimension.PERSUASAO,),
    scale_max=INTERNAL_SCALE_MAX,
    is_argumenta_extra=True,
)

ENEM_LENS = ExamLens(
    exam=Exam.ENEM,
    criteria=(
        CriterionMapping(
            code="C1",
            label="Dominio da norma culta",
            dimensions=(Dimension.NORMA_CULTA,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C2",
            label="Compreensao da proposta e repertorio",
            dimensions=(Dimension.REPERTORIO,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C3",
            label="Selecao e organizacao dos argumentos",
            dimensions=(Dimension.COERENCIA,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C4",
            label="Mecanismos linguisticos de coesao",
            dimensions=(Dimension.COESAO,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C5",
            label="Proposta de intervencao",
            dimensions=(Dimension.PROPOSTA_INTERVENCAO,),
            scale_max=200,
            boss_only=True,
        ),
    ),
    aggregation=LensAggregation.SUM,
    extra_criteria=(_PERSUASION_CRITERION,),
)

FUVEST_LENS = ExamLens(
    exam=Exam.FUVEST,
    criteria=(
        CriterionMapping(
            code="E1",
            label="Desenvolvimento do tema",
            dimensions=(Dimension.REPERTORIO,),
            scale_max=INTERNAL_SCALE_MAX,
        ),
        CriterionMapping(
            code="E2",
            label="Estrutura do texto",
            dimensions=(Dimension.COESAO, Dimension.COERENCIA),
            scale_max=INTERNAL_SCALE_MAX,
        ),
        CriterionMapping(
            code="E3",
            label="Expressao",
            dimensions=(Dimension.NORMA_CULTA,),
            scale_max=INTERNAL_SCALE_MAX,
        ),
    ),
    aggregation=LensAggregation.MEAN,
    extra_criteria=(_PERSUASION_CRITERION,),
)
"""FUVEST publishes the three axes but not a stable public per-axis scale, so
the axes keep the internal 0-100 scale until the calibration suite (issue #12)
settles the conversion. The mapping itself is what the criterion promises."""

OFFICIAL_LENSES: dict[Exam, ExamLens] = {
    Exam.ENEM: ENEM_LENS,
    Exam.FUVEST: FUVEST_LENS,
}

DEFAULT_EXAM = Exam.ENEM
"""Lens used while the student has no active exam target."""


def required_dimensions(kind: ChapterKind, exam: Exam) -> tuple[Dimension, ...]:
    """What the engine must score for this chapter under this lens."""
    lens = OFFICIAL_LENSES[exam]
    return tuple(
        dimension for criterion in lens.criteria_for(kind) for dimension in criterion.dimensions
    )


def project_lens(scores: tuple[ScoredDimension, ...], exam: Exam, kind: ChapterKind) -> LensView:
    """Aggregates the internal scores into the criteria the student expects to
    see. Criteria whose dimensions were not graded are simply not shown."""
    lens = OFFICIAL_LENSES[exam]
    by_dimension = {score.dimension: score.score for score in scores}
    criteria: list[LensCriterion] = []
    official_scores: list[float] = []
    total_max = 0

    for mapping in lens.criteria_for(kind):
        graded = [by_dimension[d] for d in mapping.dimensions if d in by_dimension]
        if not graded:
            continue
        value = sum(graded) / len(graded) * mapping.scale_max / INTERNAL_SCALE_MAX
        criteria.append(
            LensCriterion(
                code=mapping.code,
                label=mapping.label,
                score=round(value),
                scale_max=mapping.scale_max,
                is_argumenta_extra=mapping.is_argumenta_extra,
            )
        )
        if not mapping.is_argumenta_extra:
            official_scores.append(value)
            total_max += mapping.scale_max

    return LensView(
        exam=exam,
        version=LENS_VERSION,
        criteria=tuple(criteria),
        total=_aggregate(official_scores, lens.aggregation),
        total_max=total_max if lens.aggregation == LensAggregation.SUM else INTERNAL_SCALE_MAX,
    )


def _aggregate(values: list[float], aggregation: LensAggregation) -> int:
    if not values:
        return 0
    if aggregation == LensAggregation.SUM:
        return round(sum(values))
    return round(sum(values) / len(values))
