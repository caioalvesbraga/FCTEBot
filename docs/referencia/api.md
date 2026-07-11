# Referência da API

O backend expõe uma API REST via FastAPI. A documentação interativa (OpenAPI /
Swagger) é gerada automaticamente em **`/docs`** e o schema em **`/openapi.json`**.

Base URL (dev): `http://localhost:8000`.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Informações básicas da API |
| `GET` | `/health` | Health check de todos os componentes |
| `POST` | `/query` | Consulta ao pipeline RAG |
| `POST` | `/webhook` | Webhook do Telegram |
| `POST` | `/ingest` | Dispara re-ingestão em background |
| `DELETE` | `/cache` | Invalida todo o cache |
| `GET` | `/cache/stats` | Estatísticas do cache |
| `GET` | `/retriever/stats` | Estatísticas do índice |

## `POST /query`

Processa uma pergunta pelo pipeline RAG completo.

**Request:**

```json
{
  "query": "Com quanto tempo de antecedência preciso enviar o TCE?",
  "user_id": "opcional-para-métricas"
}
```

- `query` — obrigatório, 3 a 1000 caracteres.
- `user_id` — opcional.

**Response `200`:**

```json
{
  "response": "Deve ser enviado à coordenação com pelo menos 15 dias...",
  "sources": ["estagio.md"],
  "mode": "local",
  "confidence": 0.738,
  "latency_ms": 10990.2,
  "cache_hit": "none",
  "model_used": "qwen2.5:7b"
}
```

| Campo | Valores | Significado |
|---|---|---|
| `mode` | `local`, `fallback`, `cached`, `forbidden` | Origem da resposta |
| `cache_hit` | `none`, `l1`, `l2` | Se veio do cache e de qual nível |
| `confidence` | 0.0–1.0 | Confiança da recuperação/geração |
| `model_used` | ex.: `qwen2.5:7b`, `gemini-2.0-flash` | Modelo que gerou |

**Exemplo curl:**

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Como faço matrícula no SIGAA?"}' | python3 -m json.tool
```

**Erros:** `500` (erro interno no pipeline), `503` (pipeline não inicializado —
rode a ingestão).

## `GET /health`

Retorna `200` quando `status` é `ok`/`degraded`, e `503` quando `error`.

```json
{
  "status": "ok",
  "retriever": true,
  "cache": true,
  "ollama": true,
  "gemini": true,
  "gemini_key_valid": true,
  "gemini_key_type": "auth",
  "llm_strategy": "local_only",
  "index_chunks": 970
}
```

## `POST /ingest`

Dispara a re-ingestão em background e, ao concluir, recarrega o retriever e
invalida o cache. Responde imediatamente:

```json
{ "status": "ingestão iniciada em background", "message": "Use /health para verificar quando concluir" }
```

!!! warning "Sem autenticação"
    A rota **não** valida credenciais atualmente, apesar de o workflow de CI
    enviar `Authorization: Bearer`. Não exponha `/ingest` publicamente sem
    proteção. Ver [Segurança](../qualidade/seguranca-lgpd.md) e
    [Dívida técnica](../continuidade/divida-tecnica.md).

## `DELETE /cache` · `GET /cache/stats` · `GET /retriever/stats`

- `DELETE /cache` → `{ "deleted_keys": N, "message": "..." }`.
- `GET /cache/stats` → conexão, contadores L1/L2.
- `GET /retriever/stats` → estatísticas do índice (inclui `total_chunks`).

## `POST /webhook`

Recebe *updates* do Telegram e delega ao handler do bot. Usado quando
`TELEGRAM_WEBHOOK_URL` está configurado (caso contrário, o bot opera em polling).
