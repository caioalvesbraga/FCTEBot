# Arquitetura — Visão geral

O FCTEBot segue uma arquitetura em camadas, orientada a um pipeline de
**Geração Aumentada por Recuperação (RAG)**. Esta página apresenta a visão
arquitetural no estilo **C4** (Contexto → Contêineres → Componentes).

## Nível 1 — Contexto

```mermaid
flowchart TB
    student([Estudante FCTE/UnB])
    admin([Mantenedor / Coordenação])

    subgraph sys[FCTEBot]
        bot[Assistente Virtual RAG]
    end

    ollama[[Ollama - LLM local]]
    gemini[[Google Gemini - fallback]]
    unb[[Sites UnB/SAA/DEG<br/>PDFs e calendários]]

    student -->|pergunta| bot
    admin -->|atualiza base / opera| bot
    bot -->|gera resposta| ollama
    bot -.->|fallback| gemini
    bot -->|ingestão automática| unb
```

O sistema atende **estudantes** (via Telegram e web) e é mantido por um
**mantenedor** (dev/coordenação). Depende do **Ollama** para geração local, com
*fallback* opcional para o **Gemini**, e coleta conteúdo de **fontes oficiais da
UnB** para manter a base atualizada.

## Nível 2 — Contêineres

```mermaid
flowchart TB
    user([Usuário])

    subgraph edge[Borda]
        caddy[Caddy<br/>HTTPS / reverse proxy]
    end

    subgraph app_tier[Aplicação]
        front[Frontend Vue 3<br/>Nginx]
        api[Backend FastAPI<br/>Pipeline RAG + Bot Telegram]
    end

    subgraph data_tier[Dados e modelos]
        redis[(Redis<br/>cache L1/L2)]
        idx[(Índices<br/>FAISS + TF-IDF<br/>data/)]
        ollama[[Ollama<br/>LLM]]
    end

    subgraph obs[Observabilidade]
        prom[Prometheus]
        graf[Grafana]
    end

    user --> caddy --> front
    front -->|/query, /health| api
    api --> redis
    api --> idx
    api --> ollama
    api -->|/metrics| prom
    prom --> graf
```

| Contêiner | Tecnologia | Porta (dev) | Responsabilidade |
|---|---|---|---|
| `fctebot-frontend` | Vue 3 + Nginx | 3000 | SPA de chat; proxy `/query` e `/health` para o backend |
| `fctebot-app` | FastAPI + Uvicorn | 8000 | API REST, pipeline RAG, bot Telegram, métricas |
| `fctebot-ollama` | Ollama | 11434 | Servidor de LLM local (ex.: `qwen2.5:7b`) |
| `fctebot-redis` | Redis 7 | 6379 | Cache multinível de respostas |
| `fctebot-prometheus` | Prometheus | 9090 | Coleta de métricas |
| `fctebot-grafana` | Grafana | 3001 | Dashboards e alertas |
| `caddy` (prod) | Caddy | 80/443 | TLS automático e reverse proxy |

!!! note "Portas"
    Em `docker-compose.yml` o **frontend** ocupa a `3000` e o **Grafana** a
    `3001`. Em produção (`docker-compose.prod.yml`) apenas 80/443 ficam
    expostas via Caddy.

## Nível 3 — Componentes do backend (`src/`)

```mermaid
flowchart LR
    subgraph api[src/api]
        routes[routes.py]
        mw[middleware.py<br/>rate limit + logging]
    end
    subgraph rag[src/rag]
        pipeline[pipeline.py<br/>orquestrador]
        retrieval[retrieval.py<br/>TF-IDF + FAISS + RRF]
        reranker[reranker.py<br/>cross-encoder]
        generator[generator.py<br/>Ollama + Gemini]
        ingestion[ingestion.py<br/>chunking + índices]
    end
    cache[src/cache<br/>redis_cache.py]
    bot[src/bot<br/>telegram_handler.py]
    metrics[src/monitoring<br/>metrics.py]
    config[src/config.py]

    routes --> pipeline
    bot --> pipeline
    pipeline --> cache
    pipeline --> retrieval --> reranker --> generator
    ingestion --> retrieval
    routes --> metrics
    config -.-> pipeline
```

Veja o detalhamento arquivo a arquivo em
[Desenvolvimento → Estrutura do código](../desenvolvimento/estrutura-codigo.md)
e o fluxo de uma consulta em [Pipeline RAG](pipeline-rag.md).

## Camadas (resumo lógico)

1. **Interface** — Telegram e frontend web.
2. **API** — FastAPI (`/query`, `/health`, `/webhook`, `/ingest`, `/cache`).
3. **Cache** — Redis L1 (correspondência exata) + L2 (similaridade semântica).
4. **Recuperação** — híbrida (TF-IDF esparso + FAISS denso), fundida por RRF.
5. **Re-ranking** — cross-encoder multilíngue reordena os melhores trechos.
6. **Geração** — Ollama (local-first) com *fallback* para Gemini.
7. **Observabilidade** — Prometheus + Grafana.

## Decisões arquiteturais

As principais escolhas estão registradas como
[ADRs](decisoes/index.md) — leia-os para entender *por que* cada componente
existe, quais alternativas foram consideradas e quais os trade-offs.
