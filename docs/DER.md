# DER: Argumenta

Versão 0.1, 2026-08-18. Modelo de dados do MVP em Postgres, derivado das decisões do
[PRD](./PRD.md). Identificadores em inglês, snake_case; chaves primárias `uuid`
(`gen_random_uuid()`); todo timestamp é `timestamptz`; extensões: `pgcrypto`, `citext`.

## Visão geral

Quatro domínios: **conta** (quem é o aluno), **conteúdo autoral** (o que os autores
escrevem), **jogo e avaliação** (o que o aluno faz e como o motor corrige) e
**hábito e telemetria** (streak, limite diário, eventos).

```mermaid
erDiagram
  users ||--o{ auth_identities : "entra por"
  users ||--o{ push_subscriptions : "recebe"
  users ||--o{ submissions : "escreve"
  users ||--o{ chapter_progress : "avanca"
  users ||--o{ drafts : "rascunha"
  users ||--o{ daily_activity : "pratica"
  users ||--o{ telemetry_events : "gera"
  themes ||--o{ stories : "inspira"
  stories ||--o{ characters : "tem"
  stories ||--o{ chapters : "contem"
  characters ||--o{ chapters : "antagoniza"
  chapters ||--o{ chapter_beats : "roteiriza"
  characters |o--o{ chapter_beats : "fala em"
  chapters ||--o{ submissions : "recebe"
  chapters ||--o{ chapter_progress : "rastreia"
  chapters ||--o{ drafts : "guarda"
  submissions ||--o{ evaluations : "corrigida por"
  evaluations ||--o{ evaluation_scores : "pontua"
  evaluations ||--o{ evaluation_annotations : "anota"
  submissions ||--o{ character_reactions : "provoca"
  characters ||--o{ character_reactions : "reage em"
  submissions |o--o{ telemetry_events : "contextualiza"
  submissions |o--o{ chapter_progress : "aprova"
```

## Domínio 1: conta e identidade

```mermaid
erDiagram
  users {
    uuid id PK
    citext email UK
    text nickname
    smallint exam_year "ano do vestibular"
    exam target_exam "lente: enem ou fuvest"
    timestamptz created_at
    timestamptz deleted_at "soft delete LGPD"
  }
  auth_identities {
    uuid id PK
    uuid user_id FK
    auth_provider provider "google ou email"
    text provider_subject "sub do Google"
    text password_hash "argon2, so provider email"
    timestamptz created_at
  }
  push_subscriptions {
    uuid id PK
    uuid user_id FK
    text endpoint UK
    text p256dh
    text auth
    timestamptz created_at
  }
  users ||--o{ auth_identities : "entra por"
  users ||--o{ push_subscriptions : "recebe"
```

Notas:

- `users` carrega só o mínimo LGPD do PRD: e-mail, apelido, ano de vestibular.
  Nada de nome completo, CPF, telefone, escola.
- Um usuário pode ter as duas identidades (Google e e-mail):
  `UNIQUE (user_id, provider)` e `UNIQUE (provider, provider_subject)`.
- Exclusão de conta: `deleted_at` marca; uma rotina de expurgo apaga as dependentes
  (`ON DELETE CASCADE`) e anonimiza o que precisar ser retido.

## Domínio 2: conteúdo autoral

```mermaid
erDiagram
  themes {
    uuid id PK
    exam exam "enem ou fuvest"
    smallint year
    text title "tema real que caiu"
    text statement "enunciado reescrito"
  }
  stories {
    uuid id PK
    uuid theme_id FK "null no tutorial"
    text slug UK
    text title
    text synopsis
    smallint position UK "ordem na trilha"
    boolean is_tutorial
    smallint dimension_floor "piso por dimensao 0-100"
    smallint min_average "media minima 0-100"
    text cover_asset
    content_status status "draft ou published"
    timestamptz created_at
    timestamptz updated_at
  }
  characters {
    uuid id PK
    uuid story_id FK
    text name
    text persona_brief "voz do personagem para a IA"
    text portrait_asset
  }
  chapters {
    uuid id PK
    uuid story_id FK
    smallint position "unico por story"
    chapter_kind kind "confronto ou chefe"
    text title
    text objective "o que o aluno deve alcancar"
    uuid antagonist_id FK "quem convencer"
    smallint min_words
    smallint max_words
    text evaluator_brief "o que e argumento viavel aqui"
  }
  chapter_beats {
    uuid id PK
    uuid chapter_id FK
    branch branch "main, consequence ou recovery"
    smallint position "unico por chapter e branch"
    beat_type beat_type "narration, dialogue, objective, hint"
    uuid character_id FK "so em dialogue"
    text body
    text illustration_asset "cena ilustrada"
  }
  themes ||--o{ stories : "inspira"
  stories ||--o{ characters : "tem"
  stories ||--o{ chapters : "contem"
  characters ||--o{ chapters : "antagoniza"
  chapters ||--o{ chapter_beats : "roteiriza"
  characters |o--o{ chapter_beats : "fala em"
```

