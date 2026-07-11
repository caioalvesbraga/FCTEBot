# Referência de configuração

Toda a configuração é feita por variáveis de ambiente (arquivo `.env` na raiz;
copie de `.env.example`). São carregadas e validadas por `src/config.py`
(Pydantic Settings).

!!! note
    O `.env` contém **segredos** (tokens) e **não** deve ser versionado.
    Em runtime, o valor do `.env` prevalece sobre os defaults do `src/config.py`.

## Aplicação

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_NAME` | `FCTEBot` | Nome da aplicação |
| `DEBUG` | `false` | Modo debug |
| `LOG_LEVEL` | `INFO` | Verbosidade dos logs |

## Telegram

| Variável | Padrão | Descrição |
|---|---|---|
| `TELEGRAM_TOKEN` | — | Token do bot (via @BotFather) |
| `TELEGRAM_WEBHOOK_URL` | vazio | URL pública para webhook; vazio = polling (dev) |

## Ollama (LLM local)

| Variável | Padrão | Descrição |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Endereço do servidor Ollama |
| `OLLAMA_MODEL` | `qwen2.5:0.5b` | Modelo; produção GPU usa `qwen2.5:7b` |
| `OLLAMA_TIMEOUT` | `300` | Timeout (s); use alto em CPU |

## Gemini (fallback/primário)

| Variável | Padrão | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | vazio | Chave (`AIza...` legado ou `AQ....` auth 2026) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Modelo Gemini |
| `LLM_STRATEGY` | `local_first` | `local_first` \| `local_only` \| `gemini_only` |

## Embeddings e re-ranker

| Variável | Padrão | Descrição |
|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | Modelo de embeddings |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` ou `cuda` (GPU) |
| `RERANKER_MODEL` | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Cross-encoder |
| `RERANKER_TOP_K` | `2` | Trechos mantidos após o re-ranking |

## Recuperação

| Variável | Padrão | Descrição |
|---|---|---|
| `RETRIEVAL_TOP_K` | `6` | Candidatos recuperados |
| `RETRIEVAL_TFIDF_WEIGHT` | `0.4` | Peso do recuperador esparso no RRF |
| `RETRIEVAL_DENSE_WEIGHT` | `0.6` | Peso do recuperador denso no RRF |
| `CONFIDENCE_THRESHOLD` | `0.0` | Abaixo disso, dispara fallback Gemini |

## Cache (Redis)

| Variável | Padrão | Descrição |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | Conexão Redis |
| `CACHE_L1_TTL` | `604800` | TTL L1 (7 dias) |
| `CACHE_L2_TTL` | `2592000` | TTL L2 (30 dias) |
| `CACHE_L2_SIMILARITY_THRESHOLD` | `0.95` | Similaridade mínima para reuso L2 |

## Base de conhecimento e chunking

| Variável | Padrão | Descrição |
|---|---|---|
| `KNOWLEDGE_BASE_PATH` | `Infos Adms UnB` | Pasta dos documentos-fonte |
| `CHUNK_SIZE` | `512` | Tamanho do chunk |
| `CHUNK_OVERLAP` | `64` | Sobreposição entre chunks |

## Geração

| Variável | Padrão | Descrição |
|---|---|---|
| `TEMPERATURE` | `0.2` | Criatividade da geração |
| `MAX_TOKENS` | `300` | **Aumente para ~2048** para respostas completas |

## Rate limiting e monitoramento

| Variável | Padrão | Descrição |
|---|---|---|
| `RATE_LIMIT_PER_USER` | `30` | Requisições por usuário/minuto |
| `METRICS_PORT` | `9090` | Porta do servidor de métricas Prometheus |

## Setup na primeira subida

| Variável | Padrão | Descrição |
|---|---|---|
| `SKIP_FIRST_RUN_SETUP` | `false` | Pula atualização de docs (ambiente offline) |
| `FORCE_SETUP` | `false` | Força re-download mesmo já inicializado |

## Frontend

| Variável | Padrão | Descrição |
|---|---|---|
| `VITE_API_URL` | vazio | URL da API; vazio em Docker (proxy Nginx); `http://localhost:8000` em dev sem proxy |

!!! tip "Recomendações de produção (GPU)"
    `OLLAMA_MODEL=qwen2.5:7b`, `EMBEDDING_DEVICE=cuda`, `MAX_TOKENS=2048`,
    `OLLAMA_TIMEOUT=300`.
