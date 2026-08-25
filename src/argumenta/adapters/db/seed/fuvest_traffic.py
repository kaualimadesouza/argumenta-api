"""História FUVEST "Sinal Fechado" (tema real de 2021)."""

from sqlalchemy.orm import Session

from argumenta.adapters.db.seed.story import (
    BeatSeed,
    ChapterSeed,
    StorySeed,
    ThemeSeed,
    insert_story,
)
from argumenta.domain.enums import BeatType, Branch, ChapterKind, Exam

STORY_SLUG = "sinal-fechado"

THEME = ThemeSeed(
    exam=Exam.FUVEST,
    year=2021,
    title="O mundo contemporâneo está fora de ordem?",
    statement=(
        "Com base na leitura dos textos de apoio e nos seus próprios conhecimentos, "
        "escreva um texto dissertativo-argumentativo, em norma culta, sobre o tema: "
        "O mundo contemporâneo está fora de ordem?"
    ),
)

CHARACTERS: dict[str, str] = {
    "Luciana": (
        "Uma executiva apressada que divide o táxi com você. Acredita que o mundo está "
        "exatamente como deveria ser: uma máquina eficiente que premia quem corre e "
        "pune quem para. Não tem paciência para filosofias sobre 'ordem' ou 'caos'."
    ),
    "Roberto": (
        "O motorista do aplicativo. Nostálgico, acha que no passado as coisas faziam "
        "sentido e as pessoas se respeitavam. Acredita que o mundo atual é uma "
        "bagunça irreversível porque abandonou valores antigos."
    ),
    "Sargento Moura": (
        "O guarda de trânsito tentando desatar o nó no cruzamento. Para ele, o caos "
        "é só falta de punição. Acredita que qualquer desordem se resolve com mais "
        "regras e autoridade."
    ),
    "Jonas": (
        "O vendedor de água no semáforo. Sobrevive à margem de tudo. Para ele, a "
        "ordem que os outros defendem sempre foi uma ilusão feita para manter quem "
        "já tem dinheiro no poder. Ele vê o caos não como uma crise, mas como a "
        "regra do jogo."
    ),
    "Prof. Carlos": (
        "O professor da banca avaliadora. Exige uma análise sociológica profunda. "
        "Não aceita lamentações saudosistas nem otimismo cego; quer uma tese que "
        "explique de onde vem essa sensação de desordem no mundo contemporâneo."
    ),
}


def _c1_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Avenida travada. O carro de aplicativo não anda há dez minutos. Ao seu "
            "lado, Luciana digita furiosamente no celular sem olhar pela janela.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "As pessoas reclamam que o mundo tá um caos, mas é simples: tempo é "
            "dinheiro. Quem sabe se adaptar à velocidade, prospera. O resto fica "
            "chorando no trânsito.",
            character="Luciana",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Convencer Luciana de que a hipervelocidade e o imperativo da "
            "produtividade não são a única medida de ordem possível, e que essa "
            "lógica gera o próprio caos.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Desconstrua a ideia de que adaptação e velocidade significam ordem. "
            "Mostre o custo humano dessa 'máquina eficiente'.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ela solta um riso curto, bloqueia a tela do celular por um segundo e "
            "olha para você como se você fosse uma criança ingênua.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Muito bonito isso na teoria. Mas na prática, quem não corre é "
            "atropelado. Eu prefiro estar no volante.",
            character="Luciana",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ela volta a digitar. O argumento bateu no escudo da meritocracia dela e escorregou.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "O sinal abre, mas os carros da frente continuam parados. O barulho de "
            "buzinas começa a ensurdecer a rua.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Você acha que esse sistema falha? Me prove. Me dê um exemplo de como "
            "essa 'velocidade' quebra a gente em vez de impulsionar.",
            character="Luciana",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva apontando a fragilidade desse modelo: mostre como a pressa e a "
            "busca incessante por lucro criam instabilidade e desordem emocional ou "
            "social (ex: burnout, desigualdade).",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Use um argumento concreto de consequência. A máquina que ela elogia está "
            "fundida pelo próprio excesso de giro.",
        ),
    )


def _c2_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "O motorista desliga o rádio para reclamar da buzina contínua. Ele bate "
            "no volante, inconformado.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Não tem mais jeito, o mundo acabou. Na minha época existia respeito, "
            "regra, as coisas funcionavam. Hoje é só bagunça, ninguém liga pra mais "
            "nada.",
            character="Roberto",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para o Roberto: por que o saudosismo é uma ilusão e como as "
            "transformações do mundo atual (tecnologia, valores) não são apenas a "
            "destruição do passado, mas a criação de uma nova lógica complexa.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Não compre o discurso do 'antigamente era melhor'. Argumente que a "
            "sensação de desordem vem da rapidez da mudança, não do fim da ética.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Roberto balança a cabeça, olhando pelo retrovisor, e aumenta a marcha "
            "só para frear bruscamente em seguida.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Nova lógica? Que nova lógica? O que eu vejo é falta de educação e "
            "ninguém querendo assumir responsabilidade.",
            character="Roberto",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele liga o rádio de novo, agora numa estação de notícias policiais. A "
            "nostalgia dele não foi abalada.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "O locutor do rádio fala sobre uma crise internacional invisível que "
            "afeta o preço da gasolina. Roberto suspira.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Se você diz que não é só bagunça, então me explica: da onde vem essa "
            "sensação de que o chão sumiu? Por que parece que a gente não controla "
            "mais nada?",
            character="Roberto",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva explicando que a 'desordem' que ele sente é o resultado da "
            "globalização e de redes hiperconectadas, onde velhas regras locais já "
            "não dão conta de problemas globais.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Conecte o sentimento dele a um fenômeno moderno: o excesso de informação "
            "ou a fluidez de Bauman (modernidade líquida).",
        ),
    )


