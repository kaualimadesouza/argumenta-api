"""Issue #11: exam lenses (ENEM/FUVEST) and the boss essay, tests first (TDD)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Evaluation
from argumenta.domain.enums import ChapterKind, Dimension, Exam
from argumenta.domain.evaluation import (
    BASE_DIMENSIONS,
    DimensionScore,
    EvaluationRuler,
    ScoredDimension,
    decide_verdict,
)
from argumenta.domain.lenses import (
    LENS_VERSION,
    OFFICIAL_LENSES,
    project_lens,
    required_dimensions,
)
from tests.conftest import ScriptedEngine, submit_text

BOSS_TEXT = " ".join(["palavra"] * 300)

_SCORES = {
    Dimension.NORMA_CULTA: 90,
    Dimension.COESAO: 80,
    Dimension.COERENCIA: 70,
    Dimension.REPERTORIO: 60,
    Dimension.PERSUASAO: 50,
}


def _scored(**overrides: int) -> tuple[ScoredDimension, ...]:
    values = {**_SCORES, **{Dimension(k): v for k, v in overrides.items()}}
    return tuple(
        ScoredDimension(dimension=dimension, score=score, evidence="trecho", passed_floor=True)
        for dimension, score in values.items()
    )


class TestTheLensNeverMovesTheVerdict:
    """The point of the whole module: the exam changes what the student SEES,
    never whether the character was convinced."""

    def test_the_extra_boss_dimension_stays_out_of_the_verdict(self) -> None:
        five = tuple(
            DimensionScore(dimension=d, score=70, evidence="trecho") for d in BASE_DIMENSIONS
        )
        six = (
            *five,
            DimensionScore(dimension=Dimension.PROPOSTA_INTERVENCAO, score=10, evidence="fraca"),
        )
        ruler = EvaluationRuler(dimension_floor=40, min_average=50)

        without = decide_verdict(five, ruler)
        with_proposal = decide_verdict(six, ruler)

        assert (without.verdict, without.average_score) == (
            with_proposal.verdict,
            with_proposal.average_score,
        )

    def test_the_proposal_is_still_scored_and_checked_against_the_floor(self) -> None:
        scores = (
            *(DimensionScore(dimension=d, score=70, evidence="trecho") for d in BASE_DIMENSIONS),
            DimensionScore(dimension=Dimension.PROPOSTA_INTERVENCAO, score=10, evidence="fraca"),
        )

        decision = decide_verdict(scores, EvaluationRuler(dimension_floor=40, min_average=50))

        proposal = next(s for s in decision.scores if s.dimension == Dimension.PROPOSTA_INTERVENCAO)
        assert proposal.score == 10
        assert proposal.passed_floor is False


class TestLensMapping:
    """The mapping lives in code and is versioned next to the prompt."""

    @pytest.mark.parametrize("exam", list(Exam))
    @pytest.mark.parametrize("kind", list(ChapterKind))
    def test_what_the_engine_grades_is_exactly_what_the_lens_shows(
        self, exam: Exam, kind: ChapterKind
    ) -> None:
        lens = OFFICIAL_LENSES[exam]
        mapped = [d for criterion in lens.criteria_for(kind) for d in criterion.dimensions]

        assert len(mapped) == len(set(mapped)), "a dimension cannot be graded twice"
        assert set(mapped) == set(required_dimensions(kind, exam))

    def test_persuasion_is_an_argumenta_criterion_in_both_lenses(self) -> None:
        for lens in OFFICIAL_LENSES.values():
            extras = [c for c in lens.extra_criteria if Dimension.PERSUASAO in c.dimensions]
            assert len(extras) == 1


class TestEnemLens:
    def test_confronto_shows_four_competences_out_of_two_hundred(self) -> None:
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CONFRONTO)

        official = [c for c in view.criteria if not c.is_argumenta_extra]
        assert [c.code for c in official] == ["C1", "C2", "C3", "C4"]
        assert all(c.scale_max == 200 for c in official)
        assert view.version == LENS_VERSION
        assert view.exam == Exam.ENEM

    def test_competences_carry_the_documented_dimensions(self) -> None:
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CONFRONTO)
        by_code = {c.code: c.score for c in view.criteria}

        # C1 norma culta 90/100 -> 180/200; C4 coesao 80 -> 160
        assert by_code["C1"] == 180
        assert by_code["C4"] == 160
        # C3 coerencia 70 -> 140; C2 repertorio 60 -> 120
        assert by_code["C3"] == 140
        assert by_code["C2"] == 120

    def test_confronto_total_is_out_of_eight_hundred(self) -> None:
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CONFRONTO)

        assert view.total_max == 800
        assert view.total == 180 + 120 + 140 + 160

    def test_persuasion_is_shown_but_stays_out_of_the_official_total(self) -> None:
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CONFRONTO)

        extra = next(c for c in view.criteria if c.is_argumenta_extra)
        assert extra.score == 50
        assert extra.scale_max == 100
        assert view.total == 600

    def test_boss_chapter_grades_c5_out_of_one_thousand(self) -> None:
        scores = _scored(proposta_intervencao=100)

        view = project_lens(scores, Exam.ENEM, ChapterKind.CHEFE)

        by_code = {c.code: c.score for c in view.criteria}
        assert by_code["C5"] == 200
        assert view.total_max == 1000
        assert view.total == 600 + 200


class TestFuvestLens:
    def test_three_official_axes_with_the_documented_mapping(self) -> None:
        view = project_lens(_scored(), Exam.FUVEST, ChapterKind.CONFRONTO)

        official = [c for c in view.criteria if not c.is_argumenta_extra]
        assert [c.code for c in official] == ["E1", "E2", "E3"]
        # E1 desenvolvimento do tema <- repertorio 60
        # E2 estrutura do texto <- coesao 80 + coerencia 70
        # E3 expressao <- norma culta 90
        assert [c.score for c in official] == [60, 75, 90]

    def test_total_is_the_average_of_the_axes(self) -> None:
        view = project_lens(_scored(), Exam.FUVEST, ChapterKind.CONFRONTO)

        assert view.total_max == 100
        assert view.total == 75

    def test_boss_chapter_does_not_add_an_intervention_axis(self) -> None:
        view = project_lens(_scored(), Exam.FUVEST, ChapterKind.CHEFE)

        official = [c for c in view.criteria if not c.is_argumenta_extra]
        assert [c.code for c in official] == ["E1", "E2", "E3"]
        assert view.total_max == 100

    def test_the_total_matches_the_criteria_the_student_can_see(self) -> None:
        """A student who adds up the axes on screen must land on our total."""
        view = project_lens(_scored(coesao=80, coerencia=81), Exam.FUVEST, ChapterKind.CONFRONTO)

        official = [c for c in view.criteria if not c.is_argumenta_extra]
        assert view.total == round(sum(c.score for c in official) / len(official))

    def test_half_points_round_up_instead_of_to_even(self) -> None:
        """Bankers rounding on a student's grade is indefensible: 80.5 shown as
        80 in one axis and 82 in the next reads as a bug, because it is one."""
        low = project_lens(_scored(coesao=80, coerencia=81), Exam.FUVEST, ChapterKind.CONFRONTO)
        high = project_lens(_scored(coesao=82, coerencia=83), Exam.FUVEST, ChapterKind.CONFRONTO)

        assert next(c.score for c in low.criteria if c.code == "E2") == 81
        assert next(c.score for c in high.criteria if c.code == "E2") == 83


class TestTotalHonesty:
    """Only the ENEM boss essay has a real board total; everything else is our
    own aggregation and says so, so the client never renders it as official."""

    def test_enem_boss_total_comes_from_the_board(self) -> None:
        view = project_lens(_scored(proposta_intervencao=100), Exam.ENEM, ChapterKind.CHEFE)

        assert view.total_max == 1000
        assert view.scale_source == "board"

    def test_enem_confronto_total_is_ours_because_the_board_has_no_partial_scale(
        self,
    ) -> None:
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CONFRONTO)

        assert view.total_max == 800
        assert view.scale_source == "argumenta"

    def test_fuvest_total_is_ours_until_the_calibration_suite_settles_it(self) -> None:
        view = project_lens(_scored(), Exam.FUVEST, ChapterKind.CONFRONTO)

        assert view.scale_source == "argumenta"

    def test_a_criterion_without_scores_leaves_the_total_undefined(self) -> None:
        """Replaying an old five-dimension evaluation into the boss lens must
        not silently degrade 1000 into 800."""
        view = project_lens(_scored(), Exam.ENEM, ChapterKind.CHEFE)

        assert view.total is None
        assert [c.code for c in view.criteria if c.code == "C5"] == []


class TestRequiredDimensions:
    def test_confronto_asks_for_the_five_internal_dimensions(self) -> None:
        for exam in Exam:
            assert Dimension.PROPOSTA_INTERVENCAO not in required_dimensions(
                ChapterKind.CONFRONTO, exam
            )

    def test_enem_boss_also_asks_for_the_intervention_proposal(self) -> None:
        required = required_dimensions(ChapterKind.CHEFE, Exam.ENEM)

        assert Dimension.PROPOSTA_INTERVENCAO in required
        assert len(required) == 6

    def test_fuvest_boss_does_not_ask_for_an_intervention_proposal(self) -> None:
        required = required_dimensions(ChapterKind.CHEFE, Exam.FUVEST)

        assert Dimension.PROPOSTA_INTERVENCAO not in required
        assert len(required) == 5


class TestSubmissionLens:
    def test_submission_is_shown_in_the_enem_lens_by_default(
        self, game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, chapter_id = game

        body = submit_text(client, chapter_id).json()

        lens = body["lens"]
        assert lens["exam"] == "enem"
        assert lens["version"] == LENS_VERSION
        assert [c["code"] for c in lens["criteria"] if not c["is_argumenta_extra"]] == [
            "C1",
            "C2",
            "C3",
            "C4",
        ]
        assert lens["total_max"] == 800

    def test_the_same_evaluation_is_shown_in_the_active_lens(
        self, game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, chapter_id = game
        target = client.post("/me/targets", json={"exam": "fuvest", "year": 2027}).json()
        assert client.put(f"/me/targets/{target['id']}/activate").status_code == 204

        body = submit_text(client, chapter_id).json()

        internal = {s["dimension"]: s["score"] for s in body["scores"]}
        assert internal == dict.fromkeys(internal, 80), "internal scores stay untouched"
        assert body["lens"]["exam"] == "fuvest"
        assert [c["code"] for c in body["lens"]["criteria"] if not c["is_argumenta_extra"]] == [
            "E1",
            "E2",
            "E3",
        ]

    def test_the_lens_that_showed_the_correction_is_stored_with_it(
        self,
        game: tuple[TestClient, uuid.UUID],
        db_engine: Engine,
    ) -> None:
        """LENS_VERSION only means something if an old evaluation can be
        replayed into the mapping that produced it."""
        client, chapter_id = game

        submit_text(client, chapter_id)

        with Session(db_engine) as session:
            stored = session.scalars(select(Evaluation)).one()
        assert stored.lens_version == LENS_VERSION
        assert stored.exam == Exam.ENEM

    def test_boss_chapter_grades_the_intervention_proposal(
        self, boss_game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, boss_chapter_id = boss_game

        body = submit_text(client, boss_chapter_id, body=BOSS_TEXT).json()

        assert Dimension.PROPOSTA_INTERVENCAO in engine_double.calls[-1].required_dimensions
        dimensions = {s["dimension"] for s in body["scores"]}
        assert "proposta_intervencao" in dimensions
        assert body["lens"]["total_max"] == 1000
        assert any(c["code"] == "C5" for c in body["lens"]["criteria"])

    def test_boss_chapter_validates_its_own_word_limits(
        self, boss_game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, boss_chapter_id = boss_game

        # 130 words pass a confronto chapter and fail the boss (250 to 450)
        response = submit_text(client, boss_chapter_id)

        assert response.status_code == 422

    def test_engine_that_skips_the_required_proposal_is_rejected(
        self, boss_game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, boss_chapter_id = boss_game
        engine_double.ignore_required_dimensions = True

        response = submit_text(client, boss_chapter_id, body=BOSS_TEXT)

        assert response.status_code == 502
