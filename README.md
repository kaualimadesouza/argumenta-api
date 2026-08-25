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

`make seed` insere o conteúdo das histórias (tutorial "O Gremio" e a história
ENEM "Cuidado Invisível"). É idempotente por slug, então roda em todo deploy:
história já presente é reportada e não é tocada. A trilha é linear na ordem de
`stories.position`, então a história ENEM abre quando o tutorial termina.

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

## Autenticação

Duas portas de entrada: cadastro/login por e-mail e senha (hash argon2) e Google
SSO (authorization code flow), gravando em `users` + `auth_identities`. A sessão
vive em cookies httpOnly: access token JWT curto (15 min) e refresh token (14
dias) restrito a `/auth`. Login por e-mail tem rate limit por IP+e-mail.
Endpoints: `POST /auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`,
`/auth/logout`, `GET /me` e gestão de alvos de vestibular em `/me/targets`.

Limitações conhecidas do beta (decisão de produto, sem e-mail transacional):

- Cadastro sem verificação de e-mail e sem fluxo "esqueci a senha"; o caminho de
  recuperação sugerido é o login com Google.
- Tokens são stateless: logout limpa os cookies, mas não existe revogação
  server-side de um token exfiltrado (session store fica para a fase 2). A única
  revogação que existe é a da conta excluída: toda requisição autenticada
  confirma no banco que a conta ainda está lá.

Google OAuth exige `ARGUMENTA_GOOGLE_CLIENT_ID` e `ARGUMENTA_GOOGLE_CLIENT_SECRET`
(criados no Google Cloud Console); sem eles o endpoint `/auth/google` responde 502.

## Exclusão de conta (LGPD)

`DELETE /me` responde 202: a conta para de funcionar na hora (sessão morta,
identidades e dispositivos aposentados, login recusado) e as linhas são
apagadas pela varredura, depois da janela de carência
(`ARGUMENTA_ACCOUNT_PURGE_GRACE_DAYS`, 7 dias). A carência é a única chance de
desfazer uma exclusão por engano; o aluno não percebe diferença, porque para ele
a conta já morreu.

A varredura é `make purge` (`python -m argumenta.entrypoints.purge_accounts`),
feita para rodar agendada: ela apaga a linha de `users` e o Postgres derruba
todo o resto por cascade. O expurgo é **hard delete**, a única exceção ao soft
delete universal do DER, porque o texto do aluno é dado pessoal. Um teste de
schema garante que nenhuma tabela nova entre com FK que recuse o delete.

## Releases

Versionamento e changelog são automáticos via
[Release Please](https://github.com/googleapis/release-please): todo merge na main
com conventional commit (`feat:`, `fix:`, ...) alimenta um PR de release; mergear
esse PR cria a tag semver, a GitHub Release e o `CHANGELOG.md`, propagando a
versão para `pyproject.toml` e `src/argumenta/__init__.py`. PRs são squash-merged
com título convencional (validado pelo workflow de título).

## Documentação

- [PRD](docs/PRD.md): visão, decisões de produto e escopo do MVP.
- [DER](docs/DER.md): modelo de dados Postgres.

Frontend: [argumenta-web](https://github.com/kaualimadesouza/argumenta-web).
Aplicativo (fase 2): [argumenta-mobile](https://github.com/kaualimadesouza/argumenta-mobile).

## Calibração do Motor

O motor de correção LLM possui uma suíte de calibração em `tests/calibration` para proteger contra regressões e variações. A tolerância contra o gabarito autoral é de 15 pontos por dimensão. A variância do modelo por chamada (ruído de amostragem) foi medida empiricamente (3 corridas sucessivas) em **5 pontos**; esse valor é usado como banda estrita (`TIGHT_BAND`) para proteger contra drift quando uma baseline medida já existe para o prompt atual.
