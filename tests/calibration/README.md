# Suite de calibracao do motor

Mede o **drift** do motor de correcao: roda o engine real sobre fixtures
anotadas e compara nota a nota com a referencia, falhando quando o desvio passa
da tolerancia. Serve para responder uma pergunta so: *esta mudanca de prompt
deixou a correcao mais dura, mais frouxa ou instavel?*

## Como rodar

Nao roda por padrao (`addopts = -m 'not calibration'` no `pyproject.toml`), e nao
roda em pull request. Para rodar localmente:

```bash
export ARGUMENTA_ANTHROPIC_API_KEY=sk-...
uv run pytest -m calibration -q
```

Sem a chave, o teste é pulado com a mensagem dizendo o que falta. No CI, o
workflow `Calibration` roda manualmente (`workflow_dispatch`) ou toda noite, usa
o secret `ARGUMENTA_ANTHROPIC_API_KEY` e escreve o relatorio no summary do job.

O relatorio sai por `prompt_version`: quantas fixtures passaram, a media da
referencia e a media do motor por dimensao, e as fixtures ordenadas pelo pior
desvio.

## Sobre as fixtures

As 11 fixtures sao **autorais**, escritas para este repositorio, e cada arquivo
declara isso em `source`. Nao sao redacoes oficiais de vestibular: reproduzir
texto de terceiros aqui seria problema de direito autoral, e fingir que uma nota
inventada é a nota da banca seria pior. O que cada fixture garante é um **perfil
de erro isolado**, que é o que o drift precisa medir:

| Fixture | O que isola |
| --- | --- |
| 01 | plano concreto, tudo alto |
| 02 | mesmo argumento afundado por desvios de norma |
| 03 | ideias soltas, sem coesao |
| 04 | repertorio inventado (lei e estudo falsos) |
| 05 | apelo emocional sem plano |
| 06 | texto correto sobre outro assunto (fuga ao tema) |
| 07 | coacao no lugar de argumento |
| 08 | lugar-comum sem repertorio |
| 09 | contradicao interna |
| 10 | dissertacao-chefe completa, com proposta de intervencao |
| 11 | dissertacao-chefe sem proposta de intervencao |

As notas de referencia sao um gabarito inicial nosso. O PRD ja prevê um
professor de redacao revisor depois do beta: quando isso acontecer, o gabarito
deve ser revisado por ele, e este é o lugar certo para gravar essa revisao.

## Como adicionar uma fixture

Um arquivo JSON em `fixtures/`, nome comecando com numero para manter a ordem:

```json
{
  "slug": "12-exemplo",
  "title": "O que esta fixture isola",
  "source": "autoral (Argumenta), nao e redacao oficial",
  "chapter_objective": "O que a cena pede do aluno.",
  "evaluator_brief": "O que conta como argumento viavel aqui.",
  "persona_brief": "Quem o aluno precisa convencer.",
  "min_words": 120,
  "max_words": 250,
  "text": "O texto do aluno.",
  "expected": {
    "norma_culta": 80,
    "coesao": 70,
    "coerencia": 70,
    "repertorio": 60,
    "persuasao": 60
  },
  "tolerance": 15
}
```

Regras que os testes do harness cobram (e que rodam em todo PR):

- as cinco dimensoes internas sempre presentes em `expected`, de 0 a 100;
- `proposta_intervencao` **somente** em fixture de capitulo-chefe (é ela que faz
  o pedido ao motor incluir a dimensao e ligar a regra de dissertacao completa);
- o texto dentro dos proprios `min_words` e `max_words`, senao a fixture mediria
  o portao de contagem de palavras e nunca chegaria ao motor;
- `slug` unico;
- `tolerance` em pontos, por fixture: use um valor maior quando a dimensao
  isolada for legitimamente subjetiva.

A tolerancia padrao é 15 pontos, larga de proposito. Um LLM nao é regua: o
objetivo é pegar deriva, nao fingir precisao decimal.
