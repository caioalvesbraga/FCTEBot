# Setup local

Como rodar o FCTEBot na sua máquina para desenvolvimento.

## Pré-requisitos

- **Docker** e **Docker Compose**
- (Opcional, dev sem Docker) **Python 3.11+** e **Node 22+**
- Espaço em disco para modelos de embedding (~500 MB) e o modelo do Ollama

## Opção 1 — Docker (recomendado)

```bash
# 1. configuração
cp .env.example .env      # ajuste tokens se for usar Telegram/Gemini

# 2. subir a stack completa (app, ollama, frontend, redis, prometheus, grafana)
make up

# 3. baixar um modelo no Ollama
docker exec fctebot-ollama ollama pull qwen2.5:3b

# 4. indexar a base de conhecimento
make ingest
```

Serviços:

- API: <http://localhost:8000> (docs em `/docs`)
- Frontend: <http://localhost:3000>
- Grafana: <http://localhost:3001> (admin / `fctebot2025`)
- Prometheus: <http://localhost:9090>

!!! tip "CPU only"
    Use um modelo pequeno (`qwen2.5:0.5b`) e `OLLAMA_TIMEOUT=300`. A latência
    será de segundos — normal sem GPU.

## Opção 2 — Backend sem Docker

```bash
make dev
# equivalente a: pip install -r requirements.txt e uvicorn src.main:app --reload
```

Requer Redis e Ollama acessíveis (via Docker ou instalados localmente).

## Frontend em modo dev

```bash
cd frontend
npm install
npm run dev        # Vite em http://localhost:5173 (proxy para :8000)
```

## Problemas comuns

- **`/query` retorna 503:** índice não criado → `make ingest`.
- **Ollama timeout:** aumente `OLLAMA_TIMEOUT`; use modelo menor.
- **Porta ocupada:** ajuste as portas no `docker-compose.yml`.

Mais em [Operação → Incidentes](../operacao/incidentes.md).
