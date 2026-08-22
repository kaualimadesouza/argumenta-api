"""Calibration harness: compares the engine against annotated fixtures.

This lives under tests/ on purpose. It is not product behaviour, it is how we
measure the engine: the comparison rule and the report are the deliverable, and
they must be testable without an API key.
"""

import json
import pathlib
from dataclasses import dataclass, field

from argumenta.domain.enums import Dimension

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

DEFAULT_TOLERANCE = 15
"""Points per dimension. Wide on purpose: an LLM is not a ruler, and the point
is catching drift, not pretending the reference grades are exact."""


@dataclass(frozen=True)
class CalibrationFixture:
    slug: str
    title: str
    source: str
    """Where the text came from. Authorial fixtures say so, plainly."""
    chapter_objective: str
    evaluator_brief: str
    persona_brief: str
    min_words: int
    max_words: int
    text: str
    expected: dict[Dimension, int]
    """Reference score per dimension, 0-100."""
    tolerance: int = DEFAULT_TOLERANCE


@dataclass(frozen=True)
class DimensionDrift:
    dimension: Dimension
    expected: int
    actual: int | None
    """None when the engine did not score this dimension at all."""
    tolerance: int

    @property
    def delta(self) -> int:
        """Actual minus expected: negative means the engine was harsher."""
        if self.actual is None:
            return -self.expected
        return self.actual - self.expected

    @property
    def within_tolerance(self) -> bool:
        return self.actual is not None and abs(self.delta) <= self.tolerance


@dataclass(frozen=True)
class FixtureOutcome:
    fixture: CalibrationFixture
    drifts: tuple[DimensionDrift, ...]

    @property
    def passed(self) -> bool:
        return all(drift.within_tolerance for drift in self.drifts)

    @property
    def worst_drift(self) -> DimensionDrift | None:
        if not self.drifts:
            return None
        return max(self.drifts, key=lambda drift: abs(drift.delta))


@dataclass(frozen=True)
class CalibrationResult:
    prompt_version: str
    outcomes: tuple[FixtureOutcome, ...] = field(default_factory=tuple)

    @property
    def passed_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.passed)


def load_fixtures() -> tuple[CalibrationFixture, ...]:
    """Reads the annotated fixtures into typed objects. Adding a fixture is
    dropping one JSON file in tests/calibration/fixtures (see README)."""
    fixtures = [_parse(path) for path in sorted(FIXTURES_DIR.glob("*.json"))]
    return tuple(fixtures)


def _parse(path: pathlib.Path) -> CalibrationFixture:
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = {Dimension(name): int(score) for name, score in raw["expected"].items()}
    return CalibrationFixture(
        slug=raw.get("slug", path.stem),
        title=raw["title"],
        source=raw["source"],
        chapter_objective=raw["chapter_objective"],
        evaluator_brief=raw["evaluator_brief"],
        persona_brief=raw["persona_brief"],
        min_words=int(raw["min_words"]),
        max_words=int(raw["max_words"]),
        text=raw["text"],
        expected=expected,
        tolerance=int(raw.get("tolerance", DEFAULT_TOLERANCE)),
    )


def compare(fixture: CalibrationFixture, actual: dict[Dimension, int]) -> FixtureOutcome:
    drifts = tuple(
        DimensionDrift(
            dimension=dimension,
            expected=expected,
            actual=actual.get(dimension),
            tolerance=fixture.tolerance,
        )
        for dimension, expected in fixture.expected.items()
    )
    return FixtureOutcome(fixture=fixture, drifts=drifts)


def build_report(result: CalibrationResult) -> str:
    """Markdown for the job summary: headline, mean score per dimension, and
    the fixtures that drifted most, worst first."""
    total = len(result.outcomes)
    lines = [
        f"## Calibracao do motor ({result.prompt_version})",
        "",
        f"**{result.passed_count}/{total} fixtures dentro da tolerancia.**",
        "",
        "| Dimensao | Referencia media | Motor media | Desvio medio |",
        "| --- | --- | --- | --- |",
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
    rows = []
    for dimension in Dimension:
        drifts = [
            drift
            for outcome in result.outcomes
            for drift in outcome.drifts
            if drift.dimension == dimension
        ]
        if not drifts:
            continue
        scored = [drift.actual for drift in drifts if drift.actual is not None]
        expected_mean = sum(drift.expected for drift in drifts) / len(drifts)
        actual_mean = sum(scored) / len(scored) if scored else 0.0
        delta_mean = sum(drift.delta for drift in drifts) / len(drifts)
        rows.append(
            f"| {dimension.value} | {expected_mean:.1f} | {actual_mean:.1f} | {delta_mean:+.1f} |"
        )
    return rows


def _fixture_rows(result: CalibrationResult) -> list[str]:
    ranked = sorted(
        result.outcomes,
        key=lambda outcome: abs(outcome.worst_drift.delta) if outcome.worst_drift else 0,
        reverse=True,
    )
    rows = []
    for outcome in ranked:
        worst = outcome.worst_drift
        dimension = worst.dimension.value if worst else "-"
        delta = f"{worst.delta:+d}" if worst else "-"
        mark = "sim" if outcome.passed else "NAO"
        rows.append(f"| {outcome.fixture.slug} | {dimension} | {delta} | {mark} |")
    return rows
