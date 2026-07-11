# FCTEBot v2.0 — Assistente Virtual Educacional

> **TCC — Engenharia de Software | UnB/FCTE**  
> Autor: Caio Felipe Alves Braga  
> Orientador: Prof. Dr. Fabiano A. Soares  
> 
> *Otimização de Arquitetura RAG para Assistente Virtual Educacional:  
> Uma Abordagem Local-First com Modelos de Linguagem de Código Aberto*

---

## Visão Geral

O FCTEBot v2.0 é um chatbot educacional para estudantes da FCTE/UnB que responde dúvidas acadêmicas usando **Retrieval-Augmented Generation (RAG)** com infraestrutura completamente local.

### Comparação com o Protótipo Original

| Dimensão | Baseline (v1) | FCTEBot Otimizado (v2) |
|----------|---------------|------------------------|
| LLM | Google Gemini API | **Qwen2.5:3b local** + fallback Gemini |
| Banco Vetorial | Pinecone (cloud) | **FAISS local** |
| Busca | Vetorial apenas | **TF-IDF + FAISS + RRF** (híbrida) |
| Re-ranking | Nenhum | **Cross-encoder multilingual** |
| Cache | Nenhum | **Redis L1/L2** (hit rate 40-50%) |
| Latência média | ~4.250ms | ~1.500ms local / <100ms cache |
| Privacidade | Dados no Google | **100% local por padrão** |
| Conformidade LGPD | Parcial | **Privacy by Design** |
| Monitoramento | Logs básicos | **Prometheus + Grafana** |
| Custo/mês | Variável | **Fixo (~R$ 171)** |

---

## Arquitetura em 6 Camadas

```
┌─────────────────────────────────────────────────────────┐
│  Camada 1: Interface       Telegram Bot                  │
├─────────────────────────────────────────────────────────┤
│  Camada 2: API Gateway     FastAPI + Rate Limiting       │
├─────────────────────────────────────────────────────────┤
│  Camada 3: Cache           Redis L1 (exato) + L2 (semân.)│
├─────────────────────────────────────────────────────────┤
│  Camada 4: Retrieval       TF-IDF + FAISS → RRF → Rerank│
├─────────────────────────────────────────────────────────┤
│  Camada 5: Geração LLM     Ollama/Qwen2.5 → Gemini fallb│
├─────────────────────────────────────────────────────────┤
│  Camada 6: Monitoramento   Prometheus + Grafana          │
└─────────────────────────────────────────────────────────┘
```

### Decisões Arquiteturais (desvios do TCC1)

| Componente | TCC (proposta) | Implementado | Justificativa |
|---|---|---|---|
| LLM local | Llama 3.2 3B | **Qwen2.5:3b** | Melhor suporte ao português em benchmarks multilinguais |
| Embedding | Não especificado | **multilingual-e5-base** | Instruction-tuned para retrieval; prefixos query/passage |
| Re-ranker | ms-marco-MiniLM | **mmarco-mMiniLMv2-L12** | Versão multilingual do mesmo modelo |
| Cache L2 | Redis Vector Search | **numpy cosine in-memory** | Evita dependência do RedisSearch (módulo Enterprise) |
| LLM client | ollama-python | **openai SDK** | Ollama expõe API OpenAI-compatível; facilita migração futura |

---

## Início Rápido

### Pré-requisitos

- Docker e Docker Compose
- 8GB+ RAM (16GB recomendado para GPU)
- 20GB+ espaço em disco (modelos Ollama)

### 1. Configurar

```bash
git clone <repo>
cd FCTEBot

# Copiar e editar variáveis de ambiente
cp .env.example .env
# Editar .env com seus tokens (TELEGRAM_TOKEN, GEMINI_API_KEY)
```

### 2. Subir os serviços

```bash
make up
# ou: docker compose up -d --build
```

### 3. Baixar o modelo LLM

```bash
docker exec fctebot-ollama ollama pull qwen2.5:3b

# Alternativas (menor/maior):
# docker exec fctebot-ollama ollama pull gemma3:4b   (melhor qualidade)
# docker exec fctebot-ollama ollama pull phi4-mini    (mais leve)
```

### 4. Adicionar documentos e indexar

```bash
# Copiar documentos da FCTE para knowledge_base/
cp /seus/documentos/*.pdf knowledge_base/

# Executar ingestão
make ingest
```

