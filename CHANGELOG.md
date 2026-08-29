# Changelog

## 0.1.0 (2026-08-29)


### Features

* accept Bearer tokens alongside cookies, for the mobile client ([#56](https://github.com/kaualimadesouza/argumenta-api/issues/56)) ([c8a016a](https://github.com/kaualimadesouza/argumenta-api/commit/c8a016a4d3ccf50d758649d4aac3a5f4b76a2999))
* **accounts:** self-service account deletion with purge ([#37](https://github.com/kaualimadesouza/argumenta-api/issues/37)) ([84e76a6](https://github.com/kaualimadesouza/argumenta-api/commit/84e76a6568558b25d996d7655cf97ee3d39ec118)), closes [#14](https://github.com/kaualimadesouza/argumenta-api/issues/14)
* **api:** editable nickname and the progress aggregate ([#40](https://github.com/kaualimadesouza/argumenta-api/issues/40)) ([cedf251](https://github.com/kaualimadesouza/argumenta-api/commit/cedf251465bee14e8201474795cafecfa1cc4eab))
* argument submission with evaluation, verdict and state machine ([#26](https://github.com/kaualimadesouza/argumenta-api/issues/26)) ([0e9f56f](https://github.com/kaualimadesouza/argumenta-api/commit/0e9f56f8b21c8940bc363faff990ebb9e27a7f92))
* auth with email/password and Google SSO ([#23](https://github.com/kaualimadesouza/argumenta-api/issues/23)) ([5f302f5](https://github.com/kaualimadesouza/argumenta-api/commit/5f302f529d7d82c4c647ad1aaa4744d57a348790))
* calibration baseline recording, tight band checking and test restructuring ([#48](https://github.com/kaualimadesouza/argumenta-api/issues/48)) ([3b52422](https://github.com/kaualimadesouza/argumenta-api/commit/3b524225926f28e68dc35f12fd3afcd8f68d6c2a)), closes [#35](https://github.com/kaualimadesouza/argumenta-api/issues/35)
* **calibration:** drift suite for the evaluation engine ([4eb62e2](https://github.com/kaualimadesouza/argumenta-api/commit/4eb62e20f2a856da383c025d8b459ad20eb94cbb)), closes [#12](https://github.com/kaualimadesouza/argumenta-api/issues/12)
* consequence branch and recovery scene flow ([#27](https://github.com/kaualimadesouza/argumenta-api/issues/27)) ([714514c](https://github.com/kaualimadesouza/argumenta-api/commit/714514cfcd4c745efeb981ec9ad7bd5f1080718e))
* **content:** ENEM story "Cuidado Invisível" ([#38](https://github.com/kaualimadesouza/argumenta-api/issues/38)) ([841f87f](https://github.com/kaualimadesouza/argumenta-api/commit/841f87ff7a5a533c5e440e4e6ede03b42e67b3f2)), closes [#15](https://github.com/kaualimadesouza/argumenta-api/issues/15)
* correct pt-br spelling in engine prompts and bump versions ([#49](https://github.com/kaualimadesouza/argumenta-api/issues/49)) ([53b0ee3](https://github.com/kaualimadesouza/argumenta-api/commit/53b0ee39dcc0223c40ec0015182738dad5aae28b))
* correction engine v1 with structured rubric and mandatory evidence ([#25](https://github.com/kaualimadesouza/argumenta-api/issues/25)) ([28815da](https://github.com/kaualimadesouza/argumenta-api/commit/28815da9b97c7ba1a5c5a4b4299f603cc57fc3e9))
* deploy the API to AWS Lambda with SAM and Neon Postgres ([#50](https://github.com/kaualimadesouza/argumenta-api/issues/50)) ([bf32876](https://github.com/kaualimadesouza/argumenta-api/commit/bf328764b501f6b4860a7214c40588be94147dfe))
* FastAPI service skeleton with hexagonal architecture ([#19](https://github.com/kaualimadesouza/argumenta-api/issues/19)) ([16540d2](https://github.com/kaualimadesouza/argumenta-api/commit/16540d21db34fc61cbb1463fb5a3c6deafa3852a))
* historia FUVEST Sinal Fechado completa ([#46](https://github.com/kaualimadesouza/argumenta-api/issues/46)) ([0074e7a](https://github.com/kaualimadesouza/argumenta-api/commit/0074e7a22d2e7accd8b2f46468578b248360c604))
* initial Alembic migration for DER v0.6 ([#22](https://github.com/kaualimadesouza/argumenta-api/issues/22)) ([453881f](https://github.com/kaualimadesouza/argumenta-api/commit/453881feb5d7fe0bdf85d7bd73d7dd0aae41a217))
* **lenses:** ENEM and FUVEST lenses plus the boss essay in the engine ([#29](https://github.com/kaualimadesouza/argumenta-api/issues/29)) ([032cabb](https://github.com/kaualimadesouza/argumenta-api/commit/032cabbdf91cdb2e1e9f587689be3a1f90bc0e19))
* **llm:** the vendor is configuration, not a new engine ([#44](https://github.com/kaualimadesouza/argumenta-api/issues/44)) ([d81b5e6](https://github.com/kaualimadesouza/argumenta-api/commit/d81b5e671a3541436aef68b451ce5f5499ae53e9)), closes [#43](https://github.com/kaualimadesouza/argumenta-api/issues/43)
* move the character reaction to Haiku 4.5 and harden the engine contract ([#59](https://github.com/kaualimadesouza/argumenta-api/issues/59)) ([b9bef27](https://github.com/kaualimadesouza/argumenta-api/commit/b9bef271a5e543795b707de9c421cfc6c1c86095))
* push de streak com registro de dispositivos e job da Expo ([#47](https://github.com/kaualimadesouza/argumenta-api/issues/47)) ([96bbbf7](https://github.com/kaualimadesouza/argumenta-api/commit/96bbbf78062b5c930c46e2c5ad05f830ff82a5db))
* **reactions:** AI character reaction per submission verdict ([#28](https://github.com/kaualimadesouza/argumenta-api/issues/28)) ([826ca85](https://github.com/kaualimadesouza/argumenta-api/commit/826ca852b2dfb069ab8dde0fb949a23ccaa8c52f))
* **telemetry:** batch endpoint for paste and typing events ([#34](https://github.com/kaualimadesouza/argumenta-api/issues/34)) ([e8d8285](https://github.com/kaualimadesouza/argumenta-api/commit/e8d82850056ed6adcfb7547452e9e533bc71db0b))
* tutorial story seed and track/chapter endpoints ([#24](https://github.com/kaualimadesouza/argumenta-api/issues/24)) ([4b29b1c](https://github.com/kaualimadesouza/argumenta-api/commit/4b29b1ced30a0ca3cd693f6c809d4e380fffe467))


### Bug Fixes

* **content:** correct Portuguese accentuation in everything a student reads ([#42](https://github.com/kaualimadesouza/argumenta-api/issues/42)) ([9ad022c](https://github.com/kaualimadesouza/argumenta-api/commit/9ad022cb7086417de9368b71085121172405f1cd))
* **reactions:** one reaction per beat, real token cost, no frozen fallback ([#30](https://github.com/kaualimadesouza/argumenta-api/issues/30)) ([6002d2d](https://github.com/kaualimadesouza/argumenta-api/commit/6002d2d8d5f179ab68b11ca0b57f73d0948b213e))
* **reactions:** return the stored line and survive dirty data on upgrade ([#36](https://github.com/kaualimadesouza/argumenta-api/issues/36)) ([a736ab0](https://github.com/kaualimadesouza/argumenta-api/commit/a736ab048518cd1fc63f9273b773a6a412637c66))
* readiness probe and an explicit status for every domain error ([#54](https://github.com/kaualimadesouza/argumenta-api/issues/54)) ([e6c7212](https://github.com/kaualimadesouza/argumenta-api/commit/e6c72126c0074a94d8fc8a0656c1f48967745dc9)), closes [#53](https://github.com/kaualimadesouza/argumenta-api/issues/53)


### Documentation

* deploy must run alembic upgrade head before traffic switch ([33d2afc](https://github.com/kaualimadesouza/argumenta-api/commit/33d2afcfd3fcac6bda02a62d7e804bf4ab3098d9))
* DER v0.2 - user_exam_targets list with active lens, universal updated_at ([3590100](https://github.com/kaualimadesouza/argumenta-api/commit/35901004ae1dbf3c5b9bb663d056aab44a6446af))
* DER v0.3 - drop web push, push_devices table for React Native app (phase 2) ([8df63f3](https://github.com/kaualimadesouza/argumenta-api/commit/8df63f30db19d742230c0cbd683ab7f00f74a62f))
* DER v0.4 - soft delete on stories ([1851235](https://github.com/kaualimadesouza/argumenta-api/commit/1851235250bb1980495fd78ad8497013c4b6b871))
* DER v0.5 - universal soft delete, partial uniques on deleted_at ([7a716fe](https://github.com/kaualimadesouza/argumenta-api/commit/7a716fe590df06601a0507bf65bb86137aad03ba))
* DER v0.6 - terms_accepted_at on users ([540b5c0](https://github.com/kaualimadesouza/argumenta-api/commit/540b5c0b4522bd4dc9515163bc1ba8030c41dec0))
* PRD - hexagonal architecture template, RN app phase 2 replaces PWA ([fca87a3](https://github.com/kaualimadesouza/argumenta-api/commit/fca87a30b806fe3d56e7a67a97c521e67ca4822c))
* PRD - Sonnet as engine model, streak rule, beta scope decisions ([5348bef](https://github.com/kaualimadesouza/argumenta-api/commit/5348befc7535032396165edcccc10a1a43aefed9))
