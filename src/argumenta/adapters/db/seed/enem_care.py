"""História ENEM "Cuidado Invisível" (tema real de 2023, trabalho de cuidado).
Segunda história da trilha; o capítulo 2 é o desenhado nos mockups do
argumenta-web, e as falas dele são as mesmas da arte."""

from sqlalchemy.orm import Session

from argumenta.adapters.db.seed.story import (
    BeatSeed,
    ChapterSeed,
    StorySeed,
    ThemeSeed,
    insert_story,
)
from argumenta.domain.enums import BeatType, Branch, ChapterKind, Exam

STORY_SLUG = "cuidado-invisivel"

THEME = ThemeSeed(
    exam=Exam.ENEM,
    year=2023,
    title=(
        "Desafios para o enfrentamento da invisibilidade do trabalho de cuidado "
        "realizado pela mulher no Brasil"
    ),
    statement=(
        "No Brasil, cuidar de crianças, de idosos e de pessoas com deficiência é "
        "trabalho feito quase sempre por mulheres, dentro de casa, sem contrato, sem "
        "salário e sem aparecer nas contas do país. Escreva um texto "
        "dissertativo-argumentativo, em norma culta, sobre os desafios para tornar "
        "esse trabalho visível e reconhecido, apresentando proposta de intervenção "
        "que respeite os direitos humanos."
    ),
)

CHARACTERS: dict[str, str] = {
    "Tia Bete": (
        "Irmã da sua mãe, afetuosa e evasiva. Aparece no almoço de domingo e diz que "
        "ajuda quando dá. Elogia a irmã para não se comprometer e desvia com a própria "
        "correria; aceita compromisso pequeno, datado e com nome."
    ),
    "Tio Marcos": (
        "Irmão da sua mãe, sai às seis e volta às oito. Para ele, trabalho é o que tem "
        "contracheque, e cuidar da mãe é obrigação natural de mulher. Oferece dinheiro "
        "para não oferecer tempo; só se move diante de critério e de dado verificável."
    ),
    "Dona Cida": (
        "Sua avó, costureira aposentada, orgulhosa e irônica. Recusa pena e recusa "
        "virar turno de escala. Fala pouco e certeiro; cede ao que preserva a rotina e "
        "as decisões dela, nunca ao que a trata como assunto de reunião."
    ),
    "Rosana": (
        "Sua mãe. Faz tudo, dorme cinco horas e acredita que ninguém acerta o horário "
        "do remédio. Cansada e defensiva, confunde dividir com abandonar; se move pelo "
        "risco para a avó, não pelo próprio descanso."
    ),
    "Dra. Neusa": (
        "Assistente social do CRAS, ouviu centenas de famílias e não se comove com "
        "depoimento. Corta generalização e frase feita; pede texto que se sustente "
        "sozinho, com tese, repertório explicado e proposta que caiba no orçamento."
    ),
}


def _c1_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Domingo, uma da tarde. A mesa está posta para nove pessoas. Sua mãe "
            "serve todos os pratos e come de pé, encostada na pia, com a vó já "
            "chamando da sala.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Sua mãe é um anjo, sabia? Eu ajudo quando dá. Você sabe como é a minha "
            "correria, meu amor.",
            character="Tia Bete",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para a tia Bete: por que ajudar quando dá não sustenta a rotina "
            "da vó, e o que exatamente você está pedindo dela.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Ajuda sem dia marcado não entra na conta de ninguém. Peça pouco, mas "
            "peça específico: dia, horário e tarefa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Bete lê o seu texto no meio do almoço, dá um beijo na sua testa e guarda "
            "o papel na bolsa junto com o comprovante da farmácia.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Que texto bonito, viu? Vou ver o que eu consigo fazer, prometo.",
            character="Tia Bete",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'Na porta, ela para com a chave na mão: "se você me disser exatamente o '
            'que precisa, eu olho na minha agenda hoje à noite".',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Quarta-feira, 20h. O grupo da família está em silêncio desde domingo, e "
            "sua mãe faltou ao trabalho outra vez.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Então me diz: qual dia, que horas, e o que eu faço quando chegar lá?",
            character="Tia Bete",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva o pedido respondendo às três perguntas dela: qual dia, qual "
            "horário e o que ela assume enquanto estiver lá.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Compromisso pequeno e datado vale mais que um grande e vago. Diga "
            "também o que acontece se ela não puder ir.",
        ),
    )