### 5. Verificar funcionamento

```bash
# Health check
curl http://localhost:8000/health

# Testar uma consulta
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual o prazo para trancamento parcial?"}'
```

### 6. Dashboards

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| API Docs | http://localhost:8000/docs | — |
| Grafana | http://localhost:3000 | admin / fctebot2025 |
| Prometheus | http://localhost:9090 | — |

---

## Desenvolvimento sem Docker

```bash
# Instalar dependências
pip install -r requirements.txt

# Copiar .env
cp .env.example .env

# Assumindo Redis e Ollama rodando localmente:
REDIS_URL=redis://localhost:6379/0 \
OLLAMA_BASE_URL=http://localhost:11434 \
uvicorn src.main:app --reload --port 8000
```

---

## Estrutura do Projeto

```
FCTEBot/
├── src/
│   ├── config.py               # Configuração centralizada (Pydantic Settings)
│   ├── main.py                 # Entry point FastAPI
│   ├── rag/
│   │   ├── ingestion.py        # Pipeline de ingestão (PDF/MD/TXT/DOCX)
│   │   ├── retrieval.py        # Recuperação híbrida TF-IDF + FAISS + RRF
│   │   ├── reranker.py         # Cross-encoder multilingual
│   │   ├── generator.py        # Ollama + Gemini fallback + Circuit Breaker
│   │   └── pipeline.py         # Orquestrador do pipeline RAG
│   ├── cache/
│   │   └── redis_cache.py      # Cache L1 (SHA-256) + L2 (cosine similarity)
│   ├── monitoring/
│   │   └── metrics.py          # Métricas Prometheus
│   ├── api/
│   │   ├── routes.py           # Endpoints FastAPI
│   │   └── middleware.py       # Rate limiting + logging
│   └── bot/
│       └── telegram_handler.py # Bot Telegram assíncrono
├── evaluation/
│   ├── questions.json          # Dataset: 25 perguntas, 14 categorias
│   ├── evaluate.py             # Avaliação com métricas e RAGAS
│   └── baseline_comparison.py # Benchmark comparativo baseline vs. otimizado
├── monitoring/
│   ├── prometheus.yml          # Configuração do Prometheus
│   ├── alerts.yml              # Regras de alertas
│   └── grafana/
│       ├── dashboards/         # Dashboard JSON pré-configurado
│       └── provisioning/       # Auto-configuração datasource
├── scripts/
│   └── ingest.py               # CLI de ingestão
├── knowledge_base/             # Documentos da FCTE (adicionar aqui)
├── data/                       # Índices gerados (FAISS, TF-IDF, metadados)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── Makefile
```

---

## Comandos Make

```bash
make setup    # Configura ambiente inicial
make up       # Sobe todos os serviços
make down     # Para todos os serviços
make logs     # Logs em tempo real
make ingest   # Re-indexa base de conhecimento
make eval     # Executa avaliação RAGAS
make baseline # Benchmark comparativo
make clean    # Remove índices gerados
```

---

## Avaliação

```bash
# Avaliação completa (métricas de latência + RAGAS)
make eval

# Benchmark comparativo com baseline
make baseline

# Resultados salvos em evaluation/results/
```

### Métricas coletadas

| Métrica | Meta (RNF) | Instrumento |
|---------|-----------|-------------|
| Latência P95 | ≤ 5s | Prometheus + evaluate.py |
| Taxa de sucesso | ≥ 95% | evaluate.py |
| Cache hit rate | ≥ 15% | Prometheus |
| Fallback rate | ≤ 20% | Prometheus |
| Faithfulness | — | RAGAS |
| Answer Relevancy | — | RAGAS |
| Context Recall | — | RAGAS |

---

## Configuração do Webhook Telegram (Produção)

```bash
# No .env:
TELEGRAM_WEBHOOK_URL=https://seu-dominio.com.br

# O bot configura o webhook automaticamente ao iniciar
# Para remover: DELETE /webhook via BotFather
```

---

## Licença

MIT License — Uso acadêmico e pesquisa sem restrições.

Modelos utilizados:
- **Qwen2.5** — Apache 2.0
- **multilingual-e5-base** — MIT
- **mmarco-mMiniLMv2** — Apache 2.0
- **Gemma 3** (alternativo) — Gemma Terms of Use (uso acadêmico permitido)
