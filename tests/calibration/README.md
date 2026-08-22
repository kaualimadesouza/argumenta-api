# Suite de calibracao do motor

Mede o **drift** do motor de correcao: roda o engine real sobre fixtures
anotadas e compara nota a nota com a referencia. Serve para responder uma
pergunta so: *esta mudanca de prompt (ou de modelo) deixou a correcao mais dura,
mais frouxa ou instavel?*

## O portao tem dois niveis

Um gate por fixture nao pega a regressao mais comum. Se um prompt novo endurece
a correcao em 14 pontos em todas as dimensoes de todas as fixtures, cada fixture
continua dentro da banda de 15 e o job fica verde, que é exatamente o contrario
do que a suite existe para fazer. Por isso:

- **banda por fixture** (`tolerance`, 15 pontos por padrao): pega picos, uma
  dimensao que desabou numa fixture especifica;
- **media entre fixtures** (`MEAN_TOLERANCE`, 5 pontos): pega deslocamento
  sistematico, por dimensao e no geral. Uma media sobre dezenas de medicoes
  absorve ruido de amostragem, entao ela pode e deve ser bem mais apertada.

Uma fixture cuja chamada falhou, ou que voltou sem alguma dimensao, tambem
reprova a corrida: dimensao ausente **nao** é tratada como nota zero, senao toda
media do relatorio viraria ficcao.

## Como rodar

Nao roda por padrao (`addopts = -m 'not calibration'` no `pyproject.toml`), e nao
roda em pull request. Para rodar localmente:

```bash
export ARGUMENTA_ANTHROPIC_API_KEY=sk-...
uv run pytest -m calibration -s
```

O `-m calibration` sobrescreve o `addopts`, e o `-s` mantem o relatorio visivel
quando a corrida passa (sem ele o pytest engole o stdout do teste que passou).
Sem a chave, o teste é pulado dizendo o que falta. Os testes puros do harness
(`test_harness.py`) rodam em todo PR, sem chave e **sem banco**: o
`conftest.py` daqui anula a fixture autouse de banco da raiz.

No CI, o workflow `Calibration` roda quando um prompt muda, sob demanda
(`workflow_dispatch`, que falha se o secret nao existir) e uma vez por semana
como piso. Custa cerca de 12 chamadas por corrida, algo em torno de 30 centavos
de dolar. Esses tokens **nao** passam pelo teto mensal do produto
(`llm_monthly_token_budget`), entao o relatorio informa o gasto da corrida.

## Sobre as fixtures

As 12 fixtures sao **autorais**, escritas para este repositorio, e cada arquivo
declara isso em `source`. Nao sao redacoes oficiais de vestibular: reproduzir
texto de terceiros aqui seria problema de direito autoral, e fingir que uma nota
inventada é a nota da banca seria pior. O que cada fixture garante é um **perfil
de erro isolado**, que é o que o drift precisa medir:

| Fixture | O que isola |
| --- | --- |
| 01 | plano concreto, tudo alto, zero erro de norma |
| 02 | mesmo argumento afundado por desvios de norma (17 palavras desconhecidas) |
| 03 | ideias soltas, sem coesao |
| 04 | repertorio falso e anacronico (artigo inexistente, ECA em 1975) |
| 05 | apelo emocional sem plano |
| 06 | texto correto sobre outro assunto (fuga ao tema) |
| 07 | coacao no lugar de argumento |
| 08 | lugar-comum sem repertorio |
| 09 | contradicao interna |
| 10 | dissertacao-chefe ENEM completa, com proposta de intervencao |
| 11 | dissertacao-chefe ENEM sem proposta de intervencao |
| 12 | dissertacao-chefe FUVEST, que nao cobra proposta de intervencao |

**Acentuacao é conteudo aqui.** O resto do repositorio escreve portugues sem
diacriticos por convencao, mas o texto da fixture é o payload avaliado, e
`norma_culta` julga ortografia e acentuacao. Um texto sem acento com nota 90
seria uma referencia impossivel. Cada fixture declara em `spelling_anchors`
quantas palavras o dicionario pt-BR vendorizado nao conhece, e um teste de
harness (gratuito, em todo PR) confere esse numero contra o corretor real.

**As notas de referencia ainda nao foram confrontadas com o motor.** Sao um
gabarito autoral. A primeira corrida medida pode reprovar por desacordo de
gabarito, e nao por drift: nesse caso o certo é revisar a referencia com o texto
na frente, uma fixture por vez, e registrar a revisao aqui. O PRD ja prevê um
professor de redacao revisor depois do beta, e este é o lugar de gravar essa
revisao. Enquanto isso, nenhuma referencia fica colada no teto ou no chao (um
teste cobra `tolerance <= nota <= 100 - tolerance`), senao a fixture so
detectaria drift numa direcao.

## Como adicionar uma fixture

Um arquivo JSON em `fixtures/`, nome comecando com numero (o nome do arquivo é o
`slug`, nao repita a chave dentro):

```json
{
  "title": "O que esta fixture isola",
  "source": "autoral (Argumenta), nao e redacao oficial",
  "chapter_kind": "confronto",
  "exam": "enem",
  "chapter_objective": "O que a cena pede do aluno.",
  "evaluator_brief": "O que conta como argumento viavel aqui.",
  "persona_brief": "Quem o aluno precisa convencer.",
  "min_words": 120,
  "max_words": 250,
  "spelling_anchors": 0,
  "expected": {
    "norma_culta": 80,
    "coesao": 70,
    "coerencia": 70,
    "repertorio": 60,
    "persuasao": 60
  },
  "text": "O texto do aluno.",
  "tolerance": 15
}
```

Regras que os testes do harness cobram, todas rodando em todo PR:

- `chapter_kind` e `exam` decidem o que o motor vai pontuar, via `grading_spec`:
  `expected` tem que ser exatamente essas dimensoes, nem uma a mais nem a menos.
  A suite nunca redecide essa regra por conta propria;
- chave desconhecida no JSON é rejeitada (pydantic com `extra="forbid"`), assim
  um `expectd` digitado errado nao passa em silencio;
- nota de 0 a 100, e dentro da faixa que deixa a banda simetrica;
- texto dentro dos proprios `min_words` e `max_words`;
- `spelling_anchors` igual ao que o corretor deterministico encontra, e zero
  sempre que `norma_culta >= 70`;
- fixture de capitulo-chefe existe nas duas lentes, porque a FUVEST nao cobra
  proposta de intervencao e esse caminho tambem precisa de cobertura.
