---
name: portuguese-copy
description: Write correct pt-BR in every string a student can read, with full accentuation, crase and hyphenation. Use when writing or editing story content, character personas, objectives, hints, UI copy, error messages, legal text, LLM prompts, or any Portuguese prose.
---

# Portuguese copy: accents are not optional

Argumenta teaches writing. A product that grades a student's spelling and shows
them `"Voce e presidente do gremio ha onze dias"` has no standing to correct
anybody. Every Portuguese string a student can read must be **orthographically
correct pt-BR** under the Acordo Ortográfico de 1990: diacritics, crase and
hyphens included.

This is an owner decision (2026-08-22), triggered by exactly that sentence
appearing on screen in the tutorial.

## Where it applies

Everything a student, or the correction model, actually reads:

- story content: narration, dialogue, objectives, hints, chapter and story
  titles, synopses, character names and `persona_brief`, `evaluator_brief`
- UI copy (pt-BR by convention), empty states, button labels, notices
- error messages and any text mapped from an API error code
- lens criterion labels (they are shown on the scoreboard)
- LLM prompts written in Portuguese
- legal pages, README prose, issue and PR bodies

## Where it does NOT apply

Identifiers stay ASCII and unaccented, on purpose:

- slugs (`o-gremio`, `cuidado-invisivel`), enum values, column and table names
- file names, module names, branch names, git commit subjects
- code, identifiers and comments (those are in English anyway)

A slug is not copy. Do not "fix" `o-gremio`: it is a key, and changing it breaks
idempotency of the seeds and any row already pointing at it.

## The traps that actually showed up here

Words this codebase got wrong at least once:

> você, vocês, não, é, há, até, três, só, já, além, através, próprio, próximo,
> último, único, possível, necessário, específico, responsável, verificável,
> viável, grêmio, pátio, Tenório, óculos, braços, mãos, sábado, prejuízo,
> mágoa, auditório, silêncio, murmúrio, plateia (sem acento, pós-reforma),
> colégio, associação, reunião, redação, correção, avaliação, organização,
> intervenção, reclamação, ameaça, espaço, reposição, bajulação, segurança,
> condição, portão, pichação, votação, intenção, intenções, objeções, razões,
> soluções, preocupações, dimensão, dimensões, coesão, coerência, persuasão,
> repertório, critério, ortografia, acentuação, pontuação, gramática,
> explicação, sugestão, evidência, consequência, pedagógico, linguísticos,
> domínio, compreensão, seleção, expressão

Two things that are not accents but break the same way:

- **crase**: "respondendo **às** objeções", "**à** autoridade da diretora",
  "responde **às** três perguntas". Not `as` when the sense is `a + as`.
- **hyphen in enclisis**: "como o grêmio vai **organizá-lo**", never `organiza-lo`.

## Check before committing

Grep the strings you touched for the usual suspects. From the repo root:

```bash
grep -rnE --include='*.py' '\b(voce|nao|entao|tambem|ate|apos|alem|atraves|proprio|proximo|ultimo|unico|possivel|necessario|especifico|responsavel|verificavel|viavel|gremio|patio|Tenorio|oculos|bracos|maos|sabado|prejuizo|magoa|auditorio|silencio|murmurio|colegio|associacao|reuniao|redacao|correcao|avaliacao|organizacao|intervencao|reclamacao|ameaca|espaco|reposicao|bajulacao|seguranca|condicao|portao|pichacao|votacao|intencao|intencoes|objecoes|razoes|solucoes|preocupacoes|dimensao|dimensoes|coesao|coerencia|persuasao|repertorio|criterio|acentuacao|pontuacao|gramatica|explicacao|sugestao|evidencia|consequencia|pedagogico|linguisticos|dominio|compreensao|selecao|expressao)\b' src/ docs/ | grep -v __pycache__
```

Hits inside slugs, enum values or English comments are fine. Hits inside a
Portuguese string are bugs.

## Content already in a database

The seeds are **idempotent by slug**: fixing a string in `seed/*.py` does not
touch a database that already has the story. Nothing is deployed yet, so the fix
plus a fresh seed is enough. Once something is deployed, a content correction
needs a data migration (see the `db-migrations` skill), the same way the frozen
fallback reaction lines were retired.

## Prompts are versioned

The Portuguese in `adapters/llm/prompts/` is read by the model, so fixing it
changes grading behaviour. That means bumping the prompt version and re-running
the calibration suite, never a silent edit. Treat it as its own card.