Notas:

- `themes` guarda os temas reais de FUVEST/ENEM passados, com enunciado **reescrito
  em palavras próprias** (cautela com direitos autorais registrada no PRD).
- A dificuldade crescente da trilha mora em `stories.dimension_floor` e
  `stories.min_average` (piso por critério + média mínima do PRD).
- `chapters.evaluator_brief` alimenta a dimensão de persuasão do motor: descreve o
  que conta como argumento viável naquele contexto.
- `chapter_beats` é o esqueleto autoral: cada ramo (`main`, `consequence`,
  `recovery`) é uma sequência ordenada de batidas (narração, fala, objetivo, dica).
- O antagonista é por capítulo, não por história: capítulos podem trocar o
  interlocutor.

## Domínio 3: jogo e avaliação

```mermaid
erDiagram
  submissions {
    uuid id PK
    uuid user_id FK
    uuid chapter_id FK
    smallint attempt_number "unico por user e chapter"
    submission_context context "main ou recovery"
    text body
    smallint word_count
    integer typing_ms "tempo de escrita"
    smallint paste_count
    timestamptz created_at
  }
  evaluations {
    uuid id PK
    uuid submission_id FK
    boolean is_current "so uma por submission"
    verdict verdict
    numeric average_score "0-100"
    smallint floor_value "piso congelado no envio"
    smallint min_average "media congelada no envio"
    text model
    text prompt_version
    integer latency_ms
    integer input_tokens
    integer output_tokens
    timestamptz created_at
  }
  evaluation_scores {
    uuid id PK
    uuid evaluation_id FK
    dimension dimension "unico por evaluation"
    smallint score "0-100"
    boolean passed_floor
    text evidence "citacao do texto que sustenta a nota"
  }
  evaluation_annotations {
    uuid id PK
    uuid evaluation_id FK
    integer span_start "offset no texto"
    integer span_end
    annotation_type type
    severity severity "error, warning ou praise"
    text message "explicacao curta"
    text suggestion "forma correta"
    smallint priority "1-3 entra no para passar"
  }
  character_reactions {
    uuid id PK
    uuid submission_id FK
    uuid character_id FK
    reaction_beat beat
    text body
    text model
    text prompt_version
    integer output_tokens
    timestamptz created_at
  }
  chapter_progress {
    uuid user_id PK,FK
    uuid chapter_id PK,FK
    chapter_status status
    smallint attempts
    uuid passing_submission_id FK
    timestamptz unlocked_at
    timestamptz passed_at
  }
  drafts {
    uuid user_id PK,FK
    uuid chapter_id PK,FK
    text body
    timestamptz updated_at
  }
  submissions ||--o{ evaluations : "corrigida por"
  evaluations ||--o{ evaluation_scores : "pontua"
  evaluations ||--o{ evaluation_annotations : "anota"
  submissions ||--o{ character_reactions : "provoca"
  submissions |o--o{ chapter_progress : "aprova"
```

Notas:

- **Motor único do PRD em forma de tabela**: `evaluation_scores` tem uma linha por
  dimensão (`norma_culta`, `coesao`, `coerencia`, `repertorio`, `persuasao`, e
  `proposta_intervencao` apenas na redação-chefe com lente ENEM). O gráfico de
  evolução por dimensão do Progresso vira um `GROUP BY` simples.
- **Evidência obrigatória**: `evaluation_scores.evidence` guarda a citação do texto
  que sustenta a nota, regra de confiabilidade do PRD.
- **Regra de aprovação congelada**: `floor_value` e `min_average` são copiados da
  story no momento do envio; recalibrar a régua depois não reescreve o passado.
- **Re-correção com histórico**: `evaluations` é 1-N por submission com
  `is_current` (índice único parcial `WHERE is_current`); quando `prompt_version`
  muda dá para re-corrigir e comparar sem perder nada.
- **Dois modos de falha do PRD** no enum `verdict`: `approved`,
  `failed_technical` (pausa e revisão) e `failed_persuasion` (ramo de consequência).
- `submissions.context` distingue o envio normal (`main`) do envio na cena de
  recuperação (`recovery`).
- `chapter_progress` é a única máquina de estados persistida
  (`locked`, `available`, `drafting`, `in_consequence`, `in_recovery`, `passed`);
  progresso de história e de trilha derivam dela por consulta.
- `drafts` é o rascunho com autosave, apagado quando o capítulo é aprovado.
- `character_reactions` guarda o que a IA fez o personagem responder ao texto real
  do aluno (rebate, convencido, abertura da consequência, chamada da recuperação),
  com custo em tokens para monitorar a conta de LLM.

