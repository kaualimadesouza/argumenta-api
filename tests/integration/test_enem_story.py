"""Issue #15: a história ENEM "Cuidado Invisível" completa e jogável. Conteúdo
é dado, então o que se testa é a forma: todo capítulo com os três ramos, réguas
do card, e a trilha inteira jogável depois do seed."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session
from tests.integration.conftest import REGISTER, ScriptedEngine, submit_text

from argumenta.adapters.db.models import (
    Chapter,
    ChapterBeat,
    Character,
    DailyActivity,
    Story,
    Theme,
)
from argumenta.adapters.db.seed.enem_care import STORY_SLUG, seed_enem_care
from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.domain.enums import BeatType, Branch, ChapterKind, Exam
from argumenta.presentation.fastapi.dependencies import get_evaluation_engine


@pytest.fixture
def seeded(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        seed_tutorial(session)
        seed_enem_care(session)
        session.commit()


def _story(session: Session) -> Story:
    story = session.scalar(select(Story).where(Story.slug == STORY_SLUG))
    assert story is not None
    return story


class TestStoryShape:
    def test_the_seed_is_idempotent(self, db_engine: Engine) -> None:
        """Roda em todo deploy: a segunda vez não pode duplicar nem estourar o
        único parcial de slug e de posição."""
        with Session(db_engine) as session:
            assert seed_enem_care(session) is True
            assert seed_enem_care(session) is False
            session.commit()

        with Session(db_engine) as session:
            assert len(session.scalars(select(Story)).all()) == 1
            assert len(session.scalars(select(Theme)).all()) == 1

    def test_the_story_carries_the_real_exam_theme(self, seeded: None, db_engine: Engine) -> None:
        with Session(db_engine) as session:
            story = _story(session)
            theme = session.get(Theme, story.theme_id)

        assert theme is not None
        assert (theme.exam, theme.year) == (Exam.ENEM, 2023)
        assert "trabalho de cuidado" in theme.title
        assert "proposta de intervenção" in theme.statement

    def test_the_story_sits_after_the_tutorial_with_its_own_ruler(
        self, seeded: None, db_engine: Engine
    ) -> None:
        """Régua do card #15: piso 50 por dimensão, média mínima 60."""
        with Session(db_engine) as session:
            story = _story(session)

        assert (story.position, story.is_tutorial) == (2, False)
        assert (story.dimension_floor, story.min_average) == (50, 60)

    def test_five_chapters_four_confrontos_and_a_boss(
        self, seeded: None, db_engine: Engine
    ) -> None:
        chapters = _chapters(db_engine)

        assert [chapter.position for chapter in chapters] == [1, 2, 3, 4, 5]
        assert [chapter.kind for chapter in chapters] == [ChapterKind.CONFRONTO] * 4 + [
            ChapterKind.CHEFE
        ]

    def test_every_chapter_has_all_three_branches_and_a_brief(
        self, seeded: None, db_engine: Engine
    ) -> None:
        """Sem o ramo de consequência não existe cena de derrota, e sem o de
        recuperação o aluno fica preso no capítulo."""
        with Session(db_engine) as session:
            for chapter in _chapters(db_engine):
                beats = session.scalars(
                    select(ChapterBeat).where(ChapterBeat.chapter_id == chapter.id)
                ).all()
                branches = {beat.branch for beat in beats}
                assert branches == set(Branch), f"{chapter.title}: {sorted(branches)}"
                assert len(chapter.evaluator_brief) > 80, chapter.title
                for branch in Branch:
                    positions = [beat.position for beat in beats if beat.branch == branch]
                    assert positions == list(range(1, len(positions) + 1)), chapter.title

    def test_every_branch_tells_the_student_what_to_write(
        self, seeded: None, db_engine: Engine
    ) -> None:
        """Objetivo em main e em recovery, porque são os dois ramos em que o
        aluno escreve; consequência é cena, não pedido."""
        with Session(db_engine) as session:
            for chapter in _chapters(db_engine):
                beats = session.scalars(
                    select(ChapterBeat).where(ChapterBeat.chapter_id == chapter.id)
                ).all()
                for branch in (Branch.MAIN, Branch.RECOVERY):
                    types = {b.beat_type for b in beats if b.branch == branch}
                    assert BeatType.OBJECTIVE in types, f"{chapter.title}/{branch}"
                    assert BeatType.HINT in types, f"{chapter.title}/{branch}"
                consequence = [b for b in beats if b.branch == Branch.CONSEQUENCE]
                assert any(b.beat_type == BeatType.DIALOGUE for b in consequence), chapter.title

    def test_the_boss_asks_for_a_dissertation(self, seeded: None, db_engine: Engine) -> None:
        boss = _chapters(db_engine)[-1]

        assert (boss.min_words, boss.max_words) == (250, 450)
        assert "dissertativo-argumentativo" in boss.objective

    def test_the_confrontos_use_the_card_word_limits(self, seeded: None, db_engine: Engine) -> None:
        for chapter in _chapters(db_engine)[:-1]:
            assert (chapter.min_words, chapter.max_words) == (120, 250), chapter.title

    def test_every_dialogue_has_a_voice_and_every_character_a_persona(
        self, seeded: None, db_engine: Engine
    ) -> None:
        """A fala sem personagem não tem quem a diga na cena, e a persona vazia
        deixa o motor de reação sem voz para imitar."""
        with Session(db_engine) as session:
            story = _story(session)
            characters = session.scalars(
                select(Character).where(Character.story_id == story.id)
            ).all()
            chapter_ids = [chapter.id for chapter in _chapters(db_engine)]
            beats = session.scalars(
                select(ChapterBeat).where(ChapterBeat.chapter_id.in_(chapter_ids))
            ).all()

        assert len(characters) == 5
        assert all(len(character.persona_brief) > 80 for character in characters)
        for beat in beats:
            if beat.beat_type == BeatType.DIALOGUE:
                assert beat.character_id is not None, beat.body[:40]
            else:
                assert beat.character_id is None, beat.body[:40]

    def test_the_second_chapter_speaks_the_lines_from_the_mockups(
        self, seeded: None, db_engine: Engine
    ) -> None:
        """A arte do argumenta-web já desenhou esse capítulo: se o texto do seed
        divergir, a tela mostra uma cena e o banco tem outra."""
        chapter = _chapters(db_engine)[1]
        with Session(db_engine) as session:
            bodies = [
                beat.body
                for beat in session.scalars(
                    select(ChapterBeat)
                    .where(ChapterBeat.chapter_id == chapter.id, ChapterBeat.branch == Branch.MAIN)
                    .order_by(ChapterBeat.position)
                ).all()
            ]

        assert bodies[0].startswith("Domingo à noite. A pia ainda cheia, a vó já dormindo.")
        assert bodies[1].startswith("Sua mãe reclama, mas cuidar da vó nem é trabalho de verdade.")
        assert chapter.objective.startswith("Convencer o tio Marcos")