def _c2_beats() -> tuple[BeatSeed, ...]:
    """Capítulo desenhado nos mockups: narração, fala e objetivo são os da arte."""
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Domingo à noite. A pia ainda cheia, a vó já dormindo. Sua mãe apaga a "
            "luz da cozinha com o rosto fechado de quem repete aquilo há meses.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Sua mãe reclama, mas cuidar da vó nem é trabalho de verdade. Trabalho é "
            "o que eu faço: sair de casa às seis e voltar às oito.",
            character="Tio Marcos",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Convencer o tio Marcos de que o cuidado com a vó é trabalho de verdade, "
            "e que precisa ser dividido.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Existe nome para isso: economia do cuidado. Procure um dado de horas "
            "semanais em trabalho não remunerado no Brasil e explique o dado.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Segunda-feira, 6h. O tio Marcos saiu sem falar com ninguém. Na mesa, um "
            'bilhete: "cada um cuida da sua parte". Sua mãe lê, dobra o papel em '
            "silêncio e liga para o trabalho. Vai faltar de novo.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Recebi o seu texto. Se cuidar é trabalho, me diz quanto custa e quem "
            "paga. Aí a gente conversa.",
            character="Tio Marcos",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'Sua mãe, da porta do quarto, sem olhar para você: "ele nunca respondeu '
            'nada de ninguém. Escreve de novo".',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Terça, 21h. Marcos aparece com a chave do carro na mão e não senta. "
            "Fica em pé, encostado na porta da cozinha.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Tenho quinze minutos. Me mostra a conta: quantas horas, quanto isso "
            "valeria pago, e qual é a minha parte.",
            character="Tio Marcos",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva o argumento com a conta na frente: as horas de cuidado da "
            "semana, o que elas valeriam se fossem pagas, e a parte que cabe a ele.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Ele aceita critério, não indignação. Tempo, esforço e valor: uma linha "
            'de dado bem explicada derruba o "sempre foi assim".',
        ),
    )


def _c3_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Você chega com a escala impressa e apoia na mesa da máquina de costura. "
            "Dona Cida olha o papel de longe, como quem já viu essa cena antes.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Escala é coisa de fábrica. Eu criei cinco filhos sem escala nenhuma e "
            "não vou virar turno de ninguém agora.",
            character="Dona Cida",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para a vó: por que o plano não é pena nem perda de autonomia, e "
            "o que continua sendo decisão dela dentro dele.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Ela recusa ser objeto do plano. Dê decisões a ela: horário, quem entra "
            "no quarto, o que ela segue fazendo sozinha.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ela dobra a sua folha em quatro e usa o papel para calçar o pé da mesa "
            "da máquina de costura.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Você escreveu bonito, mas escreveu sobre mim, não comigo. Não gosto de "
            "ser assunto de reunião.",
            character="Dona Cida",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'Antes de você sair, ela desliga a máquina: "a Rosana está acabada, isso '
            'eu sei melhor que você. Escreve outra vez, e me pergunta alguma coisa".',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Sábado de manhã. A sala cheia de luz, a máquina ligada, dois cafés na "
            "bandeja: um para ela, um para você.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Senta. Dessa vez me diz o que eu ganho, o que eu perco, e o que continua sendo meu.",
            character="Dona Cida",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva o texto respondendo às três perguntas dela, deixando explícito "
            "o que segue sob o controle dela.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "A autonomia dela é o seu argumento, não o obstáculo: mostre que o plano "
            "existe para ela decidir mais, não menos.",
        ),
    )


def _c4_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Duas da manhã. A luz da cozinha acesa outra vez, sua mãe conferindo a "
            "caixinha de remédios com o dedo tremendo de sono.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Deixa que eu faço. Ninguém dá o remédio na hora, ninguém lembra que ela "
            "não come com sal. Quando eu solto, dá errado.",
            character="Rosana",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para a sua mãe: por que dividir o cuidado protege a vó, e como o "
            "plano evita justamente o erro que ela teme.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Ela não se move por si, se move pela vó. E o risco que ela aponta é "
            'real: responda com combinado escrito, não com "vai dar certo".',
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ela lê em pé, ainda de uniforme, e guarda o papel dobrado no bolso do "
            "avental sem dizer nada.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Você quer me tirar de perto dela. Já ouvi isso da assistente social e "
            "não gostei de ouvir.",
            character="Rosana",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'Mais tarde, no corredor, você escuta ela no telefone: "se der errado uma '
            'vez, a culpa vai ser minha, não deles".',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Domingo, seis da tarde. Ela senta na sua frente com a caixinha de "
            "remédios na mão e o caderno de receitas aberto.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Me convence com o que eu perguntei: quem dá o remédio, quem anota, e o "
            "que acontece quando alguém errar.",
            character="Rosana",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva o texto com o combinado explícito: quem faz cada tarefa, onde "
            "fica registrado e o que acontece quando alguém falha.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Dividir não é abandonar. Mostre o registro (caderno, alarme, grupo) que "
            "entra no lugar da memória dela.",
        ),
    )