def _c3_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Um guarda de trânsito se coloca no meio do cruzamento travado, apitando "
            "sem parar e gesticulando ordens que ninguém segue.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "O problema do mundo é falta de limite! Se todo mundo respeitasse a lei "
            "e a autoridade, nada disso estaria acontecendo. Ordem se impõe na "
            "marra!",
            character="Sargento Moura",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Convencer o Sargento de que a complexidade do mundo contemporâneo não "
            "pode ser resolvida com imposição autoritária e punição simples.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Regras antigas não resolvem crises novas. Mostre que a ordem real "
            "depende de pacto social e compreensão, não apenas de coerção.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele dá um tapa no capô de um carro que tentou avançar e aponta o bloco de multas.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Pacto social não organiza cruzamento! O que organiza é a multa e o "
            "medo. Falta mão de ferro nesse país.",
            character="Sargento Moura",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele vira as costas e continua apitando. O caos permanece idêntico, "
            "apenas mais barulhento.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Duas motos sobem na calçada para desviar do bloqueio, ignorando "
            "completamente o guarda, que abaixa o apito cansado.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Eu apito, eu multo, e eles continuam passando por cima. Se a força não "
            "resolve a desordem, o que resolve?",
            character="Sargento Moura",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva explicando que a desordem sistêmica (como a desigualdade ou o "
            "caos urbano) só é superada com políticas estruturais e cidadania, e não "
            "com repressão pontual.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Force não muda estrutura. O caos que ele tenta conter na rua é sintoma "
            "de uma desordem maior que leis de trânsito não alcançam.",
        ),
    )


def _c4_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "Entre os carros parados, Jonas desvia dos retrovisores equilibrando "
            "fardos de água. Ele vê a executiva, o motorista e o guarda brigando.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Vocês acham que o mundo perdeu a ordem? O mundo de quem? Para quem "
            "nasce onde eu nasci, a ordem sempre foi essa brutalidade aí. Nunca "
            "teve paz nenhuma pra ser perdida.",
            character="Jonas",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva para Jonas: reconhecer que a 'ordem' do passado era excludente, "
            "mas argumentar que as crises de hoje (climática, digital) afetam de "
            "maneira nova e mais profunda até quem sempre esteve à margem.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "Valide a visão dele sobre a desigualdade estrutural, mas aponte por que "
            "a desordem atual traz ameaças globais inéditas (ex: precarização extrema).",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele vende uma água, guarda o troco amassado no bolso e encolhe os "
            "ombros, sem parar de andar.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Ameaça inédita? Meu amigo, a minha ameaça inédita é o sol rachando e a "
            "conta de luz. O resto é teoria de gente que tem ar-condicionado.",
            character="Jonas",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele segue para a próxima fila de carros. A urgência da fome esmaga a "
            "sua explicação macroscópica.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Jonas senta no canteiro central por um minuto para contar as moedas, o "
            "rosto molhado de suor sob o calor anormal do meio-dia.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Vocês chamam de desordem. Eu chamo de sobrevivência. Se o buraco tá "
            "mais embaixo agora, me diz: onde essa desordem nova me atinge pior do "
            "que a desordem velha?",
            character="Jonas",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva mostrando o impacto prático dessa nova desordem (como "
            "mudanças climáticas afetando o trabalho de rua ou o fim de garantias "
            "básicas) na vida dele.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Foque no trabalho plataformizado ou na crise ambiental (calor, chuvas). "
            "A desordem moderna cobra a conta dos mais vulneráveis primeiro.",
        ),
    )


