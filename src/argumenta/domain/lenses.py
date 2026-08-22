"""Exam lenses: how the internal dimensions are shown to a student aiming at a
given exam, and what the engine is asked to grade in each kind of chapter.

The correction is the same for everyone: the same BASE_DIMENSIONS, the same
ruler, and a verdict built only from them (see decide_verdict). A lens changes
what the student SEES. The one thing it changes upstream is whether the boss
essay is also graded on the ENEM intervention proposal, and that dimension is
deliberately outside the verdict, so two students with the same text get the
same outcome whichever vestibular they picked.

This mapping is versioned like the prompt (LENS_VERSION): changing a criterion,
a scale or a dimension assignment MUST bump it, and the version is stored with
each evaluation so an old correction can be replayed into the lens that showed
it.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from argumenta.domain.enums import ChapterKind, Dimension, Exam
from argumenta.domain.evaluation import BASE_DIMENSIONS, ScoredDimension

LENS_VERSION = "lens-v1.0"

INTERNAL_SCALE_MAX = 100
"""Every dimension is scored 0-100 internally, whatever the lens shows."""

ScaleSource = Literal["board", "argumenta"]
"""Who owns the total: the exam board, or us. The client must not render our
own aggregation as an official grade."""


@dataclass(frozen=True)
class CriterionMapping:
    code: str
    label: str
    dimensions: tuple[Dimension, ...]
    """Internal dimensions averaged into this criterion."""
    scale_max: int
    boss_only: bool = False


@dataclass(frozen=True)
class ExamLens:
    exam: Exam
    criteria: tuple[CriterionMapping, ...]
    """Official criteria of the board, in display order."""
    extra_criteria: tuple[CriterionMapping, ...] = field(default_factory=tuple)
    """Argumenta criteria shown beside the official ones, never in the total."""
    normalize_to: int | None = None
    """None sums the criteria (ENEM); a value averages them onto that scale."""
    board_total_kinds: frozenset[ChapterKind] = frozenset()
    """Chapter kinds where the total is the board's own scale, not ours."""
    grades_intervention_proposal: bool = False
    """Whether a boss essay under this lens is also graded on the proposal."""

    def official_for(self, kind: ChapterKind) -> tuple[CriterionMapping, ...]:
        return tuple(
            criterion
            for criterion in self.criteria
            if not criterion.boss_only or kind == ChapterKind.CHEFE
        )

    def criteria_for(self, kind: ChapterKind) -> tuple[CriterionMapping, ...]:
        return self.official_for(kind) + self.extra_criteria


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
    total: int | None
    """None when the lens cannot state a total for what was graded."""
    total_max: int | None
    scale_source: ScaleSource


@dataclass(frozen=True)
class GradingSpec:
    """What the engine must produce for one chapter under one lens: the two
    values are one decision, so they cannot contradict each other."""

    dimensions: tuple[Dimension, ...]
    full_essay: bool


_PERSUASION_CRITERION = CriterionMapping(
    code="ARG",
    label="Persuasão (critério Argumenta)",
    dimensions=(Dimension.PERSUASAO,),
    scale_max=INTERNAL_SCALE_MAX,
)

ENEM_LENS = ExamLens(
    exam=Exam.ENEM,
    criteria=(
        CriterionMapping(
            code="C1",
            label="Domínio da norma culta",
            dimensions=(Dimension.NORMA_CULTA,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C2",
            label="Compreensão da proposta e repertório",
            dimensions=(Dimension.REPERTORIO,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C3",
            label="Seleção e organização dos argumentos",
            dimensions=(Dimension.COERENCIA,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C4",
            label="Mecanismos linguísticos de coesão",
            dimensions=(Dimension.COESAO,),
            scale_max=200,
        ),
        CriterionMapping(
            code="C5",
            label="Proposta de intervenção",
            dimensions=(Dimension.PROPOSTA_INTERVENCAO,),
            scale_max=200,
            boss_only=True,
        ),
    ),
    extra_criteria=(_PERSUASION_CRITERION,),
    board_total_kinds=frozenset({ChapterKind.CHEFE}),
    grades_intervention_proposal=True,
)
"""Only the boss essay has a real ENEM total (0-1000, the five competences).
There is no official 0-800 partial grade, so the confronto total is ours."""

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
            label="Expressão",
            dimensions=(Dimension.NORMA_CULTA,),
            scale_max=INTERNAL_SCALE_MAX,
        ),
    ),
    extra_criteria=(_PERSUASION_CRITERION,),
    normalize_to=INTERNAL_SCALE_MAX,
)
"""FUVEST publishes the three axes but not a per-axis scale stable enough to
pin here, so the axes keep the internal 0-100 and the total is ours, labelled
as such, until the calibration suite (issue #12) settles the conversion."""

