# argumenta-api

Backend do Argumenta: plataforma que treina argumentação textual para estudantes do
ensino médio por meio de histórias interativas, com correção por critérios de
vestibular (FUVEST e ENEM) somados a persuasão no contexto da história.

## Stack

- FastAPI (Python 3.12, uv) + Postgres
- Migrations com Alembic
- Claude API no motor de correção e nas reações dos personagens
- Deploy serverless na AWS (Lambda + API Gateway) via GitHub Actions, com
  infraestrutura em Terraform

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

## Deploy

O deploy é automatizado no GitHub Actions (`.github/workflows/deploy.yml`), num pipeline de 4 estágios: **CI** (lint, types, testes) → **Build and Push** (imagem Docker da API, publicada no Amazon ECR) → **Deploy** (migrations do Alembic + `terraform apply`, subindo a função **AWS Lambda** por trás de um **API Gateway**) → **Notify** (mensagem no Telegram com o resultado).

A infraestrutura vive como código em `infrastructure/` (Terraform: função Lambda, role de execução, API Gateway e a permissão entre os dois). A função Lambda roda como container (`package_type = "Image"`, ver `Dockerfile`), não como zip: o estágio de build gera a imagem e a envia ao ECR marcada com o SHA do commit, e o estágio de deploy só referencia essa imagem já publicada via a variável `image_uri` (o `terraform apply` não builda nada, só atualiza os recursos AWS para apontar pra ela). Isso desacopla "gerar o artefato" de "publicá-lo". O state do Terraform fica num bucket S3 remoto (nunca commitado: contém os valores resolvidos dos secrets), com uma chave por ambiente (`argumenta-api/<dev|prod>/terraform.tfstate`).

O banco de dados de produção fica hospedado gratuitamente no **Neon** (Serverless Postgres), aproveitando o connection pooling nativo (`pooler.neon.tech`), o que é fundamental para a compatibilidade com a natureza altamente paralela do Lambda.

**Antes do primeiro deploy**, configurações manuais (uma vez só, fora do Terraform, pra sobreviverem caso a infra seja destruída): o repositório ECR (`argumenta-api`, com uma lifecycle policy que expira imagens além das últimas 10, já que cada deploy empurra uma tag nova pelo SHA do commit e nada apaga as antigas sozinho) e o bucket S3 do state remoto (`argumenta-api-tfstate-<account-id>`, versionamento habilitado). Reproduzível com:

```bash
aws ecr create-repository --repository-name argumenta-api --region us-east-1 \
  --image-scanning-configuration scanOnPush=true --image-tag-mutability MUTABLE
aws ecr put-lifecycle-policy --repository-name argumenta-api --region us-east-1 \
  --lifecycle-policy-text file://infrastructure/ecr-lifecycle-policy.json
# sem isso o CreateFunction falha com AccessDeniedException: o Lambda puxa a
# imagem como service principal, nao com as credenciais de quem faz o deploy
aws ecr set-repository-policy --repository-name argumenta-api --region us-east-1 \
  --policy-text file://infrastructure/ecr-lambda-pull-policy.json

aws s3api create-bucket --bucket <seu-bucket-tfstate> --region us-east-1
aws s3api put-bucket-versioning --bucket <seu-bucket-tfstate> \
  --versioning-configuration Status=Enabled

gh variable set TF_STATE_BUCKET --body "<seu-bucket-tfstate>"
```

**Variáveis (não sensíveis) que escolhem o motor de correção**, com default pro código atual caso não sejam setadas (`anthropic`/`claude-sonnet-5`):
```bash
gh variable set ARGUMENTA_LLM_VENDOR --body "google"          # anthropic | openai | google
gh variable set ARGUMENTA_EVALUATION_MODEL --body "gemini-3-pro"
gh variable set ARGUMENTA_REACTION_MODEL --body "gemini-3-pro"
gh secret set ARGUMENTA_GOOGLE_API_KEY --body "SUA_CHAVE_GEMINI"
```

O usuário IAM usado pelo pipeline (`argumenta-api-deployer`) não é o admin da conta: tem uma policy própria (`argumenta-api-deployer-policy`) com só o necessário para essas etapas (push no ECR, ler/escrever o state no bucket acima, e gerenciar a função Lambda, sua role de execução e o API Gateway, todos com nomes restritos a `argumenta-api-*`).

**Secrets necessários no ambiente do GitHub:**
- `AWS_ACCESS_KEY_ID`: access key do usuário `argumenta-api-deployer`.
- `AWS_SECRET_ACCESS_KEY`: secret key do mesmo usuário.
- `ARGUMENTA_ANTHROPIC_API_KEY`: Chave do Claude. Opcional se `ARGUMENTA_LLM_VENDOR` não for `anthropic`.
- `ARGUMENTA_GOOGLE_API_KEY`: Chave do Gemini (Google AI Studio). Necessária se `ARGUMENTA_LLM_VENDOR` for `google`. Não confundir com o OAuth abaixo, são credenciais diferentes.
- `ARGUMENTA_GOOGLE_CLIENT_ID`: OAuth do Google (login).
- `ARGUMENTA_GOOGLE_CLIENT_SECRET`: OAuth do Google (login).
- `ARGUMENTA_DATABASE_URL`: URL do Neon **com pooler**, formato `postgresql+psycopg://user:pass@ep-...-pooler.neon.tech/db`. Usada em runtime pela função Lambda. <!-- pragma: allowlist secret -->
- `ARGUMENTA_DATABASE_URL_DIRECT`: URL do Neon **sem pooler** (mesmo host, sem o sufixo `-pooler`), mesmo formato acima. Usada só para rodar as migrations do Alembic: o pooler do Neon roda em modo transaction do pgbouncer, que não sustenta o estado de sessão que o Alembic depende. <!-- pragma: allowlist secret -->
- `ARGUMENTA_JWT_SECRET`: Chave secreta da aplicação para assinar os tokens JWT (32+ bytes).
- `TELEGRAM_BOT_TOKEN`: token do bot criado com o [@BotFather](https://t.me/BotFather), usado pelo estágio de notificação.
- `TELEGRAM_CHAT_ID`: id do chat (pessoal) pra onde a notificação de sucesso/falha do deploy é enviada.

**Como acionar:**
```bash
gh workflow run deploy.yml -f environment=dev   # manual deploy (dev/prod)
```
O deploy também ocorre a cada `push` na `main`.
