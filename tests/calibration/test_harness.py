"""Issue #12: the calibration harness itself, tests first (TDD).

These run on every PR: the comparison, the gate and the report are pure logic
and must need neither an API key nor a database. The suite that actually calls
the engine lives in test_engine_calibration.py and is marked `calibration`.
"""

import pytest
from pydantic import ValidationError

from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.domain.enums import ChapterKind, Dimension, Exam
from argumenta.domain.evaluation import BASE_DIMENSIONS
from argumenta.domain.lenses import grading_spec
from tests.calibration.harness import (
    CalibrationFixture,
    CalibrationResult,
    DimensionDrift,
    build_report,
    compare,
    failed,
    judge,
    load_fixtures,
)

_EXPECTED: dict[Dimension, int] = {
    Dimension.NORMA_CULTA: 80,
    Dimension.COESAO: 70,
    Dimension.COERENCIA: 70,
    Dimension.REPERTORIO: 60,
    Dimension.PERSUASAO: 60,
}


def _scored(**overrides: int) -> dict[Dimension, int]:
    """The reference scores with a few dimensions moved, typed once here so
    every test reads as the deviation it is testing."""
    return {**_EXPECTED, **{Dimension(name): score for name, score in overrides.items()}}


def _fixture(slug: str = "exemplo") -> CalibrationFixture:
    return CalibrationFixture(
        slug=slug,
        title="Exemplo",
        source="autoral",
        chapter_kind=ChapterKind.CONFRONTO,
        exam=Exam.ENEM,
        chapter_objective="Convencer a diretora.",
        evaluator_brief="Plano concreto conta.",
        persona_brief="Pragmatica.",
        min_words=120,
        max_words=250,
        spelling_anchors=0,
        text="palavra " * 130,
        expected=_EXPECTED,
        tolerance=15,
    )


def _result(*outcome_specs: tuple[str, dict[Dimension, int]]) -> CalibrationResult:
    return CalibrationResult(
        prompt_version="eval-v1.1",
        model="claude-sonnet-5",
        outcomes=tuple(compare(_fixture(slug), actual) for slug, actual in outcome_specs),
        input_tokens=2400,
        output_tokens=900,
    )


class TestCompare:
    def test_scores_inside_the_tolerance_pass(self) -> None:
        actual: dict[Dimension, int] = {d: value + 10 for d, value in _EXPECTED.items()}

        outcome = compare(_fixture(), actual)

        assert outcome.passed is True
        assert all(abs(drift.delta) == 10 for drift in outcome.drifts)

    def test_a_dimension_beyond_the_tolerance_fails_the_fixture(self) -> None:
        outcome = compare(_fixture(), _scored(repertorio=20))

        assert outcome.passed is False
        worst = outcome.worst_drift
        assert worst is not None
        assert worst.dimension == Dimension.REPERTORIO
        assert worst.delta == -40

    def test_tolerance_is_per_fixture(self) -> None:
        tolerant = _fixture().model_copy(update={"tolerance": 45})

        assert compare(tolerant, _scored(repertorio=20)).passed is True

    def test_a_dimension_the_engine_skipped_is_missing_not_a_score_of_zero(self) -> None:
        """Treating it as zero would invent a delta of minus everything and
        poison every mean in the report."""
        actual: dict[Dimension, int] = {d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO}

        outcome = compare(_fixture(), actual)

        assert outcome.passed is False
        assert outcome.missing == (Dimension.COESAO,)
        assert all(drift.dimension != Dimension.COESAO for drift in outcome.drifts)

    def test_a_dimension_nobody_annotated_is_not_compared(self) -> None:
        outcome = compare(_fixture(), _scored(proposta_intervencao=3))

        assert [drift.dimension for drift in outcome.drifts] == list(_EXPECTED)


class TestGate:
    def test_a_uniform_shift_fails_even_with_every_fixture_inside_its_band(self) -> None:
        """The regression this suite exists for: a prompt that hardened the
        correction by 14 points everywhere. No single band notices it."""
        shifted: dict[Dimension, int] = {d: value - 14 for d, value in _EXPECTED.items()}
        result = _result(*((f"fixture-{index}", shifted) for index in range(11)))

        verdict = judge(result)

        assert all(outcome.passed for outcome in result.outcomes)
        assert verdict.passed is False
        assert verdict.global_delta_mean == pytest.approx(-14.0)
        assert set(verdict.shifted_dimensions) == set(_EXPECTED)

    def test_noise_around_the_reference_passes(self) -> None:
        up: dict[Dimension, int] = {d: value + 4 for d, value in _EXPECTED.items()}
        down: dict[Dimension, int] = {d: value - 4 for d, value in _EXPECTED.items()}

        verdict = judge(_result(("acima", up), ("abaixo", down)))

        assert verdict.passed is True
        assert verdict.summary.startswith("sem drift")

    def test_a_single_spike_fails_the_run(self) -> None:
        verdict = judge(
            _result(
                ("boa", _EXPECTED),
                ("pico", _scored(persuasao=10)),
            )
        )

        assert verdict.passed is False
        assert verdict.drifted_fixtures == ("pico",)

    def test_a_call_that_never_scored_fails_the_run_and_is_named(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            model="claude-sonnet-5",
            outcomes=(compare(_fixture("boa"), _EXPECTED), failed(_fixture("caiu"), "429")),
        )

        verdict = judge(result)

        assert verdict.passed is False
        assert verdict.broken_fixtures == ("caiu",)
        assert "caiu" in verdict.summary