OFFICIAL_LENSES: dict[Exam, ExamLens] = {
    Exam.ENEM: ENEM_LENS,
    Exam.FUVEST: FUVEST_LENS,
}

DEFAULT_EXAM = Exam.ENEM
"""Lens used while the student has no active exam target. Safe as a default
precisely because the lens does not touch the verdict."""


def criterion_for(exam: Exam, dimension: Dimension) -> CriterionMapping | None:
    """Which criterion of the lens labels this internal dimension. Feeds
    per-dimension views (the progress series), never a total."""
    lens = OFFICIAL_LENSES[exam]
    for criterion in (*lens.criteria, *lens.extra_criteria):
        if dimension in criterion.dimensions:
            return criterion
    return None


def grading_spec(kind: ChapterKind, exam: Exam) -> GradingSpec:
    """The base dimensions always, plus the ENEM intervention proposal in a
    boss essay. Derived from the chapter, never from display configuration:
    removing a criterion from a lens must not silently stop the engine from
    scoring a dimension the verdict depends on."""
    proposal = kind == ChapterKind.CHEFE and OFFICIAL_LENSES[exam].grades_intervention_proposal
    dimensions = (*BASE_DIMENSIONS, Dimension.PROPOSTA_INTERVENCAO) if proposal else BASE_DIMENSIONS
    return GradingSpec(dimensions=dimensions, full_essay=kind == ChapterKind.CHEFE)


def required_dimensions(kind: ChapterKind, exam: Exam) -> tuple[Dimension, ...]:
    return grading_spec(kind, exam).dimensions


def project_lens(scores: tuple[ScoredDimension, ...], exam: Exam, kind: ChapterKind) -> LensView:
    """Aggregates the internal scores into the criteria the student expects to
    see. A criterion whose dimensions were not graded is not shown, and then
    the lens states no total instead of quietly shrinking the scale."""
    lens = OFFICIAL_LENSES[exam]
    by_dimension = {score.dimension: score.score for score in scores}
    official = _views(lens.official_for(kind), by_dimension, is_extra=False)
    extras = _views(lens.extra_criteria, by_dimension, is_extra=True)

    complete = len(official) == len(lens.official_for(kind))
    official_max = sum(criterion.scale_max for criterion in official)
    shown_total = sum(criterion.score for criterion in official)
    return LensView(
        exam=exam,
        version=LENS_VERSION,
        criteria=(*official, *extras),
        total=_total(shown_total, official_max, lens) if complete else None,
        total_max=(lens.normalize_to or official_max) if complete else None,
        scale_source="board" if kind in lens.board_total_kinds else "argumenta",
    )


def _views(
    mappings: tuple[CriterionMapping, ...],
    by_dimension: dict[Dimension, int],
    is_extra: bool,
) -> tuple[LensCriterion, ...]:
    views = (_view(mapping, by_dimension, is_extra) for mapping in mappings)
    return tuple(view for view in views if view is not None)


def _view(
    mapping: CriterionMapping, by_dimension: dict[Dimension, int], is_extra: bool
) -> LensCriterion | None:
    graded = [by_dimension[d] for d in mapping.dimensions if d in by_dimension]
    if not graded:
        return None
    return LensCriterion(
        code=mapping.code,
        label=mapping.label,
        score=_rescale(sum(graded) / len(graded), mapping.scale_max),
        scale_max=mapping.scale_max,
        is_argumenta_extra=is_extra,
    )


def _total(shown_total: int, official_max: int, lens: ExamLens) -> int:
    """Aggregates over the numbers on screen, so the student can add them up."""
    if lens.normalize_to is None or not official_max:
        return shown_total
    return _rescale(shown_total * INTERNAL_SCALE_MAX / official_max, lens.normalize_to)


def _rescale(value: float, scale_max: int) -> int:
    """Half up, never bankers rounding: a grade that flips between 80 and 82 on
    consecutive half points reads as a bug to the student, and is one."""
    scaled = Decimal(value) * scale_max / INTERNAL_SCALE_MAX
    return int(scaled.quantize(Decimal(1), rounding=ROUND_HALF_UP))
