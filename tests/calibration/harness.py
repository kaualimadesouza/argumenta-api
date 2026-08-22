"""Calibration harness: compares the engine against annotated fixtures.

This lives under tests/ on purpose. It is not product behaviour, it is how we
measure the engine: the comparison rule, the gate and the report are the
deliverable, and they must be testable without an API key or a database.
"""

import enum
import json
import math
import pathlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argumenta.domain.enums import ChapterKind, Dimension, Exam

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

BAND = 15
"""Points a single measurement may differ from the reference. Wide on purpose:
an LLM is not a ruler, and the reference grades are an authorial gabarito, not
the truth."""

MEAN_FLOOR = 3
"""Tightest band any mean gets, however many fixtures back it."""


def mean_tolerance_for(sample_count: int) -> int:
    """The band a mean gets, shrinking with the square root of the sample count
    because that is how the noise of a mean shrinks. Twelve fixtures land on 5
    points, two land on 11: applying the twelve-fixture number to a two-sample
    mean would fail a whole run over one fixture wobbling inside its own band.
    """
    if sample_count <= 0:
        return MEAN_FLOOR
    return max(MEAN_FLOOR, math.ceil(BAND / math.sqrt(sample_count)))


Score = Annotated[int, Field(gt=0, lt=100)]
"""Reference score. Never 0 or 100: at the ends of the scale the band only opens
in one direction, so the fixture could not catch the engine drifting the other
way."""