class TestReport:
    def test_report_names_what_was_measured(self) -> None:
        report = build_report(_result(("boa", _EXPECTED), ("ruim", _scored(persuasao=10))))

        assert "eval-v1.1" in report
        assert "claude-sonnet-5" in report, "a model bump moves the scores too"
        assert "2400" in report and "900" in report, "the run must report its cost"
        assert "1/2" in report

    def test_the_dimension_row_adds_up(self) -> None:
        """Reference, engine and drift on the same row must be one arithmetic:
        a row reading 70, 70 and -35 is a report nobody can trust."""
        scored = _scored(coesao=60)
        without_coesao: dict[Dimension, int] = {
            d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO
        }
        result = _result(("com", scored), ("sem", without_coesao))

        row = next(row for row in result.dimension_means if row.dimension == Dimension.COESAO)

        assert (row.expected_mean, row.actual_mean, row.delta_mean) == (70.0, 60.0, -10.0)
        assert row.missing_count == 1
        assert "| coesao | 70.0 | 60.0 | -10.0 | 1 |" in build_report(result)

    def test_a_failing_fixture_is_never_listed_below_a_passing_one(self) -> None:
        report = build_report(
            _result(
                ("passou-com-14", {d: v + 14 for d, v in _EXPECTED.items()}),
                (
                    "falhou-sem-nota",
                    {d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO},
                ),
            )
        )

        assert report.index("falhou-sem-nota") < report.index("passou-com-14")

    def test_a_failed_call_shows_the_reason_instead_of_a_fake_delta(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            model="claude-sonnet-5",
            outcomes=(failed(_fixture("caiu"), "overloaded_error"),),
        )

        report = build_report(result)

        assert "overloaded_error" in report
        assert "0/1" in report


class TestFixtureFiles:
    def test_the_repository_ships_at_least_ten_fixtures(self) -> None:
        assert len(load_fixtures()) >= 10

    def test_every_fixture_scores_what_its_chapter_and_exam_require(self) -> None:
        """The fixture declares chapter and exam; what gets graded is the
        product rule, so a fixture cannot annotate a dimension the engine will
        not be asked for, nor skip one it will."""
        for fixture in load_fixtures():
            spec = grading_spec(fixture.chapter_kind, fixture.exam)
            assert set(fixture.expected) == set(spec.dimensions), fixture.slug

    def test_the_boss_essay_is_covered_under_both_exams(self) -> None:
        boss = [f for f in load_fixtures() if f.chapter_kind == ChapterKind.CHEFE]
        exams = {fixture.exam for fixture in boss}

        assert exams == set(Exam), "FUVEST grades a boss essay without the proposal"
        assert any(Dimension.PROPOSTA_INTERVENCAO in f.expected for f in boss)
        assert any(set(f.expected) == set(BASE_DIMENSIONS) for f in boss)

    def test_every_fixture_respects_its_own_word_limits(self) -> None:
        """Outside the limits the fixture would be measuring a text the game
        would never accept, and rule 8 of the prompt penalises the mismatch."""
        for fixture in load_fixtures():
            words = len(fixture.text.split())
            assert fixture.min_words <= words <= fixture.max_words, (
                f"{fixture.slug} has {words} words, outside {fixture.min_words}-{fixture.max_words}"
            )

    def test_the_declared_norm_profile_matches_the_real_spell_checker(self) -> None:
        """Production always sends deterministic anchors, and the prompt orders
        the engine to ignore spelling outside that list. A fixture claiming a
        norm score has to agree with the dictionary the game actually uses."""
        checker = SpyllsSpellChecker()
        for fixture in load_fixtures():
            found = len(checker.find_unknown_words(fixture.text))
            assert found == fixture.spelling_anchors, (
                f"{fixture.slug} declares {fixture.spelling_anchors} unknown words, "
                f"the dictionary finds {found}"
            )

    def test_a_high_norm_score_cannot_come_with_unknown_words(self) -> None:
        for fixture in load_fixtures():
            if fixture.expected[Dimension.NORMA_CULTA] >= 70:
                assert fixture.spelling_anchors == 0, fixture.slug

    def test_reference_scores_leave_room_to_drift_in_both_directions(self) -> None:
        """A reference of 95 with a band of 15 can only catch the engine getting
        harsher: there is no room above. Same at the bottom."""
        for fixture in load_fixtures():
            for dimension, score in fixture.expected.items():
                assert fixture.tolerance <= score <= 100 - fixture.tolerance, (
                    f"{fixture.slug}.{dimension.value} = {score} is pinned against a wall"
                )

    def test_a_fixture_with_an_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationFixture.model_validate({**_fixture().model_dump(), "notas": 10})

    def test_a_score_outside_the_internal_scale_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationFixture.model_validate(
                {**_fixture().model_dump(), "expected": {Dimension.COESAO: 200}}
            )


def test_drift_reads_as_actual_minus_expected() -> None:
    drift = DimensionDrift(dimension=Dimension.PERSUASAO, expected=60, actual=45)

    assert drift.delta == -15
    assert drift.within(15) is True
    assert drift.within(14) is False


def test_calibration_marker_is_registered(pytestconfig: pytest.Config) -> None:
    """The engine suite must be opt-in, never blocking a normal PR."""
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("calibration") for marker in markers)
