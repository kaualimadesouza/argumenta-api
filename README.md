# argumenta-api

Backend do Argumenta: plataforma que treina argumentação textual para estudantes do
ensino médio por meio de histórias interativas, com correção por critérios de
vestibular (FUVEST e ENEM) somados a persuasão no contexto da história.

## Stack

- FastAPI (Python 3.12, uv) + Postgres
- Migrations com Alembic
- Claude API no motor de correção e nas reações dos personagens
- Deploy via SSH para VPS com CI/CD no GitHub Actions (imagens em GHCR,
  blue/green com healthcheck e rollback)

## Setup local

```bash
uv sync                 # instala dependências e o pacote em modo editável
docker compose up       # sobe Postgres 16 e a API em http://localhost:8000
make run                # alternativa: só a API, com reload (banco via compose)
make check              # lint + typecheck + contratos de import + testes
```

Variáveis de ambiente: copie `.env.example` para `.env` (prefixo `ARGUMENTA_`).

## Arquitetura

Hexagonal (ports and adapters) com CQRS na camada de aplicação, seguindo a
estrutura do template
[python-hexagonal-framework](https://github.com/mauricio-dalpont/python-hexagonal-framework):

```
src/argumenta/
  domain/               # entidades, value objects e serviços de domínio puros
  application/          # use cases, commands e queries (CQRS)
  adapters/             # repositórios SQLAlchemy, cliente Claude, push
  presentation/fastapi/ # rotas e schemas da API
  entrypoints/          # montagem da aplicação (rest_application)
  settings.py           # configuração via pydantic-settings
```

`domain` e `application` não podem importar FastAPI nem SQLAlchemy; a regra é
verificada por contratos do [import-linter](https://import-linter.readthedocs.io/)
(`make imports`) e roda no CI junto de ruff, mypy (strict) e pytest.

## Documentação

- [PRD](docs/PRD.md): visão, decisões de produto e escopo do MVP.
- [DER](docs/DER.md): modelo de dados Postgres.

Frontend: [argumenta-web](https://github.com/kaualimadesouza/argumenta-web).
Aplicativo (fase 2): [argumenta-mobile](https://github.com/kaualimadesouza/argumenta-mobile).