def _c5_beats() -> tuple[BeatSeed, ...]:
    return (
        BeatSeed(
            Branch.MAIN,
            BeatType.NARRATION,
            "O trânsito finalmente flui e você chega à sala de aula. O Professor "
            "Carlos te aguarda com a prova aberta na mesa.",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.DIALOGUE,
            "Ouvir as vozes da rua é o começo, não o fim. Agora me apresente uma "
            "tese. O mundo contemporâneo está fora de ordem, ou a ordem atual é, "
            "por natureza, o caos?",
            character="Prof. Carlos",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.OBJECTIVE,
            "Escreva um texto dissertativo-argumentativo sobre o tema: O mundo "
            "contemporâneo está fora de ordem?",
        ),
        BeatSeed(
            Branch.MAIN,
            BeatType.HINT,
            "A tese não pode ser um mero 'sim' ou 'não'. Discuta os fatores que dão "
            "essa percepção (hiperconectividade, crises sistêmicas, desigualdade).",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele lê rapidamente, risca um parágrafo inteiro e devolve a prova com "
            "um suspiro longo.",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.DIALOGUE,
            "Você fez um desabafo sobre o trânsito e o estresse. Falta repertório. "
            "Falta embasamento sociológico ou filosófico. Reescreva.",
            character="Prof. Carlos",
        ),
        BeatSeed(
            Branch.CONSEQUENCE,
            BeatType.NARRATION,
            "Ele aponta para a lousa vazia. O seu texto era superficial e não atendeu "
            "aos requisitos da banca.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.NARRATION,
            "Você puxa a folha de rascunho. O relógio na parede marca trinta minutos "
            "para o fim da prova.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.DIALOGUE,
            "Estruture a tese com clareza. Use um conceito que explique a fluidez do "
            "presente ou o esvaziamento das instituições. Argumente.",
            character="Prof. Carlos",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.OBJECTIVE,
            "Reescreva a redação: defina uma tese sobre a 'desordem' contemporânea "
            "e sustente com repertório (ex: Zygmunt Bauman, Byung-Chul Han, Hannah "
            "Arendt) e argumentos coerentes.",
        ),
        BeatSeed(
            Branch.RECOVERY,
            BeatType.HINT,
            "Foque em duas causas estruturais para o caos (como precarização, bolhas "
            "digitais ou colapso ambiental) e traga repertório válido.",
        ),
    )


def _chapters() -> tuple[ChapterSeed, ...]:
    return (
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A pressa no trânsito",
            objective=(
                "Convencer Luciana de que a hipervelocidade e o imperativo da "
                "produtividade geram desordem e instabilidade."
            ),
            antagonist="Luciana",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável desconstrói a ideia de que velocidade e lucro "
                "equivalem a ordem, apontando falhas concretas do modelo de "
                "produtividade a qualquer custo (adoecimento, crise, desigualdade). "
                "Reclamar genericamente que ela é fria ou materialista não passa."
            ),
            beats=_c1_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A nostalgia do motorista",
            objective=(
                "Explicar ao motorista que a desordem atual é sintoma da complexidade "
                "e conectividade globais, não apenas de um abandono moral."
            ),
            antagonist="Roberto",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável explica a sensação de desordem como fruto de "
                "mudanças estruturais rápidas (globalização, tecnologia) que não "
                "cabem mais nas regras antigas. Concordar com o saudosismo dele "
                "ou apenas dizer que o mundo moderno é melhor não passa."
            ),
            beats=_c2_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A ordem do guarda",
            objective=(
                "Mostrar ao sargento que crises complexas e desigualdade estrutural "
                "não se resolvem com autoritarismo e repressão."
            ),
            antagonist="Sargento Moura",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável opõe a força bruta a soluções sistêmicas (pacto "
                "social, políticas públicas, cidadania), mostrando a ineficácia da "
                "repressão isolada. Atacar a autoridade do guarda ou focar apenas "
                "em leis de trânsito não passa."
            ),
            beats=_c3_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CONFRONTO,
            title="A sobrevivência no asfalto",
            objective=(
                "Reconhecer que a ordem do passado era excludente, mas evidenciar "
                "como a desordem moderna traz impactos práticos aos mais vulneráveis."
            ),
            antagonist="Jonas",
            min_words=120,
            max_words=250,
            evaluator_brief=(
                "Argumento viável valida a denúncia da desigualdade histórica "
                "apontada por Jonas, mas detalha ameaças específicas da modernidade "
                "(crise climática, precarização do trabalho plataformizado) que o "
                "afetam. Falar de filosofia abstrata sem tocar na materialidade não passa."
            ),
            beats=_c4_beats(),
        ),
        ChapterSeed(
            kind=ChapterKind.CHEFE,
            title="A banca da FUVEST",
            objective=(
                "Redação final: texto dissertativo-argumentativo sobre o tema "
                "O mundo contemporâneo está fora de ordem?"
            ),
            antagonist="Prof. Carlos",
            min_words=250,
            max_words=450,
            evaluator_brief=(
                "Texto completo analisando se o mundo atual está em desordem, com "
                "tese clara sustentada por repertório sociocultural produtivo e "
                "argumentação crítica (sociológica, filosófica, histórica). "
                "Senso comum, saudosismo raso ou dissertação vazia de conceitos "
                "não passa."
            ),
            beats=_c5_beats(),
        ),
    )


def seed_fuvest_traffic(session: Session) -> bool:
    """Insert the FUVEST story; returns False when it already exists."""
    return insert_story(
        session,
        StorySeed(
            slug=STORY_SLUG,
            title="Sinal Fechado",
            synopsis=(
                "Preso em um engarrafamento caótico que parece durar para sempre, "
                "você debate com desconhecidos se o mundo contemporâneo perdeu a "
                "ordem ou se o caos já virou a regra do jogo."
            ),
            position=3,
            dimension_floor=55,
            min_average=65,
            characters=CHARACTERS,
            chapters=_chapters(),
            theme=THEME,
        ),
    )
