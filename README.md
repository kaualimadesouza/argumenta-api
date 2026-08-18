# argumenta-api

Backend do Argumenta: plataforma que treina argumentação textual para estudantes do
ensino médio por meio de histórias interativas, com correção por critérios de
vestibular (FUVEST e ENEM) somados a persuasão no contexto da história.

## Stack

- FastAPI (Python 3.12) + Postgres
- Migrations com Alembic
- Claude API no motor de correção e nas reações dos personagens
- Deploy via SSH para VPS com CI/CD no GitHub Actions (imagens em GHCR,
  blue/green com healthcheck e rollback)

## Documentação

- [PRD](docs/PRD.md): visão, decisões de produto e escopo do MVP.
- [DER](docs/DER.md): modelo de dados Postgres.

Frontend: [argumenta-web](https://github.com/kaualimadesouza/argumenta-web).
