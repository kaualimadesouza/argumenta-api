"""Issue #12: the calibration harness itself, tests first (TDD).

These run on every PR: the comparison and the report are pure logic and must
not need an API key. The suite that actually calls the engine lives in
test_engine_calibration.py and is marked `calibration`.
"""

import pytest

from argumenta.domain.enums import Dimension
from tests.calibration.harness import (
    CalibrationFixture,
    CalibrationResult,
    DimensionDrift,
    FixtureOutcome,
    build_report,
    compare,
    load_fixtures,
)

_EXPECTED: dict[Dimension, int] = {
    Dimension.NORMA_CULTA: 80,
    Dimension.COESAO: 70,
    Dimension.COERENCIA: 70,
    Dimension.REPERTORIO: 60,
    Dimension.PERSUASAO: 60,
}


def _fixture(slug: str = "exemplo") -> CalibrationFixture:
    return CalibrationFixture(
        slug=slug,
        title="Exemplo",
        source="autoral",
        chapter_objective="Convencer a diretora.",
        evaluator_brief="Plano concreto conta.",
        persona_brief="Pragmatica.",
        min_words=120,
        max_words=250,
        text="palavra " * 130,
        expected=_EXPECTED,
        tolerance=15,
    )


class TestCompare:
    def test_scores_inside_the_tolerance_pass(self) -> None:
        actual = {d: value + 10 for d, value in _EXPECTED.items()}

        outcome = compare(_fixture(), actual)

        assert outcome.passed is True
        assert all(abs(drift.delta) == 10 for drift in outcome.drifts)

    def test_a_dimension_beyond_the_tolerance_fails_the_fixture(self) -> None:
        actual = {**_EXPECTED, Dimension.REPERTORIO: 20}

        outcome = compare(_fixture(), actual)

        assert outcome.passed is False
        worst = outcome.worst_drift
        assert worst is not None
        assert worst.dimension == Dimension.REPERTORIO
        assert worst.delta == -40

    def test_tolerance_is_per_fixture(self) -> None:
        tolerant = CalibrationFixture(**{**vars(_fixture()), "tolerance": 45})

        assert compare(tolerant, {**_EXPECTED, Dimension.REPERTORIO: 20}).passed is True

    def test_a_missing_dimension_is_a_failure_not_a_crash(self) -> None:
        actual: dict[Dimension, int] = {d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO}

        outcome = compare(_fixture(), actual)

        assert outcome.passed is False
        assert any(drift.actual is None for drift in outcome.drifts)


class TestReport:
    def _result(self, passed: bool, slug: str) -> FixtureOutcome:
        actual = {**_EXPECTED} if passed else {**_EXPECTED, Dimension.PERSUASAO: 10}
        return compare(_fixture(slug), actual)

    def test_report_states_the_prompt_version_and_the_headline(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            outcomes=(self._result(True, "boa"), self._result(False, "ruim")),
        )

        report = build_report(result)

        assert "eval-v1.1" in report
        assert "1/2" in report, "the summary must say how many fixtures passed"
        assert "ruim" in report

    def test_report_lists_the_mean_score_per_dimension(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1", outcomes=(self._result(True, "boa"),)
        )

        report = build_report(result)

        for dimension in Dimension:
            if dimension in _EXPECTED:
                assert dimension.value in report

    def test_report_ranks_the_worst_drifts_first(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            outcomes=(self._result(False, "ruim"), self._result(True, "boa")),
        )

        report = build_report(result)

        assert report.index("ruim") < report.index("boa")


class TestFixtureFiles:
    def test_the_repository_ships_at_least_ten_fixtures(self) -> None:
        assert len(load_fixtures()) >= 10

    def test_every_fixture_is_typed_and_scored_on_every_dimension(self) -> None:
        for fixture in load_fixtures():
            assert isinstance(fixture, CalibrationFixture)
            assert set(fixture.expected) >= set(_EXPECTED), fixture.slug
            assert all(0 <= score <= 100 for score in fixture.expected.values()), fixture.slug
            assert fixture.tolerance > 0, fixture.slug

    def test_every_fixture_respects_its_own_word_limits(self) -> None:
        """A fixture outside the limits would measure the word gate, not the
        engine: the request would never reach the LLM."""
        for fixture in load_fixtures():
            words = len(fixture.text.split())
            assert fixture.min_words <= words <= fixture.max_words, (
                f"{fixture.slug} has {words} words, outside {fixture.min_words}-{fixture.max_words}"
            )

    def test_fixture_slugs_are_unique(self) -> None:
        slugs = [fixture.slug for fixture in load_fixtures()]

        assert len(slugs) == len(set(slugs))

    def test_drift_reads_as_actual_minus_expected(self) -> None:
        drift = DimensionDrift(dimension=Dimension.PERSUASAO, expected=60, actual=45, tolerance=15)

        assert drift.delta == -15
        assert drift.within_tolerance is True


def test_calibration_marker_is_registered(pytestconfig: pytest.Config) -> None:
    """The engine suite must be opt-in, never blocking a normal PR."""
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("calibration") for marker in markers)