def _c5_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Quinta, 14h. A sala do CRAS tem duas cadeiras, um ventilador de mesa e "
            "uma pilha de pastas com nomes de outras famílias.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "A sua família eu já conheço. Amanhã eu apresento à comissão do orçamento "
            "participativo, e lá ninguém conhece a sua avó. Escreva o texto que vai "
            "sozinho.",
            character="Dra. Neusa",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva um texto dissertativo-argumentativo sobre os desafios para o "
            "enfrentamento da invisibilidade do trabalho de cuidado realizado pela "
            "mulher no Brasil, com proposta de intervenção.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "A sua avó é exemplo, não é o tema. A tese precisa valer para as outras "
            "pastas em cima daquela mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Neusa marca duas linhas do seu texto com a caneta vermelha e empurra a "
            "folha de volta pela mesa.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Isso é depoimento, não é argumento. Comissão não decide por comoção: "
            "decide por problema, causa e proposta que caiba no orçamento.",
            character="Dra. Neusa",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            'Ela olha o relógio na parede: "a reunião é amanhã às nove. Se você '
            'reescrever hoje, eu levo".',
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Vinte e três horas, cozinha silenciosa. O caderno da escala da família "
            "aberto ao lado do caderno de redação.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Uma folha, texto fechado: tese, dois argumentos com repertório, e "
            "proposta com agente, ação e meio. É isso que a comissão lê.",
            character="Dra. Neusa",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a redação final: tese sobre a invisibilidade do trabalho de "
            "cuidado, dois argumentos sustentados por repertório e proposta de "
            "intervenção completa.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Proposta completa responde quem faz, o que faz, como faz e para quê. E "
            "repertório precisa estar explicado, não apenas citado.",
        ),
    )


def _chapters() -> tuple[ChapterSeed, ...]:
    # confrontos 120-250 palavras, chefe 250-450 (decisões do card #15)
    return (
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="O almoço de domingo",
            objective=(
                "Convencer a tia Bete a assumir um dia fixo de cuidado, transformando "
                "boa vontade difusa em compromisso com data e tarefa."
            ),
            antagonist="Tia Bete",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável transforma disposição vaga em compromisso "
                "verificável: dia, horário, tarefa e o que acontece se ela faltar. "
                "Elogiar a mãe, cobrar culpa ou pedir ajuda genérica não passa."
            ),
            beats=_c1_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A cozinha às dez da noite",
            objective=(
                "Convencer o tio Marcos de que o cuidado com a vó é trabalho de "
                "verdade, e que precisa ser dividido."
            ),
            antagonist="Tio Marcos",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável define cuidado como trabalho por critério concreto "
                "(tempo, esforço, valor econômico), de preferência com um dado "
                "explicado, e converte isso em parte da rotina que cabe a ele. "
                "Comparar sofrimento, moralizar ou ameaçar não passa."
            ),
            beats=_c2_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A régua da vó",
            objective=(
                "Convencer Dona Cida a aceitar o plano de cuidado sem se sentir "
                "tutelada, deixando claro o que continua sob decisão dela."
            ),
            antagonist="Dona Cida",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável separa cuidado de tutela: preserva rotina e "
                "decisões da avó, nomeia o que muda e o que continua sendo dela. "
                "Pena, infantilização ou argumentar só pelo bem da mãe não passa."
            ),
            beats=_c3_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="Cinco horas de sono",
            objective=(
                "Convencer Rosana a dividir o cuidado, respondendo ao risco concreto "
                "que ela teme com um combinado registrado."
            ),
            antagonist="Rosana",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável responde ao risco concreto com combinado "
                "verificável (registro, quem faz o quê, o que acontece na falha) e "
                "separa dividir de abandonar. Elogiar o sacrifício dela ou pedir que "
                "ela descanse não passa."
            ),
            beats=_c4_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CHEFE,
            title="A sala do CRAS",
            objective=(
                "Redação final: texto dissertativo-argumentativo sobre os desafios "
                "para o enfrentamento da invisibilidade do trabalho de cuidado "
                "realizado pela mulher no Brasil, com proposta de intervenção."
            ),
            antagonist="Dra. Neusa",
            min_words=250,
            max_words=450,
            evaluator_brief=(
                "Texto completo: tese sobre a invisibilidade do trabalho de cuidado, "
                "argumentos sustentados por repertório legítimo e explicado (dado, "
                "lei, conceito) e proposta de intervenção com agente, ação, meio e "
                "finalidade. Depoimento familiar sozinho, ou proposta sem agente e "
                "sem meio, não passa."
            ),
            beats=_c5_beats(),
        ),
    )


def seed_enem_care(session: Session) -> bool:
    """Insert the ENEM story; returns False when it already exists."""
    return insert_story(
        session,
        StorySeed(
            slug=STORY_SLUG,
            title="Cuidado Invisível",
            synopsis=(
                "A sua avó precisa de cuidado todos os dias, e quem cuida é sempre a "
                "sua mãe. Para mudar isso você vai ter que convencer, por escrito, "
                "cada pessoa da família, e depois a comissão que decide o orçamento."
            ),
            position=2,
            dimension_floor=50,
            min_average=60,
            characters=CHARACTERS,
            chapters=_chapters(),
            theme=THEME,
        ),
    )
