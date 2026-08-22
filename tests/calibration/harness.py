"""Calibration harness: compares the engine against annotated fixtures.

This lives under tests/ on purpose. It is not product behaviour, it is how we
measure the engine: the comparison rule, the gate and the report are the
deliverable, and they must be testable without an API key.
"""

import json
import pathlib
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from argumenta.domain.enums import ChapterKind, Dimension, Exam

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

DEFAULT_TOLERANCE = 15
"""Points per dimension, per fixture. Wide on purpose: an LLM is not a ruler,
and the point is catching drift, not pretending the reference grades are exact."""

MEAN_TOLERANCE = 5
"""Points on the average across fixtures. Much tighter than the per-fixture
band, and it has to be: a mean over dozens of measurements absorbs sampling
noise, so a systematic shift shows up here long before any single fixture
breaks its own band."""

Score = Annotated[int, Field(ge=0, le=100)]


class CalibrationFixture(BaseModel):
    """One annotated text. `slug` is the file name; everything else comes from
    the file, and unknown keys are rejected so a typo cannot pass silently."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    title: str
    source: str
    """Where the text came from. Authorial fixtures say so, plainly."""
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
    """Reference score per dimension, 0-100."""
    text: str
    tolerance: int = Field(default=DEFAULT_TOLERANCE, gt=0)


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

    def within(self, tolerance: int) -> bool:
        return abs(self.delta) <= tolerance


@dataclass(frozen=True)
class FixtureOutcome:
    fixture: CalibrationFixture
    drifts: tuple[DimensionDrift, ...]
    missing: tuple[Dimension, ...] = ()
    """Dimensions the reference annotates and the engine did not score."""
    error: str | None = None
    """Set when the call itself failed, so one bad request does not throw away
    the fixtures that were measured before it."""

    @property
    def passed(self) -> bool:
        if self.error is not None or self.missing:
            return False
        return all(drift.within(self.fixture.tolerance) for drift in self.drifts)

    @property
    def worst_drift(self) -> DimensionDrift | None:
        if not self.drifts:
            return None
        return max(self.drifts, key=lambda drift: abs(drift.delta))


@dataclass(frozen=True)
class DimensionMean:
    """One row of the report, computed over scored measurements only, so the
    three columns always add up."""

    dimension: Dimension
    expected_mean: float
    actual_mean: float
    missing_count: int

    @property
    def delta_mean(self) -> float:
        return self.actual_mean - self.expected_mean


@dataclass(frozen=True)
class CalibrationResult:
    prompt_version: str
    model: str
    outcomes: tuple[FixtureOutcome, ...]
    input_tokens: int = 0
    output_tokens: int = 0
    """What the run cost. A prompt bump and a model bump both move the scores,
    so the report has to name which one it measured."""

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
        if not drifts:
            if not missing:
                return None
            return DimensionMean(dimension, 0.0, 0.0, missing)
        return DimensionMean(
            dimension=dimension,
            expected_mean=sum(drift.expected for drift in drifts) / len(drifts),
            actual_mean=sum(drift.actual for drift in drifts) / len(drifts),
            missing_count=missing,
        )


@dataclass(frozen=True)
class CalibrationVerdict:
    """Why the run failed, in the three ways it can: a fixture out of its band,
    a dimension shifted on average, or a call that never produced a score."""

    drifted_fixtures: tuple[str, ...]
    broken_fixtures: tuple[str, ...]
    shifted_dimensions: tuple[Dimension, ...]
    global_delta_mean: float
    mean_tolerance: int

    @property
    def passed(self) -> bool:
        return not (
            self.drifted_fixtures
            or self.broken_fixtures
            or self.shifted_dimensions
            or abs(self.global_delta_mean) > self.mean_tolerance
        )

    @property
    def summary(self) -> str:
        if self.passed:
            return "sem drift: fixtures na banda e medias estaveis"
        reasons = []
        if self.broken_fixtures:
            reasons.append(f"sem nota em: {', '.join(self.broken_fixtures)}")
        if self.drifted_fixtures:
            reasons.append(f"fora da banda: {', '.join(self.drifted_fixtures)}")
        if self.shifted_dimensions:
            shifted = ", ".join(dimension.value for dimension in self.shifted_dimensions)
            reasons.append(f"media deslocada em: {shifted}")
        if abs(self.global_delta_mean) > self.mean_tolerance:
            reasons.append(
                f"media geral deslocada em {self.global_delta_mean:+.1f} "
                f"pontos (limite {self.mean_tolerance})"
            )
        return "; ".join(reasons)


def judge(result: CalibrationResult, mean_tolerance: int = MEAN_TOLERANCE) -> CalibrationVerdict:
    """The gate. Per fixture it catches spikes; on the averages it catches a
    uniform shift, which is what a prompt change actually does and what no
    single fixture band would ever notice."""
    return CalibrationVerdict(
        drifted_fixtures=tuple(
            outcome.fixture.slug
            for outcome in result.outcomes
            if not outcome.passed and outcome.error is None and not outcome.missing
        ),
        broken_fixtures=tuple(
            outcome.fixture.slug
            for outcome in result.outcomes
            if outcome.error is not None or outcome.missing
        ),
        shifted_dimensions=tuple(
            row.dimension for row in result.dimension_means if abs(row.delta_mean) > mean_tolerance
        ),
        global_delta_mean=result.global_delta_mean,
        mean_tolerance=mean_tolerance,
    )


def load_fixtures() -> tuple[CalibrationFixture, ...]:
    """Reads the annotated fixtures into typed objects. Adding a fixture is
    dropping one JSON file in tests/calibration/fixtures (see README)."""
    return tuple(_parse(path) for path in sorted(FIXTURES_DIR.glob("*.json")))


def _parse(path: pathlib.Path) -> CalibrationFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
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
    and the fixtures that drifted most, failures first."""
    verdict = judge(result)
    total = len(result.outcomes)
    lines = [
        f"## Calibracao do motor ({result.prompt_version} em {result.model})",
        "",
        f"**{result.passed_count}/{total} fixtures dentro da tolerancia.** {verdict.summary}.",
        "",
        f"Media geral do desvio: {result.global_delta_mean:+.1f} pontos. "
        f"Custo da corrida: {result.input_tokens} tokens de entrada e "
        f"{result.output_tokens} de saida.",
        "",
        "| Dimensao | Referencia media | Motor media | Desvio medio | Sem nota |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(_dimension_rows(result))
    lines.extend(
        [
            "",
            "### Fixtures por desvio",
            "",
            "| Fixture | Pior dimensao | Desvio | OK |",
            "| --- | --- | --- | --- |",
        ]
    )
    lines.extend(_fixture_rows(result))
    return "\n".join(lines)


def _dimension_rows(result: CalibrationResult) -> list[str]:
    return [
        f"| {row.dimension.value} | {row.expected_mean:.1f} | {row.actual_mean:.1f} "
        f"| {row.delta_mean:+.1f} | {row.missing_count} |"
        for row in result.dimension_means
    ]


def _fixture_rows(result: CalibrationResult) -> list[str]:
    ranked = sorted(result.outcomes, key=_rank, reverse=True)
    return [_fixture_row(outcome) for outcome in ranked]


def _rank(outcome: FixtureOutcome) -> tuple[int, int]:
    """Failures first, then by how far the worst dimension drifted, so what the
    reader sees at the top of the summary is what needs attention."""
    worst = outcome.worst_drift
    return (0 if outcome.passed else 1, abs(worst.delta) if worst else 0)


def _fixture_row(outcome: FixtureOutcome) -> str:
    if outcome.error is not None:
        return f"| {outcome.fixture.slug} | - | erro: {outcome.error} | NAO |"
    if outcome.missing:
        skipped = ", ".join(dimension.value for dimension in outcome.missing)
        return f"| {outcome.fixture.slug} | {skipped} | sem nota | NAO |"
    worst = outcome.worst_drift
    dimension = worst.dimension.value if worst else "-"
    delta = f"{worst.delta:+d}" if worst else "-"
    return (
        f"| {outcome.fixture.slug} | {dimension} | {delta} | {'sim' if outcome.passed else 'NAO'} |"
    )