## Domínio 4: hábito e telemetria

```mermaid
erDiagram
  daily_activity {
    uuid user_id PK,FK
    date activity_date PK
    smallint submissions_count "limite diario de 3"
    smallint approved_count
  }
  telemetry_events {
    bigint id PK "identity, alto volume"
    uuid user_id FK
    uuid submission_id FK "opcional"
    text event_type "paste, typing_stats, screen_view"
    jsonb payload "unico jsonb do modelo"
    timestamptz created_at
  }
  users ||--o{ daily_activity : "pratica"
  users ||--o{ telemetry_events : "gera"
  submissions |o--o{ telemetry_events : "contextualiza"
```

Notas:

- O limite de 3 correções/dia é um `UPSERT` atômico em `daily_activity` que
  incrementa `submissions_count` e rejeita acima do teto.
- Streak atual e recorde derivam de `daily_activity` (dias consecutivos com
  `submissions_count > 0`); nada denormalizado no MVP.
- Telemetria anti-cola sem bloqueio (decisão do PRD): eventos `paste` e
  `typing_stats` com payload livre em JSONB, o único JSONB do modelo, porque o
  formato é heterogêneo por natureza.

## Enums

| Enum | Valores | Usado em |
|------|---------|----------|
| `exam` | `enem`, `fuvest` | `users.target_exam`, `themes.exam` |
| `auth_provider` | `google`, `email` | `auth_identities.provider` |
| `content_status` | `draft`, `published` | `stories.status` |
| `chapter_kind` | `confronto`, `chefe` | `chapters.kind` |
| `branch` | `main`, `consequence`, `recovery` | `chapter_beats.branch` |
| `beat_type` | `narration`, `dialogue`, `objective`, `hint` | `chapter_beats.beat_type` |
| `submission_context` | `main`, `recovery` | `submissions.context` |
| `verdict` | `approved`, `failed_technical`, `failed_persuasion` | `evaluations.verdict` |
| `dimension` | `norma_culta`, `coesao`, `coerencia`, `repertorio`, `persuasao`, `proposta_intervencao` | `evaluation_scores.dimension` |
| `annotation_type` | `spelling`, `accentuation`, `punctuation`, `grammar`, `cohesion`, `coherence`, `repertoire_alert`, `repertoire_praise`, `persuasion` | `evaluation_annotations.type` |
| `severity` | `error`, `warning`, `praise` | `evaluation_annotations.severity` |
| `reaction_beat` | `rebuttal`, `convinced`, `consequence_intro`, `recovery_prompt` | `character_reactions.beat` |
| `chapter_status` | `locked`, `available`, `drafting`, `in_consequence`, `in_recovery`, `passed` | `chapter_progress.status` |

## Índices além das PKs/uniques

- `submissions (user_id, chapter_id)`: histórico de tentativas do capítulo.
- `evaluations (submission_id) WHERE is_current`: único parcial, garante uma
  avaliação corrente por envio.
- `evaluation_scores (evaluation_id)` e, para o gráfico de evolução,
  `evaluation_scores (dimension)` combinado com join em `evaluations.created_at`.
- `telemetry_events (user_id, created_at)`: consultas por aluno e período.
- `chapter_beats (chapter_id, branch, position)`: leitura do roteiro em ordem.

## Decisões de modelagem

1. **Tabelas tipadas, não sacos de JSON.** Notas por dimensão e anotações são
   linhas com colunas e enums; JSONB existe só em `telemetry_events.payload`.
   Consulta, índice e integridade vêm de graça, e o gráfico de evolução por
   dimensão é um agregado trivial.
2. **A régua viaja com a avaliação.** Piso e média mínima são congelados em
   `evaluations` no momento do envio; a trilha pode ser recalibrada sem efeito
   retroativo.
3. **Uma única máquina de estados.** Só `chapter_progress` persiste estado de
   progresso; história concluída e trilha desbloqueada são derivações. Menos
   estado, menos chance de incoerência.
4. **Calibração é cidadã do modelo.** `model` e `prompt_version` em toda avaliação
   e reação; a suíte de regressão (pytest) referencia essas versões.
5. **LGPD por construção.** Coleta mínima em `users`, soft delete com expurgo,
   textos do aluno tratados como dado pessoal no expurgo.

## O que fica fora do banco

- **Mapeamento de lentes** (dimensões para C1-C5 do ENEM ou eixos FUVEST): vive no
  código, versionado junto de `prompt_version`.
- **Prompts do motor e das reações**: arquivos no repositório, versionados no git.
- **Suíte de calibração**: fixtures e testes pytest, não linhas de produção.
- **Assets** (ilustrações, retratos, capas): storage estático/S3; o banco guarda o
  caminho.
