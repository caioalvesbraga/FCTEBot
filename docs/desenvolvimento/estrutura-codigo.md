# Estrutura do código

Mapa dos diretórios e módulos. O backend ativo é a **v2** em `src/`; há código
**legado v1** na raiz (ver [Dívida técnica](../continuidade/divida-tecnica.md)).

## Diretórios de alto nível

| Pasta | Conteúdo |
|---|---|
| `src/` | Backend v2: FastAPI, pipeline RAG, cache, bot, métricas |
| `frontend/` | SPA Vue 3 + Vite + Pinia (servida por Nginx em prod) |
| `scripts/` | Ingestão, automação de conteúdo, setup de deploy |
| `evaluation/` | Dataset de perguntas, avaliação RAGAS, baseline |
| `monitoring/` | Configuração Prometheus/Grafana |
| `Infos Adms UnB/` | Base de conhecimento (fonte real) |
| `data/` | Índices gerados (FAISS/TF-IDF) |
| `handlers/`, `utils/`, raiz | **Legado v1** (Telegram + MySQL + Pinecone) |

## Backend (`src/`)

| Arquivo | Papel |
|---|---|
| `main.py` | Bootstrap FastAPI (lifespan: Redis, retriever, reranker, generator, pipeline, bot), CORS, middleware |
| `config.py` | Settings via Pydantic; paths derivados; validação de chave Gemini |
| `rag/ingestion.py` | Ingestão PDF/MD/TXT/DOCX → chunking → índices FAISS + TF-IDF |
| `rag/retrieval.py` | Recuperação híbrida TF-IDF + FAISS com RRF |
| `rag/reranker.py` | Re-ranking com cross-encoder multilíngue |
| `rag/generator.py` | Geração Ollama + fallback Gemini + circuit breaker + guardrails |
| `rag/pipeline.py` | Orquestrador: cache → retrieval → rerank → generate |
| `cache/redis_cache.py` | Cache L1 (hash) + L2 (similaridade) |
| `api/routes.py` | Endpoints REST |
| `api/middleware.py` | Rate limiting e logging |
| `bot/telegram_handler.py` | Comandos e handler de mensagens do Telegram |
| `monitoring/metrics.py` | Métricas Prometheus (`fctebot_*`) |

## Frontend (`frontend/src/`)

| Área | Conteúdo |
|---|---|
| `components/` | `AppHeader`, `AppFooter`, `ChatWindow`, `ChatInput`, `ChatMessage`, `ChatSidebar` |
| `stores/` | `chat.ts` (sessões em localStorage), `settings.ts` (tema, sidebar) |
| `composables/` | `useApi.ts` (cliente HTTP para `/query` e `/health`) |
| `types/` | `index.ts` (contratos com a API) |
| `assets/` | `design-system.css` |

Conexão: em dev, proxy do Vite; em Docker/prod, Nginx (`frontend/nginx.conf`)
faz proxy para `app:8000`.

## Fluxo de dados

Ver [Arquitetura → Pipeline RAG](../arquitetura/pipeline-rag.md).
