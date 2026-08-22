"""Seed of the tutorial story "O Grêmio" (PRD section 6, DER content domain)."""

from sqlalchemy.orm import Session

from argumenta.adapters.db.seed.story import (
    BeatSeed,
    ChapterSeed,
    StorySeed,
    insert_story,
)
from argumenta.domain.enums import BeatType, Branch, ChapterKind

STORY_SLUG = "o-gremio"

CHARACTERS: dict[str, str] = {
    "Dona Marta": (
        "Diretora há vinte anos, pragmática e avessa a risco; já viu muito projeto "
        "de aluno morrer na praia. Respeita quem traz plano e dados, despreza apelo "
        "emocional vazio. Fala em frases curtas e cita fatos do ano passado."
    ),
    "Seu Tenório": (
        "Zelador e chefe da manutenção, desconfiado e protetor do prédio. Guarda "
        "mágoa do festival passado: quebraram duas cadeiras e ninguém limpou o "
        "pátio. Cede a quem demonstra responsabilidade concreta e verificável."
    ),
    "Ana Flor": (
        "Presidente da associação de pais, educada e firme. Fala em nome de pais "
        "preocupados com bagunça e distração das provas; muda de ideia diante de "
        "argumento estruturado com contrapartidas claras."
    ),
}


def _c1_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Sexta-feira, 7h20. O aviso no mural ainda tem cheiro de impressora: "
            '"FESTIVAL CULTURAL, CANCELADO". Você é presidente do grêmio há '
            "exatamente onze dias.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Se veio falar do festival, economize saliva. Ano passado foi reclamação "
            "de barulho, pátio imundo e três pais na minha sala. Por que este ano "
            "seria diferente?",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para Dona Marta: por que o festival merece uma segunda chance, "
            "e como o grêmio vai evitar os problemas do ano passado.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Reconheça os problemas do ano passado antes de prometer soluções; a "
            "diretora não confia em quem finge que nada aconteceu.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Dona Marta tira os óculos e devolve a sua carta pela metade da mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Bonito, mas é o mesmo discurso do ano passado. Palavra sem plano é "
            "papel. A decisão está mantida.",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'No corredor, o vice do grêmio te alcança: "Ela deixou uma brecha. '
            'Disse que se alguém trouxesse um plano de verdade, ela leria."',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Mesma sala, segunda-feira. Dona Marta aponta a cadeira e cruza os braços.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Você tem cinco minutos da minha manhã. Desta vez, seja específico: o "
            "que muda, quem faz e o que acontece se der errado.",
            character="Dona Marta",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a proposta respondendo às três perguntas dela: o que muda, "
            "quem se responsabiliza e qual o plano se algo falhar.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Estruture em causa e resposta: cada problema do ano passado ganha uma "
            "medida concreta com responsável.",
        ),
    )


def _c2_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            'Dona Marta cedeu, com uma condição: "Se o Tenório topar cuidar da '
            'estrutura, eu autorizo." O zelador está consertando um portão e nem '
            "levanta os olhos quando você chega.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Festival? Tô fora. Ano passado sumiu cadeira, pichação no banheiro e "
            "adivinha quem varreu tudo sozinho no sábado? Escreve aí no seu "
            "papelzinho: o pátio é meu.",
            character="Seu Tenório",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para Seu Tenório: por que ele pode confiar o pátio ao grêmio "
            "este ano, com compromissos concretos de cuidado e limpeza.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Comece pelo prejuízo dele, não pelo seu evento; proponha compromissos "
            "que ele consiga fiscalizar.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Tenório dobra o seu bilhete e usa para calçar a perna de uma mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Promessa de estudante dura até a primeira prova. Sem garantia, sem pátio.",
            character="Seu Tenório",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'A merendeira, que ouviu tudo, cochicha: "Ele amoleceu quando o pessoal '
            'do terceiro ano assinou termo de compromisso pela chave da quadra."',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Fim do expediente. Tenório guarda as ferramentas e te dá dois minutos, "
            "o tempo de lavar as mãos.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Fala de novo. Mas agora eu quero saber quem assina, quem limpa e quem "
            "paga se quebrar.",
            character="Seu Tenório",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Refaça a proposta com garantias verificáveis: nomes, escala de limpeza "
            "e o que o grêmio banca em caso de dano.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Compromisso verificável tem nome, data e consequência; generosidade "
            "vaga não conserta cadeira.",
        ),
    )


