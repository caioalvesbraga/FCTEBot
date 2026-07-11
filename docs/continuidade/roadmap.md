# Roadmap

Backlog de melhorias para dar continuidade ao projeto. Priorização sugerida;
ajuste conforme necessidade. Itens marcados como *dívida* estão detalhados em
[Dívida técnica](divida-tecnica.md).

## Curto prazo (fundamentos)

- [ ] **Autenticação na rota `/ingest`** (segurança) — *dívida*.
- [ ] **Alinhar path da KB** nos docs/CI para `Infos Adms UnB/` — *dívida*.
- [ ] **Primeiros testes automatizados** (retrieval, cache) + CI de testes.
- [ ] **Rotação de logs** e política de retenção.
- [ ] **Adicionar `LICENSE`** (feito) e finalizar `CONTRIBUTING`/`CHANGELOG`.

## Médio prazo (qualidade e operação)

- [ ] **Rodar RAGAS periodicamente** e publicar métricas no dashboard.
- [ ] **Alertas do Grafana** notificando um canal (Telegram/e-mail).
- [ ] **CI/CD completo** (lint, testes, build do frontend, imagem Docker).
- [ ] **Remover/arquivar o legado v1** (`handlers/`, `utils/`, `main.py` raiz) — *dívida*.
- [ ] **Unificar as duas UIs de chat** (Vue vs. estática em `/chat`) — *dívida*.

## Longo prazo (produto)

- [ ] **Feedback do usuário** (👍/👎) para avaliação contínua e curadoria da base.
- [ ] **Expandir a base** para outros cursos/serviços da FCTE.
- [ ] **Avaliar modelos** (embeddings e LLM) com o *golden set* e registrar ADRs.
- [ ] **Multi-idioma** (garantir respostas sempre em PT-BR).
- [ ] **Painel de administração** para editar a base sem acesso ao servidor.

> **Como usar este roadmap:** ao concluir um item, mova-o para o
> [CHANGELOG](https://github.com/SEU_USUARIO/FCTEBot/blob/main/CHANGELOG.md) e,
> se envolveu decisão relevante, registre um [ADR](../arquitetura/decisoes/index.md).
