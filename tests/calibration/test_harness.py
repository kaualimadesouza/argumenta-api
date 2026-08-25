"""Issue #12: the calibration harness itself, tests first (TDD).

These run on every PR: the comparison, the gate and the report are pure logic
and must need neither an API key nor a database. The suite that actually calls
the engine lives in test_engine_calibration.py and is marked `calibration`.
"""

import json
import pathlib

import pytest
from pydantic import ValidationError

from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.domain.enums import ChapterKind, Dimension, Exam
from argumenta.domain.evaluation import BASE_DIMENSIONS
from argumenta.domain.lenses import grading_spec
from argumenta.domain.submission import count_words
from tests.calibration.harness import (
    BAND,
    CONTRASTS,
    CalibrationFixture,
    CalibrationResult,
    DimensionDrift,
    FixtureStatus,
    build_report,
    compare,
    failed,
    judge,
    load_fixtures,
    mean_tolerance_for,
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
    )


def _run(*outcome_specs: tuple[str, dict[Dimension, int]]) -> CalibrationResult:
    return CalibrationResult(
        prompt_version="eval-v1.1",
        model="claude-sonnet-5",
        effort="high",
        outcomes=tuple(compare(_fixture(slug), actual) for slug, actual in outcome_specs),
        input_tokens=2400,
        output_tokens=900,
    )


class TestCompare:
    def test_scores_inside_the_band_pass(self) -> None:
        actual: dict[Dimension, int] = {d: value + 10 for d, value in _EXPECTED.items()}

        outcome = compare(_fixture(), actual)

        assert outcome.status == FixtureStatus.OK
        assert all(abs(drift.delta) == 10 for drift in outcome.drifts)

    def test_a_dimension_beyond_the_band_drifts_the_fixture(self) -> None:
        outcome = compare(_fixture(), _scored(repertorio=20))

        assert outcome.status == FixtureStatus.DRIFTED
        worst = outcome.worst_drift
        assert worst is not None
        assert (worst.dimension, worst.delta) == (Dimension.REPERTORIO, -40)

    def test_a_dimension_the_engine_skipped_is_missing_not_a_score_of_zero(self) -> None:
        """Treating it as zero would invent a delta of minus everything and
        poison every mean in the report."""
        actual: dict[Dimension, int] = {d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO}

        outcome = compare(_fixture(), actual)

        assert outcome.status == FixtureStatus.BROKEN
        assert outcome.missing == (Dimension.COESAO,)
        assert all(drift.dimension != Dimension.COESAO for drift in outcome.drifts)

    def test_a_dimension_nobody_annotated_is_not_compared(self) -> None:
        outcome = compare(_fixture(), _scored(proposta_intervencao=3))

        assert [drift.dimension for drift in outcome.drifts] == list(_EXPECTED)

    def test_baseline_band_is_tighter_than_gabarito_band(self) -> None:
        # Score is within BAND (15) of Gabarito, but outside TIGHT_BAND (5) of Baseline
        # Expected: 80, Baseline: 80, Actual: 70
        # Drift = -10. Within 15 (yes), within 5 (no) -> DRIFTED
        actual = _scored(norma_culta=70)
        baseline = _EXPECTED

        outcome = compare(_fixture(), actual, baseline)

        assert outcome.status == FixtureStatus.DRIFTED
        assert outcome.worst_drift is not None
        assert outcome.worst_drift.dimension == Dimension.NORMA_CULTA