class CalibrationFixture(BaseModel):
    """One annotated text. `slug` is the file name; everything else comes from
    the file, and unknown keys are rejected so a typo cannot pass silently."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    source: str
    """Provenance of the text. This repository must not ship third party essays,
    so every fixture states where it came from."""
    chapter_kind: ChapterKind
    exam: Exam
    """Together these decide what the engine is asked to grade, through
    grading_spec: the fixture never re-derives that rule."""
    chapter_objective: str
    evaluator_brief: str
    persona_brief: str
    min_words: int = Field(gt=0)
    max_words: int = Field(gt=0)
    spelling_anchors: int = Field(ge=0)
    """Unknown words the vendored pt-BR dictionary finds in this text, pinned so
    a fixture cannot claim a norm profile the deterministic layer contradicts."""
    expected: dict[Dimension, Score]
    text: str

    @model_validator(mode="after")
    def _word_limits_make_sense(self) -> "CalibrationFixture":
        if self.max_words < self.min_words:
            raise ValueError(f"{self.slug}: max_words is below min_words")
        return self


class FixtureStatus(enum.StrEnum):
    OK = "ok"
    DRIFTED = "drifted"
    BROKEN = "broken"
    """The call failed, or came back without a dimension the reference
    annotates: no measurement at all, which is not the same as a bad one."""


@dataclass(frozen=True)
class DimensionDrift:
    dimension: Dimension
    expected: int
    actual: int
    """Only a scored dimension becomes a drift. One the engine skipped is not a
    delta of minus everything, it is a missing measurement."""

    @property
    def delta(self) -> int:
        """Actual minus expected: negative means the engine was harsher."""
        return self.actual - self.expected

    def within(self, band: int = BAND) -> bool:
        return abs(self.delta) <= band


@dataclass(frozen=True)
class FixtureOutcome:
    fixture: CalibrationFixture
    drifts: tuple[DimensionDrift, ...]
    missing: tuple[Dimension, ...] = ()
    error: str | None = None

    @property
    def status(self) -> FixtureStatus:
        if self.error is not None or self.missing:
            return FixtureStatus.BROKEN
        if all(drift.within() for drift in self.drifts):
            return FixtureStatus.OK
        return FixtureStatus.DRIFTED

    @property
    def passed(self) -> bool:
        return self.status == FixtureStatus.OK

    @property
    def worst_drift(self) -> DimensionDrift | None:
        if not self.drifts:
            return None
        return max(self.drifts, key=lambda drift: abs(drift.delta))

    def score_for(self, dimension: Dimension) -> int | None:
        return next((drift.actual for drift in self.drifts if drift.dimension == dimension), None)


@dataclass(frozen=True)
class DimensionMean:
    """One row of the report, over scored measurements only, so reference, engine
    and drift on the same row are always one arithmetic."""

    dimension: Dimension
    scored_count: int
    missing_count: int
    expected_mean: float | None
    actual_mean: float | None

    @property
    def delta_mean(self) -> float | None:
        if self.expected_mean is None or self.actual_mean is None:
            return None
        return self.actual_mean - self.expected_mean

    @property
    def tolerance(self) -> int:
        return mean_tolerance_for(self.scored_count)

    @property
    def shifted(self) -> bool:
        return self.delta_mean is not None and abs(self.delta_mean) > self.tolerance


@dataclass(frozen=True)
class Contrast:
    """A separation the fixture set was built to produce: 01 and 02 are the same
    argument with and without norm errors, 06 is off topic where 01 is on it.

    This is what the absolute means cannot see. A difference between two
    fixtures cancels any global offset of the engine, so it catches an engine
    that stopped discriminating even while every score still sits in its band.
    """

    stronger: str
    weaker: str
    dimension: Dimension
    min_gap: int

    def __str__(self) -> str:
        return f"{self.dimension.value}: {self.stronger} > {self.weaker} por {self.min_gap}"


CONTRASTS = (
    Contrast(
        "01-plano-concreto-forte", "02-mesmo-plano-com-erros-de-norma", Dimension.NORMA_CULTA, 40
    ),
    Contrast("01-plano-concreto-forte", "03-ideias-soltas-sem-coesao", Dimension.COESAO, 30),
    Contrast("01-plano-concreto-forte", "04-repertorio-falso", Dimension.REPERTORIO, 30),
    Contrast("01-plano-concreto-forte", "05-apelo-emocional-vazio", Dimension.PERSUASAO, 30),
    Contrast("01-plano-concreto-forte", "06-fuga-ao-tema", Dimension.COERENCIA, 30),
    Contrast("01-plano-concreto-forte", "07-ameaca-velada", Dimension.PERSUASAO, 30),
    Contrast("01-plano-concreto-forte", "08-lugar-comum-sem-repertorio", Dimension.REPERTORIO, 25),
    Contrast("01-plano-concreto-forte", "09-contradicao-interna", Dimension.COERENCIA, 30),
    Contrast(
        "10-chefe-dissertacao-completa",
        "11-chefe-sem-proposta-de-intervencao",
        Dimension.PROPOSTA_INTERVENCAO,
        40,
    ),
)


@dataclass(frozen=True)
class ContrastOutcome:
    contrast: Contrast
    gap: int | None
    """None when one of the two fixtures is in the run but was not scored. A
    contrast whose fixtures are not in the run at all is not reported: the run
    measured something else, and a missing measurement already fails through
    the broken fixtures."""

    @property
    def held(self) -> bool:
        return self.gap is not None and self.gap >= self.contrast.min_gap


@dataclass(frozen=True)
class CalibrationResult:
    prompt_version: str
    model: str
    effort: str | None
    """Prompt, model and effort all move the scores, so the report names the
    three of them: a run that does not say which one it measured is a run
    nobody can compare to the next."""
    outcomes: tuple[FixtureOutcome, ...]
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def passed_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.passed)

    @property
    def dimension_means(self) -> tuple[DimensionMean, ...]:
        return tuple(
            row for dimension in Dimension if (row := self._mean_for(dimension)) is not None
        )

    @property
    def global_delta_mean(self) -> float:
        deltas = [drift.delta for outcome in self.outcomes for drift in outcome.drifts]
        return sum(deltas) / len(deltas) if deltas else 0.0

    @property
    def global_tolerance(self) -> int:
        return mean_tolerance_for(sum(len(outcome.drifts) for outcome in self.outcomes))

    @property
    def contrast_outcomes(self) -> tuple[ContrastOutcome, ...]:
        present = {outcome.fixture.slug for outcome in self.outcomes}
        return tuple(
            ContrastOutcome(contrast, self._gap(contrast))
            for contrast in CONTRASTS
            if {contrast.stronger, contrast.weaker} <= present
        )

    def score_for(self, slug: str, dimension: Dimension) -> int | None:
        outcome = next((o for o in self.outcomes if o.fixture.slug == slug), None)
        return outcome.score_for(dimension) if outcome is not None else None

    def _gap(self, contrast: Contrast) -> int | None:
        stronger = self.score_for(contrast.stronger, contrast.dimension)
        weaker = self.score_for(contrast.weaker, contrast.dimension)
        if stronger is None or weaker is None:
            return None
        return stronger - weaker

    def _mean_for(self, dimension: Dimension) -> DimensionMean | None:
        drifts = [
            drift
            for outcome in self.outcomes
            for drift in outcome.drifts
            if drift.dimension == dimension
        ]
        missing = sum(
            1 for outcome in self.outcomes for skipped in outcome.missing if skipped == dimension
        )
        if not drifts and not missing:
            return None
        return DimensionMean(
            dimension=dimension,
            scored_count=len(drifts),
            missing_count=missing,
            expected_mean=_mean(drift.expected for drift in drifts) if drifts else None,
            actual_mean=_mean(drift.actual for drift in drifts) if drifts else None,
        )


def _mean(values: Iterable[int]) -> float:
    numbers = list(values)
    return sum(numbers) / len(numbers)


@dataclass(frozen=True)
class CalibrationVerdict:
    """Why the run failed, in the four ways it can: a fixture out of its band, a
    call that produced no score, a dimension shifted on average, or a contrast
    the fixture set was built to produce that the engine no longer makes."""

    drifted_fixtures: tuple[str, ...]
    broken_fixtures: tuple[str, ...]
    shifted_dimensions: tuple[Dimension, ...]
    collapsed_contrasts: tuple[str, ...]
    global_delta_mean: float
    global_tolerance: int

    @property
    def global_shift(self) -> bool:
        return abs(self.global_delta_mean) > self.global_tolerance

    @property
    def passed(self) -> bool:
        return not (
            self.drifted_fixtures
            or self.broken_fixtures
            or self.shifted_dimensions
            or self.collapsed_contrasts
            or self.global_shift
        )

    @property
    def summary(self) -> str:
        if self.passed:
            return "sem drift: fixtures na banda, medias estaveis e contrastes de pe"
        return "; ".join(self._reasons())

    def _reasons(self) -> list[str]:
        reasons = []
        if self.broken_fixtures:
            reasons.append(f"sem nota em: {', '.join(self.broken_fixtures)}")
        if self.drifted_fixtures:
            reasons.append(f"fora da banda: {', '.join(self.drifted_fixtures)}")
        if self.collapsed_contrasts:
            reasons.append(f"contraste perdido em: {'; '.join(self.collapsed_contrasts)}")
        if self.shifted_dimensions:
            shifted = ", ".join(dimension.value for dimension in self.shifted_dimensions)
            reasons.append(f"media deslocada em: {shifted}")
        if self.global_shift:
            reasons.append(
                f"media geral deslocada em {self.global_delta_mean:+.1f} "
                f"pontos (limite {self.global_tolerance})"
            )
        return reasons


def judge(result: CalibrationResult) -> CalibrationVerdict:
    """The gate. Per fixture it catches spikes; on the means it catches a
    uniform shift, which is what a prompt change actually does; on the contrasts
    it catches an engine that stopped telling the fixtures apart, which no
    absolute measure notices."""
    return CalibrationVerdict(
        drifted_fixtures=_slugs(result, FixtureStatus.DRIFTED),
        broken_fixtures=_slugs(result, FixtureStatus.BROKEN),
        shifted_dimensions=tuple(row.dimension for row in result.dimension_means if row.shifted),
        collapsed_contrasts=tuple(
            f"{outcome.contrast} (medido {outcome.gap if outcome.gap is not None else 'nada'})"
            for outcome in result.contrast_outcomes
            if not outcome.held
        ),
        global_delta_mean=result.global_delta_mean,
        global_tolerance=result.global_tolerance,
    )


def _slugs(result: CalibrationResult, status: FixtureStatus) -> tuple[str, ...]:
    return tuple(outcome.fixture.slug for outcome in result.outcomes if outcome.status == status)


def load_fixtures() -> tuple[CalibrationFixture, ...]:
    """Reads the annotated fixtures into typed objects. Adding a fixture is
    dropping one JSON file in tests/calibration/fixtures (see README)."""
    return tuple(_parse(path) for path in sorted(FIXTURES_DIR.glob("*.json")))


def _parse(path: pathlib.Path) -> CalibrationFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "slug" in raw:
        raise ValueError(f"{path.name}: the file name is the slug, do not repeat it inside")
    return CalibrationFixture.model_validate({**raw, "slug": path.stem})


def compare(fixture: CalibrationFixture, actual: dict[Dimension, int]) -> FixtureOutcome:
    """Scores the engine returned against the reference. A dimension the engine
    skipped is reported as missing, never as a score of zero."""
    return FixtureOutcome(
        fixture=fixture,
        drifts=tuple(
            DimensionDrift(dimension=dimension, expected=expected, actual=actual[dimension])
            for dimension, expected in fixture.expected.items()
            if dimension in actual
        ),
        missing=tuple(dimension for dimension in fixture.expected if dimension not in actual),
    )


def failed(fixture: CalibrationFixture, error: str) -> FixtureOutcome:
    """A fixture whose call never produced scores. The run keeps going and the
    report says so, instead of losing every measurement taken before it."""
    return FixtureOutcome(fixture=fixture, drifts=(), missing=tuple(fixture.expected), error=error)


def build_report(result: CalibrationResult) -> str:
    """Markdown for the job summary: what was measured, the mean per dimension,
    the contrasts, and the fixtures worth looking at, failures first."""
    verdict = judge(result)
    lines = [
        f"## Calibracao do motor ({result.prompt_version}, {result.model}, effort {result.effort})",
        "",
        f"**{result.passed_count}/{len(result.outcomes)} fixtures dentro da banda.** "
        f"{verdict.summary}.",
        "",
        f"Media geral do desvio: {result.global_delta_mean:+.1f} pontos "
        f"(limite {result.global_tolerance}). Custo da corrida: "
        f"{result.input_tokens} tokens de entrada e {result.output_tokens} de saida.",
        "",
        "| Dimensao | Referencia media | Motor media | Desvio medio | Limite | Sem nota |",
        "| --- | --- | --- | --- | --- | --- |",
        *_dimension_rows(result),
        "",
        "### Contrastes que as fixtures existem para produzir",
        "",
        "| Contraste | Minimo | Medido | OK |",
        "| --- | --- | --- | --- |",
        *_contrast_rows(result),
        "",
        "### Fixtures por desvio",
        "",
        "| Fixture | Pior dimensao | Desvio | OK |",
        "| --- | --- | --- | --- |",
        *_fixture_rows(result),
    ]
    return "\n".join(lines)


def _dimension_rows(result: CalibrationResult) -> list[str]:
    return [
        f"| {row.dimension.value} | {_number(row.expected_mean)} | {_number(row.actual_mean)} "
        f"| {_delta(row.delta_mean)} | {row.tolerance if row.scored_count else '-'} "
        f"| {row.missing_count} |"
        for row in result.dimension_means
    ]


def _number(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def _delta(value: float | None) -> str:
    return "-" if value is None else f"{value:+.1f}"


def _contrast_rows(result: CalibrationResult) -> list[str]:
    return [
        f"| {outcome.contrast} | {outcome.contrast.min_gap} "
        f"| {outcome.gap if outcome.gap is not None else 'sem nota'} "
        f"| {'sim' if outcome.held else 'NAO'} |"
        for outcome in result.contrast_outcomes
    ]


def _fixture_rows(result: CalibrationResult) -> list[str]:
    return [_fixture_row(outcome) for outcome in sorted(result.outcomes, key=_rank, reverse=True)]


_STATUS_RANK = {FixtureStatus.BROKEN: 2, FixtureStatus.DRIFTED: 1, FixtureStatus.OK: 0}


def _rank(outcome: FixtureOutcome) -> tuple[int, int]:
    """A call that produced nothing outranks a drift, and a drift outranks a
    fixture inside its band, so the top of the summary is what needs attention.
    """
    worst = outcome.worst_drift
    return (_STATUS_RANK[outcome.status], abs(worst.delta) if worst else 0)


def _fixture_row(outcome: FixtureOutcome) -> str:
    if outcome.error is not None:
        return f"| {outcome.fixture.slug} | - | erro: {outcome.error} | NAO |"
    if outcome.missing:
        skipped = ", ".join(dimension.value for dimension in outcome.missing)
        return f"| {outcome.fixture.slug} | {skipped} | sem nota | NAO |"
    worst = outcome.worst_drift
    dimension = worst.dimension.value if worst else "-"
    delta = f"{worst.delta:+d}" if worst else "-"
    mark = "sim" if outcome.passed else "NAO"
    return f"| {outcome.fixture.slug} | {dimension} | {delta} | {mark} |"
