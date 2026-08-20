"""Seed of the tutorial story "O Gremio" (PRD section 6, DER content domain).

Idempotent by slug: when the story already exists (not soft-deleted) nothing is
touched, so the seed is safe to run on every deploy.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Chapter, ChapterBeat, Character, Story
from argumenta.domain.enums import BeatType, Branch, ChapterKind, ContentStatus

STORY_SLUG = "o-gremio"


@dataclass(frozen=True)
class BeatSeed:
    branch: Branch
    beat_type: BeatType
    body: str
    character: str | None = None


@dataclass(frozen=True)
class ChapterSeed:
    kind: ChapterKind
    title: str
    objective: str
    antagonist: str
    min_words: int
    max_words: int
    evaluator_brief: str
    beats: tuple[BeatSeed, ...] = field(default_factory=tuple)


CHARACTERS: dict[str, str] = {
    "Dona Marta": (
        "Diretora ha vinte anos, pragmatica e avessa a risco; ja viu muito projeto "
        "de aluno morrer na praia. Respeita quem traz plano e dados, despreza apelo "
        "emocional vazio. Fala em frases curtas e cita fatos do ano passado."
    ),
    "Seu Tenorio": (
        "Zelador e chefe da manutencao, desconfiado e protetor do predio. Guarda "
        "magoa do festival passado: quebraram duas cadeiras e ninguem limpou o "
        "patio. Cede a quem demonstra responsabilidade concreta e verificavel."
    ),
    "Ana Flor": (
        "Presidente da associacao de pais, educada e firme. Fala em nome de pais "
        "preocupados com bagunca e distracao das provas; muda de ideia diante de "
        "argumento estruturado com contrapartidas claras."
    ),
}


def _c1_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Sexta-feira, 7h20. O aviso no mural ainda tem cheiro de impressora: "
            "\"FESTIVAL CULTURAL - CANCELADO\". Voce e presidente do gremio ha "
            "exatamente onze dias.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Se veio falar do festival, economize saliva. Ano passado foi reclamacao "
            "de barulho, patio imundo e tres pais na minha sala. Por que este ano "
            "seria diferente?",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para Dona Marta: por que o festival merece uma segunda chance, "
            "e como o gremio vai evitar os problemas do ano passado.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Reconheca os problemas do ano passado antes de prometer solucoes; a "
            "diretora nao confia em quem finge que nada aconteceu.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Dona Marta tira os oculos e devolve a sua carta pela metade da mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Bonito, mas e o mesmo discurso do ano passado. Palavra sem plano e "
            "papel. A decisao esta mantida.",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "No corredor, o vice do gremio te alcanca: \"Ela deixou uma brecha. "
            "Disse que se alguem trouxesse um plano de verdade, ela leria.\"",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Mesma sala, segunda-feira. Dona Marta aponta a cadeira e cruza os bracos.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Voce tem cinco minutos da minha manha. Desta vez, seja especifico: o "
            "que muda, quem faz e o que acontece se der errado.",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a proposta respondendo as tres perguntas dela: o que muda, "
            "quem se responsabiliza e qual o plano se algo falhar.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Estruture em causa e resposta: cada problema do ano passado ganha uma "
            "medida concreta com responsavel.",
        ),
    )


def _c2_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Dona Marta cedeu, com uma condicao: \"Se o Tenorio topar cuidar da "
            "estrutura, eu autorizo.\" O zelador esta consertando um portao e nem "
            "levanta os olhos quando voce chega.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Festival? To fora. Ano passado sumiu cadeira, pichacao no banheiro e "
            "adivinha quem varreu tudo sozinho no sabado? Escreve ai no seu "
            "papelzinho: o patio e meu.",
            character="Seu Tenorio",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para Seu Tenorio: por que ele pode confiar o patio ao gremio "
            "este ano, com compromissos concretos de cuidado e limpeza.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Comece pelo prejuizo dele, nao pelo seu evento; proponha compromissos "
            "que ele consiga fiscalizar.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Tenorio dobra o seu bilhete e usa para calcar a perna de uma mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Promessa de estudante dura ate a primeira prova. Sem garantia, sem patio.",
            character="Seu Tenorio",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "A merendeira, que ouviu tudo, cochicha: \"Ele amoleceu quando o pessoal "
            "do terceiro ano assinou termo de compromisso pela chave da quadra.\"",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Fim do expediente. Tenorio guarda as ferramentas e te da dois minutos, "
            "o tempo de lavar as maos.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Fala de novo. Mas agora eu quero saber quem assina, quem limpa e quem "
            "paga se quebrar.",
            character="Seu Tenorio",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Refaca a proposta com garantias verificaveis: nomes, escala de limpeza "
            "e o que o gremio banca em caso de dano.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Compromisso verificavel tem nome, data e consequencia; generosidade "
            "vaga nao conserta cadeira.",
        ),
    )


def _c3_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Auditorio cheio na reuniao da associacao de pais. Dona Marta e Seu "
            "Tenorio sentam na ultima fileira, do seu lado pela primeira vez.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Os pais respeitam o entusiasmo de voces. Mas estamos a dois meses das "
            "provas. Nos convenca, por escrito, de que o festival soma em vez de "
            "atrapalhar, ou a associacao vota contra.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva o texto final para a assembleia: defenda o festival, responda "
            "as preocupacoes dos pais e apresente como o gremio vai organiza-lo.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Nao ignore o argumento das provas: mostre como cultura e desempenho "
            "podem andar juntos, e feche com um encaminhamento concreto.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ana Flor le em silencio e passa o texto para a mesa. Um murmurio "
            "atravessa o auditorio.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Ha boas intencoes aqui, mas intencao nao organiza evento para "
            "quinhentos alunos. A associacao precisa de mais do que isso.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "A votacao e adiada em uma semana. Dona Marta segura o seu ombro: "
            "\"Voce chegou ate aqui. Termine bem.\"",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Reuniao extraordinaria. Desta vez, so a mesa diretora e voce.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Sem plateia agora. Reescreva o essencial: sua tese, suas razoes e o "
            "seu plano. E a ultima palavra do gremio.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a redacao final: tese clara, argumentos respondendo as "
            "objecoes e plano de organizacao como fecho.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Releia as objecoes: provas, custo e seguranca; cada uma merece "
            "resposta explicita no seu texto.",
        ),
    )


def _chapters() -> tuple[ChapterSeed, ...]:
    # word limits: confrontos 120-250, chefe 250-450 (PRD decisions 26 and issue #6)
    return (
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A porta da diretoria",
            objective=(
                "Convencer Dona Marta a reabrir a discussao do festival, mostrando o "
                "valor pedagogico do evento e como os riscos do cancelamento serao "
                "tratados."
            ),
            antagonist="Dona Marta",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viavel conecta o valor pedagogico do festival a um "
                "tratamento concreto dos riscos citados (barulho, limpeza, "
                "reclamacao de pais). Apelo emocional puro, ameaca de "
                "abaixo-assinado ou promessa vaga nao passam."
            ),
            beats=_c1_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="O patio do Tenorio",
            objective=(
                "Convencer Seu Tenorio a liberar o patio e apoiar a infraestrutura, "
                "assumindo compromissos de cuidado com o espaco."
            ),
            antagonist="Seu Tenorio",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viavel trata a magoa concreta do ano passado (dano e "
                "limpeza) com compromissos verificaveis: escala de limpeza, termo "
                "de responsabilidade, reposicao em caso de dano. Bajulacao ou "
                "apelo a autoridade da diretora nao passam."
            ),
            beats=_c2_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CHEFE,
            title="A assembleia",
            objective=(
                "Redacao final: texto dissertativo-argumentativo defendendo o "
                "festival cultural, respondendo as objecoes dos pais (provas, "
                "custo, seguranca) com proposta de organizacao."
            ),
            antagonist="Ana Flor",
            min_words=250,
            max_words=450,
            evaluator_brief=(
                "Texto completo com tese, argumentos desenvolvidos com repertorio, "
                "contra-argumentacao as objecoes dos pais e encaminhamento "
                "concreto de organizacao. Na lente ENEM, exige proposta de "
                "intervencao clara."
            ),
            beats=_c3_beats(),
        ),
    )


def seed_tutorial(session: Session) -> bool:
    """Insert the whole tutorial; returns False when it already exists."""
    existing = session.scalar(
        select(Story.id).where(Story.slug == STORY_SLUG, Story.deleted_at.is_(None))
    )
    if existing is not None:
        return False

    story = Story(
        slug=STORY_SLUG,
        title="O Gremio",
        synopsis=(
            "O festival cultural do colegio foi cancelado de ultima hora. Como novo "
            "presidente do gremio, voce vai ter que convencer, por escrito, cada "
            "pessoa que pode salvar o evento."
        ),
        position=1,
        is_tutorial=True,
        dimension_floor=40,
        min_average=50,
        status=ContentStatus.PUBLISHED,
    )
    session.add(story)
    session.flush()

    characters: dict[str, Character] = {}
    for name, persona in CHARACTERS.items():
        character = Character(story_id=story.id, name=name, persona_brief=persona)
        session.add(character)
        characters[name] = character
    session.flush()

    for position, chapter_seed in enumerate(_chapters(), start=1):
        chapter = Chapter(
            story_id=story.id,
            position=position,
            kind=chapter_seed.kind,
            title=chapter_seed.title,
            objective=chapter_seed.objective,
            antagonist_id=characters[chapter_seed.antagonist].id,
            min_words=chapter_seed.min_words,
            max_words=chapter_seed.max_words,
            evaluator_brief=chapter_seed.evaluator_brief,
        )
        session.add(chapter)
        session.flush()
        branch_positions: dict[Branch, int] = {}
        for beat in chapter_seed.beats:
            branch_positions[beat.branch] = branch_positions.get(beat.branch, 0) + 1
            session.add(
                ChapterBeat(
                    chapter_id=chapter.id,
                    branch=beat.branch,
                    position=branch_positions[beat.branch],
                    beat_type=beat.beat_type,
                    character_id=(
                        characters[beat.character].id if beat.character else None
                    ),
                    body=beat.body,
                )
            )
    session.flush()
    return True