class TestGate:
    def test_a_uniform_shift_fails_even_with_every_fixture_inside_its_band(self) -> None:
        """The regression this suite exists for: a prompt that hardened the
        correction by 14 points everywhere. No single band notices it."""
        shifted: dict[Dimension, int] = {d: value - 14 for d, value in _EXPECTED.items()}
        result = _run(*((f"fixture-{index}", shifted) for index in range(11)))

        verdict = judge(result)

        assert all(outcome.passed for outcome in result.outcomes)
        assert verdict.passed is False
        assert verdict.global_delta_mean == pytest.approx(-14.0)
        assert set(verdict.shifted_dimensions) == set(_EXPECTED)

    def test_noise_around_the_reference_passes(self) -> None:
        up: dict[Dimension, int] = {d: value + 2 for d, value in _EXPECTED.items()}
        down: dict[Dimension, int] = {d: value - 2 for d, value in _EXPECTED.items()}

        verdict = judge(_run(("acima", up), ("abaixo", down)))

        assert verdict.passed is True
        assert verdict.summary.startswith("sem drift")

    def test_a_single_spike_fails_the_run(self) -> None:
        verdict = judge(_run(("boa", _EXPECTED), ("pico", _scored(persuasao=10))))

        assert verdict.drifted_fixtures == ("pico",)
        assert verdict.passed is False

    def test_a_call_that_never_scored_fails_the_run_and_is_named(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            model="claude-sonnet-5",
            effort="high",
            outcomes=(compare(_fixture("boa"), _EXPECTED), failed(_fixture("caiu"), "429")),
        )

        verdict = judge(result)

        assert verdict.broken_fixtures == ("caiu",)
        assert "caiu" in verdict.summary

    def test_an_engine_that_stopped_discriminating_fails_on_the_contrasts(self) -> None:
        """Half the fixtures up, half down, by less than the band each: every
        fixture passes, every mean is stable, and the engine has still stopped
        telling a strong text from a weak one. Only the contrasts see it."""
        result = _inverted_discrimination()

        verdict = judge(result)

        assert all(outcome.passed for outcome in result.outcomes)
        assert verdict.shifted_dimensions == ()
        assert abs(verdict.global_delta_mean) <= verdict.global_tolerance
        assert verdict.collapsed_contrasts, "the gate cannot see level only"
        assert verdict.passed is False

    def test_the_reference_run_keeps_every_contrast(self) -> None:
        """The gate must not fail an engine that agrees with the gabarito."""
        verdict = judge(_reference_run())

        assert verdict.passed is True

    def test_a_mean_over_two_fixtures_gets_a_wider_band(self) -> None:
        """proposta_intervencao only exists in the boss fixtures. Judging a two
        sample mean by the twelve sample band would fail a whole run over one
        fixture wobbling inside its own band."""
        assert mean_tolerance_for(12) == 5
        assert mean_tolerance_for(2) == 11
        assert mean_tolerance_for(62) == 3

        result = _reference_run(wobble=("11-chefe-sem-proposta-de-intervencao", 11))
        verdict = judge(result)

        assert all(outcome.passed for outcome in result.outcomes)
        assert Dimension.PROPOSTA_INTERVENCAO not in verdict.shifted_dimensions
        assert verdict.passed is True


class TestReport:
    def test_report_names_what_was_measured(self) -> None:
        report = build_report(_run(("boa", _EXPECTED), ("ruim", _scored(persuasao=10))))

        assert "eval-v1.1" in report
        assert "claude-sonnet-5" in report, "a model bump moves the scores too"
        assert "effort high" in report, "and so does the thinking effort"
        assert "2400" in report and "900" in report, "the run must report its cost"
        assert "1/2" in report

    def test_the_dimension_row_adds_up(self) -> None:
        """Reference, engine and drift on the same row must be one arithmetic:
        a row reading 70, 70 and -35 is a report nobody can trust."""
        without_coesao: dict[Dimension, int] = {
            d: v for d, v in _EXPECTED.items() if d != Dimension.COESAO
        }
        result = _run(("com", _scored(coesao=60)), ("sem", without_coesao))

        row = next(row for row in result.dimension_means if row.dimension == Dimension.COESAO)

        assert (row.expected_mean, row.actual_mean, row.delta_mean) == (70.0, 60.0, -10.0)
        assert row.missing_count == 1
        assert "| coesao | 70.0 | 60.0 | -10.0 | 15 | 1 |" in build_report(result)

    def test_a_dimension_nobody_scored_shows_no_number_at_all(self) -> None:
        """Reporting 0.0 against a reference of 0.0 would read as "the engine
        gave zero" when the truth is "there is no measurement"."""
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            model="claude-sonnet-5",
            effort="high",
            outcomes=(failed(_fixture("caiu"), "401"),),
        )

        report = build_report(result)

        assert "| norma_culta | - | - | - | - | 1 |" in report
        assert "0/1" in report

    def test_a_failed_call_outranks_a_drift_in_the_table(self) -> None:
        result = CalibrationResult(
            prompt_version="eval-v1.1",
            model="claude-sonnet-5",
            effort="high",
            outcomes=(
                compare(_fixture("apenas-deslocada"), _scored(persuasao=10)),
                failed(_fixture("sem-resposta"), "overloaded_error"),
            ),
        )

        report = build_report(result)

        assert report.index("sem-resposta") < report.index("apenas-deslocada")
        assert "overloaded_error" in report

    def test_the_report_lists_the_contrasts(self) -> None:
        report = build_report(_reference_run())

        for contrast in CONTRASTS:
            assert str(contrast) in report


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
        """Counted the way the game counts, so the fixture cannot drift away
        from the gate a real submission passes through."""
        for fixture in load_fixtures():
            words = count_words(fixture.text)
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

    def test_the_references_produce_every_contrast_with_room_to_spare(self) -> None:
        """The gate reads the contrasts off the engine; if the gabarito itself
        does not produce them, the gate would fail an engine that agrees with
        it."""
        fixtures = {fixture.slug: fixture for fixture in load_fixtures()}
        for contrast in CONTRASTS:
            gap = (
                fixtures[contrast.stronger].expected[contrast.dimension]
                - fixtures[contrast.weaker].expected[contrast.dimension]
            )
            assert gap >= contrast.min_gap + BAND, f"{contrast} has only {gap} points"

    def test_a_fixture_with_an_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationFixture.model_validate({**_fixture().model_dump(), "notas": 10})

    def test_a_reference_at_the_end_of_the_scale_is_rejected(self) -> None:
        """A reference of 100 can only catch the engine getting harsher: there
        is nothing above it to drift into."""
        for impossible in (0, 100):
            with pytest.raises(ValidationError):
                CalibrationFixture.model_validate(
                    {
                        **_fixture().model_dump(),
                        "expected": {**_EXPECTED, Dimension.COESAO: impossible},
                    }
                )

    def test_word_limits_that_cannot_be_satisfied_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CalibrationFixture.model_validate(
                {**_fixture().model_dump(), "min_words": 300, "max_words": 250}
            )


