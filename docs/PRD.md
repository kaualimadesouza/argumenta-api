# PRD: Argumenta (nome de trabalho)

Versão 0.1, 2026-08-18. Status: decisões fechadas em entrevista de requisitos.

## 1. Visão

Plataforma web que treina argumentação textual para estudantes do ensino médio por meio
de histórias interativas. O aluno vive um personagem, encontra um conflito e precisa
convencer outro personagem escrevendo um texto argumentativo. Um motor de correção
avalia o texto com critérios de vestibular (FUVEST e ENEM) somados a critérios de
persuasão dentro do contexto da história. Passar de fase exige cumprir todos os
critérios com nota mínima; argumento fraco gera consequência narrativa.

Tese: treinar redação hoje é solitário e abstrato (tema, folha em branco, nota dias
depois). Encaixar a escrita numa história com interlocutor, consequência imediata e
correção instantânea transforma treino em hábito.

## 2. Público e modelo

- Usuário primário: estudante do ensino médio (14 a 18 anos), vestibulando. B2C,
  cadastro direto, sem escola ou professor no fluxo.
- O modelo de dados não deve impedir uma futura visão de professor, mas nada de turmas
  no MVP.
- Monetização: beta gratuito com limite diário de correções (padrão inicial: 3 por dia).
  Sem billing no MVP.

## 3. Decisões registradas

| # | Tema | Decisão |
|---|------|---------|
| 1 | Objetivo | MVP para validar como negócio, com acabamento profissional (Figma, boa arquitetura) |
| 2 | Público | B2C, aluno direto |
| 3 | Rubrica | Aluno escolhe o vestibular alvo; MVP nasce com FUVEST e ENEM |
| 4 | Arquitetura de avaliação | Motor único; FUVEST/ENEM são lentes de apresentação da nota |
| 5 | Critérios do jogo | Persuasão, viabilidade no contexto e verossimilhança vivem no motor único |
| 6 | Falha | Dois modos: falha técnica (revisão) e falha de persuasão (consequência + recuperação) |
| 7 | Conteúdo | Esqueleto autoral + IA nas reações do personagem ao texto real do aluno |
| 8 | Progressão | Histórias curtas em trilha, dificuldade crescente, temas reais de FUVEST/ENEM passados |
| 9 | Formato do texto | Parágrafos (120 a 250 palavras) nos capítulos; redação completa no capítulo-chefe |
| 10 | Nota mínima | Piso por critério + média mínima crescente, exibida na escala do vestibular |
| 11 | Repertório | Avaliação de plausibilidade + alerta pedagógico; fato claramente falso derruba nota |
| 12 | Anti-cola | Telemetria (colagem, ritmo de digitação) sem bloqueio |
| 13 | Retenção | Streak diário + gráfico de evolução por dimensão + marcos |
| 14 | Plataforma | Web responsiva no MVP; app React Native (Expo) na fase 2; sem PWA (revisão 2026-08-18) |
| 15 | Monetização | Beta grátis com limite diário |
| 16 | Cadastro | Google SSO ou e-mail, coleta mínima (e-mail, apelido, ano do vestibular) |
| 17 | Corretor | Rubrica estruturada com evidência obrigatória + spellcheck determinístico + suíte de calibração |
| 18 | Conteúdo MVP | 3 histórias: tutorial + tema ENEM + tema FUVEST (~10 confrontos) |
| 19 | Stack | FastAPI hexagonal (template python-hexagonal-framework) + Vite/React/TypeScript + Postgres + Claude API |
| 20 | Métricas de validação | Fora de escopo por decisão do fundador |
| 21 | Motor LLM | Claude Sonnet (`claude-sonnet-5`); a suíte de calibração decide upgrades de modelo |
| 22 | Streak | Qualquer envio no dia mantém a sequência, aprovado ou não (prática, não desempenho) |
| 23 | E-mail transacional | Fora do beta: cadastro sem verificação de e-mail e sem reset por e-mail; Google SSO é o caminho de recuperação |
| 24 | Custo LLM | Teto mensal configurável com alerta e bloqueio gracioso, medido pelos tokens em `evaluations` |
| 25 | Ilustrações | Artes paper-cut em SVG no estilo dos mockups até o produto validar; ilustrador humano depois |
| 26 | Régua inicial | Tutorial piso 40 / média 50; história ENEM 50/60; história FUVEST 55/65; chefe 250 a 450 palavras (calibrar jogando) |
| 27 | Lente e veredito | A lente nunca move o veredito: ele sai das 5 dimensoes do jogo. A proposta de intervencao do ENEM e pontuada e exibida (C5) no capitulo-chefe, fora da media |
| 28 | Escala FUVEST | Eixos ficam na escala interna 0-100 e o total e marcado como agregacao Argumenta (`scale_source`), nao da banca, ate a suite de calibracao fechar a conversao |

