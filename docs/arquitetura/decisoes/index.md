# Decisões de Arquitetura (ADRs)

Os **Architecture Decision Records (ADRs)** registram decisões arquiteturais
relevantes: o contexto, a decisão tomada, as alternativas consideradas e as
consequências. Servem para que futuros mantenedores entendam *por que* o sistema
é como é — não apenas *como* ele funciona.

## Convenções

- Um arquivo por decisão, numerado sequencialmente: `NNNN-titulo-curto.md`.
- Não edite decisões antigas para "consertar" o histórico. Se uma decisão for
  revista, crie um novo ADR e marque o anterior como **Substituído por ADR-NNNN**.
- Use o [template](template.md) como ponto de partida.

## Índice

| ADR | Título | Status |
|---|---|---|
| [0001](0001-rag-hibrido-tfidf-faiss-rrf.md) | RAG híbrido (TF-IDF + FAISS + RRF) | Aceito |
| [0002](0002-local-first-ollama-fallback-gemini.md) | Local-first (Ollama + fallback Gemini) | Aceito |
| [0003](0003-cache-multinivel-redis.md) | Cache multinível com Redis | Aceito |

> **TODO (continuidade):** documentar como novos ADRs decisões futuras (ex.:
> escolha do modelo de embeddings, migração do frontend, autenticação da API).