def test_a_fixture_file_declaring_its_own_slug_is_rejected(tmp_path: pathlib.Path) -> None:
    from tests.calibration import harness

    path = tmp_path / "13-exemplo.json"
    path.write_text(json.dumps({"slug": "outro"}), encoding="utf-8")

    with pytest.raises(ValueError, match="the file name is the slug"):
        harness._parse(path)


def test_drift_reads_as_actual_minus_expected() -> None:
    drift = DimensionDrift(dimension=Dimension.PERSUASAO, expected=60, actual=45)

    assert drift.delta == -15
    assert drift.within(15) is True
    assert drift.within(14) is False


def test_calibration_marker_is_registered(pytestconfig: pytest.Config) -> None:
    """The engine suite must be opt-in, never blocking a normal PR."""
    markers = pytestconfig.getini("markers")

    assert any(marker.startswith("calibration") for marker in markers)


def _reference_run(wobble: tuple[str, int] | None = None) -> CalibrationResult:
    """An engine that agrees with the gabarito, optionally off by a few points
    on one fixture."""
    outcomes = []
    for fixture in load_fixtures():
        actual = dict(fixture.expected)
        if wobble is not None and fixture.slug == wobble[0]:
            actual = {dimension: score + wobble[1] for dimension, score in actual.items()}
        outcomes.append(compare(fixture, actual))
    return CalibrationResult(
        prompt_version="eval-v1.1",
        model="claude-sonnet-5",
        effort="high",
        outcomes=tuple(outcomes),
    )


def _inverted_discrimination() -> CalibrationResult:
    """Per dimension, the fixtures the gabarito puts on top come down by 14 and
    the ones at the bottom go up by 14: the mean is untouched by construction
    and every fixture stays inside its band."""
    fixtures = load_fixtures()
    actual: dict[str, dict[Dimension, int]] = {fixture.slug: {} for fixture in fixtures}
    for dimension in Dimension:
        annotated = [f for f in fixtures if dimension in f.expected]
        ranked = sorted(annotated, key=lambda f: f.expected[dimension])
        half = len(ranked) // 2
        for index, fixture in enumerate(ranked):
            shift = 14 if index < half else -14
            actual[fixture.slug][dimension] = fixture.expected[dimension] + shift
    return CalibrationResult(
        prompt_version="eval-v1.1",
        model="claude-sonnet-5",
        effort="high",
        outcomes=tuple(compare(fixture, actual[fixture.slug]) for fixture in fixtures),
    )