## 4. Loop central

Hierarquia: Trilha > História > Capítulo. Um capítulo = um confronto argumentativo = uma
fase.

- História: arco curto de 3 a 5 capítulos, 15 a 25 minutos por capítulo.
- Cada história embrulha um tema real de redação já cobrado (FUVEST ou ENEM), com
  enunciado reescrito em palavras próprias (cautela com direitos autorais).
- Capítulo comum: cena roteirizada, conflito, e o aluno escreve 1 a 3 parágrafos
  (120 a 250 palavras) dirigidos ao personagem: tese, justificativa e repertório
  explicado.
- Capítulo-chefe (final da história): redação dissertativa completa no formato do
  vestibular alvo, sobre o tema real da história.
- Reações por IA: o personagem responde citando o argumento real do aluno (rebate o
  ponto fraco específico, reconhece o ponto forte), dentro dos limites do roteiro.

Máquina de estados por envio:

1. **Aprovado** (todos os pisos + média mínima): personagem convencido, história avança,
   nota exibida na escala do vestibular.
2. **Falha técnica** (qualquer dimensão de língua abaixo do piso): a história pausa, o
   texto volta anotado, o aluno revisa e reenvia. Conta como rascunho, sem consequência
   narrativa.
3. **Falha de persuasão** (língua ok, persuasão ou coerência abaixo do piso): o
   personagem não se convence, a história avança para o ramo de consequências ruins, e
   em seguida o aluno recebe uma cena de recuperação com nova chance argumentativa.

## 5. Motor de avaliação

Motor único. FUVEST e ENEM são lentes de apresentação e agregação da nota.

Dimensões internas (0 a 100 cada):

1. **Norma culta**: ortografia, acentuação, pontuação, morfossintaxe.
2. **Coesão**: conectivos, referenciação, paragrafação.
3. **Coerência**: lógica argumentativa, ausência de contradição, progressão temática.
4. **Repertório sociocultural**: presença, explicação, articulação com a tese,
   plausibilidade.
5. **Persuasão situada**: adequação ao interlocutor, viabilidade no contexto da
   história, verossimilhança.

Lentes:

- **ENEM**: C1 recebe norma culta; C2 recebe repertório + aderência ao tema; C3 recebe
  coerência; C4 recebe coesão; C5 (proposta de intervenção) só existe na redação-chefe.
  Nos capítulos, exibição por competência (0 a 200, sem C5); na redação-chefe, escala
  0 a 1000. Persuasão situada exibida à parte como "critério Argumenta".
- **FUVEST**: eixos oficiais (desenvolvimento do tema e ponto de vista;
  estrutura/coerência/coesão; expressão/norma culta) com mapeamento das dimensões.
  Escala oficial exata a confirmar na fase de calibração.

Aprovação: piso por dimensão E média mínima crescente na trilha. Valores iniciais, a
calibrar: piso 50 nas primeiras histórias subindo a 60; média mínima 60 subindo a 80.

Repertório: o critério principal é ser explicado e conectado à tese. Fato claramente
falso ou anacrônico derruba a nota da dimensão; caso duvidoso gera alerta pedagógico
("verifique essa citação") sem reprovar sozinho.

Confiabilidade do corretor:

- Saída estruturada: nota + evidência citada do texto para cada critério. Sem evidência,
  sem desconto.
- Corretor ortográfico determinístico pt-BR ancora os erros objetivos; o LLM classifica
  e explica.
- Suíte de calibração: redações reais já avaliadas (nota 1000 públicas e exemplos
  fracos) rodando como teste de regressão (pytest) a cada mudança de prompt ou modelo.
- Temperatura baixa e versionamento de prompts.

## 6. Conteúdo do MVP

3 histórias, cerca de 10 confrontos no total:

- História-tutorial: fácil, 2 capítulos + chefe, serve de nivelamento e onboarding.
- 1 história sobre tema ENEM real: 3 a 4 capítulos + chefe.
- 1 história sobre tema FUVEST real: 3 a 4 capítulos + chefe.

Pipeline de autoria: escrever esqueletos (cenário, personagens, conflito, argumentos
viáveis esperados, ramos de consequência e recuperação); revisão idealmente por
professor de redação parceiro.

## 7. Feedback: correção em camadas

1. Placar por dimensão na lente do vestibular escolhido, com pisos e média visíveis.
2. O próprio texto do aluno anotado inline: erros marcados no lugar, explicação curta ao
   toque.