class TestPlayable:
    def test_the_track_offers_the_story_after_the_tutorial(
        self, seeded: None, client: TestClient
    ) -> None:
        assert client.post("/auth/register", json=REGISTER).status_code == 201

        track = client.get("/track").json()

        stories = {story["slug"]: story for story in track["stories"]}
        assert list(stories) == ["o-gremio", "cuidado-invisivel"]
        assert stories["cuidado-invisivel"]["state"] == "locked"
        assert stories["cuidado-invisivel"]["chapters_total"] == 5

    def test_the_whole_story_can_be_played_to_the_end(
        self,
        seeded: None,
        app: object,
        client: TestClient,
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        """De ponta a ponta: o tutorial, os quatro confrontos e a redação-chefe,
        cada capítulo aberto pela trilha e aprovado pelo motor."""
        app.dependency_overrides[get_evaluation_engine] = lambda: engine_double  # type: ignore[attr-defined]
        assert client.post("/auth/register", json=REGISTER).status_code == 201
        titles: list[str] = []

        for _ in range(8):
            chapter_id = _next_chapter(client, db_engine)
            if chapter_id is None:
                break
            titles.append(_play(client, db_engine, chapter_id))

        assert len(titles) == 8, titles
        assert titles[3:] == [
            "O almoço de domingo",
            "A cozinha às dez da noite",
            "A régua da vó",
            "Cinco horas de sono",
            "A sala do CRAS",
        ]
        track = client.get("/track").json()
        assert [story["state"] for story in track["stories"]] == ["completed", "completed"]


def _chapters(db_engine: Engine) -> list[Chapter]:
    with Session(db_engine) as session:
        story = _story(session)
        return list(
            session.scalars(
                select(Chapter).where(Chapter.story_id == story.id).order_by(Chapter.position)
            ).all()
        )


def _next_chapter(client: TestClient, db_engine: Engine) -> uuid.UUID | None:
    """A trilha materializa o próximo desbloqueio; o teste segue o que ela abriu."""
    assert client.get("/track").status_code == 200
    with Session(db_engine) as session:
        return session.scalar(
            select(Chapter.id)
            .join(Story, Story.id == Chapter.story_id)
            .where(Chapter.id.notin_(_passed(session)))
            .order_by(Story.position, Chapter.position)
        )


def _passed(session: Session) -> list[uuid.UUID]:
    from argumenta.adapters.db.models import ChapterProgress
    from argumenta.domain.enums import ChapterStatus

    return list(
        session.scalars(
            select(ChapterProgress.chapter_id).where(ChapterProgress.status == ChapterStatus.PASSED)
        ).all()
    )


def _play(client: TestClient, db_engine: Engine, chapter_id: uuid.UUID) -> str:
    """Um envio aprovado por capítulo, zerando o contador diário entre eles: o
    limite de 3 por dia é regra de hábito, testada em test_submissions."""
    with Session(db_engine) as session:
        session.execute(delete(DailyActivity))
        session.commit()
    chapter = client.get(f"/chapters/{chapter_id}")
    assert chapter.status_code == 200, chapter.text
    scene = chapter.json()
    body = " ".join(["palavra"] * (scene["min_words"] + 10))
    response = submit_text(client, chapter_id, body)
    assert response.status_code == 201, response.text
    assert response.json()["verdict"] == "approved"
    return str(scene["title"])