def _c3_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Auditório cheio na reunião da associação de pais. Dona Marta e Seu "
            "Tenório sentam na última fileira, do seu lado pela primeira vez.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Os pais respeitam o entusiasmo de vocês. Mas estamos a dois meses das "
            "provas. Nos convença, por escrito, de que o festival soma em vez de "
            "atrapalhar, ou a associação vota contra.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva o texto final para a assembleia: defenda o festival, responda "
            "às preocupações dos pais e apresente como o grêmio vai organizá-lo.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Não ignore o argumento das provas: mostre como cultura e desempenho "
            "podem andar juntos, e feche com um encaminhamento concreto.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ana Flor lê em silêncio e passa o texto para a mesa. Um murmúrio "
            "atravessa o auditório.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Há boas intenções aqui, mas intenção não organiza evento para "
            "quinhentos alunos. A associação precisa de mais do que isso.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "A votação é adiada em uma semana. Dona Marta segura o seu ombro: "
            '"Você chegou até aqui. Termine bem."',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Reunião extraordinária. Desta vez, só a mesa diretora e você.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Sem plateia agora. Reescreva o essencial: sua tese, suas razões e o "
            "seu plano. É a última palavra do grêmio.",
            character="Ana Flor",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a redação final: tese clara, argumentos respondendo às "
            "objeções e plano de organização como fecho.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Releia as objeções: provas, custo e segurança; cada uma merece "
            "resposta explícita no seu texto.",
        ),
    )


def _chapters() -> tuple[ChapterSeed, ...]:
    # word limits: confrontos 120-250, chefe 250-450 (PRD decisions 26 and issue #6)
    return (
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A porta da diretoria",
            objective=(
                "Convencer Dona Marta a reabrir a discussão do festival, mostrando o "
                "valor pedagógico do evento e como os riscos do cancelamento serão "
                "tratados."
            ),
            antagonist="Dona Marta",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável conecta o valor pedagógico do festival a um "
                "tratamento concreto dos riscos citados (barulho, limpeza, "
                "reclamação de pais). Apelo emocional puro, ameaça de "
                "abaixo-assinado ou promessa vaga não passam."
            ),
            beats=_c1_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="O pátio do Tenório",
            objective=(
                "Convencer Seu Tenório a liberar o pátio e apoiar a infraestrutura, "
                "assumindo compromissos de cuidado com o espaço."
            ),
            antagonist="Seu Tenório",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável trata a mágoa concreta do ano passado (dano e "
                "limpeza) com compromissos verificáveis: escala de limpeza, termo "
                "de responsabilidade, reposição em caso de dano. Bajulação ou "
                "apelo à autoridade da diretora não passam."
            ),
            beats=_c2_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CHEFE,
            title="A assembleia",
            objective=(
                "Redação final: texto dissertativo-argumentativo defendendo o "
                "festival cultural, respondendo às objeções dos pais (provas, "
                "custo, segurança) com proposta de organização."
            ),
            antagonist="Ana Flor",
            min_words=250,
            max_words=450,
            evaluator_brief=(
                "Texto completo com tese, argumentos desenvolvidos com repertório, "
                "contra-argumentação às objeções dos pais e encaminhamento "
                "concreto de organização. Na lente ENEM, exige proposta de "
                "intervenção clara."
            ),
            beats=_c3_beats(),
        ),
    )


def seed_tutorial(session: Session) -> bool:
    """Insert the whole tutorial; returns False when it already exists."""
    return insert_story(
        session,
        StorySeed(
            slug=STORY_SLUG,
            title="O Grêmio",
            synopsis=(
                "O festival cultural do colégio foi cancelado de última hora. Como novo "
                "presidente do grêmio, você vai ter que convencer, por escrito, cada "
                "pessoa que pode salvar o evento."
            ),
            position=1,
            is_tutorial=True,
            dimension_floor=40,
            min_average=50,
            characters=CHARACTERS,
            chapters=_chapters(),
        ),
    )