3. "Para passar": as 2 ou 3 correções prioritárias.

Na falha técnica, o aluno edita o texto com as anotações à vista.

## 8. Retenção

- Streak diário (o limite diário de correções reforça o hábito). Qualquer envio no
  dia mantém a sequência, aprovado ou não.
- Gráfico de evolução da nota por dimensão ao longo do tempo.
- Marcos por história concluída.
- Lembrete de streak por push no aplicativo React Native (fase 2); o web não envia push.

## 9. Contas e dados (LGPD)

- Entrada por Google SSO ou cadastro e-mail/senha, à escolha do aluno. No beta o
  cadastro por e-mail entra sem verificação e sem "esqueci a senha" (não há
  provedor de e-mail transacional por ora); o Google SSO é o caminho de
  recuperação sugerido.
- Coleta mínima: e-mail, apelido, ano de vestibular. Sem nome completo, CPF, telefone ou
  escola.
- Política de privacidade em linguagem simples; textos do aluno usados apenas para
  correção e progresso; sem venda ou compartilhamento; exclusão de conta autoatendida.

## 10. Telemetria

Eventos de uso (envios, aprovações, tempo de escrita), eventos de colagem e ritmo de
digitação. Sem bloqueio de nada no MVP; os dados informam decisões futuras de anti-cola
e produto.

## 11. Plataforma e stack

- Web responsiva mobile-first no MVP. Aplicativo React Native (Expo) na fase 2, no repo
  `argumenta-mobile`, com push de streak via Expo/FCM/APNs. Sem PWA (revisão de
  2026-08-18; substitui o plano Capacitor/Electron).
- Backend: FastAPI (Python), Postgres, Claude API para correção e reações do personagem.
  Suíte de calibração em pytest.
- Arquitetura do backend: **hexagonal (ports and adapters) com CQRS na camada de
  aplicação**, usando o repo
  [python-hexagonal-framework](https://github.com/mauricio-dalpont/python-hexagonal-framework)
  como template de estrutura: `domain` (entidades, value objects e serviços de domínio
  puros, sem framework), `application` (use cases, commands e queries),
  `adapters` (repositórios SQLAlchemy, cliente Claude, push), `presentation/fastapi`
  (rotas e schemas) e `entrypoints` (montagem do app). O gerenciador de pacotes segue
  uv, como já decidido.
- Frontend: Vite + React + TypeScript.
- Landing page estática separada no futuro, quando SEO/marketing importar.

## 12. Telas para o Figma

1. Entrada/login (Google e e-mail).
2. Onboarding: escolha do vestibular alvo, apelido, ano.
3. Trilha (mapa de histórias e progresso).
4. Cena de história (narrativa e diálogo com o personagem).
5. Editor de argumento (contador de palavras, envio, limite diário visível).
6. Correção em camadas (placar, texto anotado, "para passar").
7. Ramo de consequência + cena de recuperação.
8. Capítulo-chefe (editor de redação completa, confortável no desktop).
9. Perfil/progresso (streak, evolução por dimensão, marcos).
10. Configurações/conta (privacidade, exclusão de conta).

## 13. Fora de escopo do MVP

Dashboard de professor e turmas; billing; ranking e social; detector de IA; apps de
loja (planejados para a fase 2 no `argumenta-mobile`); outros vestibulares (UNICAMP
etc.); banco de repertórios; tutor conversacional; métricas formais de validação
(decisão do fundador).

## 14. Riscos e pendências

Riscos:

- Custo de LLM por correção (mitigado pelo limite diário).
- Consistência do corretor (mitigada pela suíte de calibração).
- Produção de conteúdo autoral é o gargalo de crescimento.
- Direitos autorais sobre enunciados de temas: usar o tema como fato, reescrever o
  enunciado.
- Divergência entre a nota do motor e a banca real: comunicar sempre como estimativa.

Pendências:

- Nome final e domínio.
- Escala FUVEST exata na lente de apresentação (decisão 28: por ora 0-100 marcado como
  agregação Argumenta, para o app nunca exibir número nosso como nota de banca).
- Calibração fina dos pisos e médias jogando (régua inicial proposta na decisão 26).
- Professor de redação revisor (depois do beta).
- Hospedagem: decisão adiada. Análise feita em 2026-08-20: VPS recomendada
  (Oracle Always Free ou Hetzner) mantendo o CI/CD SSH; Cloud Run é a alternativa
  serverless se largar a administração de máquina compensar; Lambda descartado
  (carga IO-bound de LLM pune o modelo de cobrança).
- Política de privacidade e termos de uso com revisão jurídica antes do beta.
