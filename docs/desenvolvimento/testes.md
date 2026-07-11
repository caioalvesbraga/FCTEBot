# Testes

!!! warning "Estado atual"
    O projeto **não possui testes automatizados** (`tests/` inexistente). Há
    apenas **avaliação empírica** em `evaluation/` (RAGAS e baseline), que não é
    executada em CI. Esta página propõe a estratégia recomendada para dar
    continuidade.

## Estratégia proposta

### 1. Testes unitários (`tests/unit/`)

Alvos de maior valor:

- `rag/retrieval.py` — fusão RRF, ordenação, pesos.
- `rag/pipeline.py` — lógica de cache hit/miss, seleção de modo.
- `cache/redis_cache.py` — L1/L2 (com `fakeredis` ou Redis de teste).
- `config.py` — validação de variáveis e da chave Gemini.
- `generator.py` — guardrails (temas proibidos → resposta padrão).

Ferramenta sugerida: **pytest** + **pytest-asyncio** (código é async).

### 2. Testes de integração (`tests/integration/`)

- Subir a API com um índice pequeno de fixtures e validar `POST /query`.
- Mockar Ollama/Gemini para não depender de rede.
- Validar `/health` nos estados `ok`/`degraded`/`error`.

### 3. Avaliação de qualidade (já existe)

Ver [Qualidade → Avaliação](../qualidade/avaliacao.md): `evaluate.py` (RAGAS) e
`baseline_comparison.py`. Recomenda-se rodá-los antes de mudanças grandes na base
ou no pipeline, como *regression gate*.

## Como começar (esqueleto)

```bash
pip install pytest pytest-asyncio fakeredis httpx
mkdir -p tests/unit tests/integration
# crie tests/unit/test_retrieval.py, etc.
pytest -q
```

> **TODO (continuidade):**
> - Criar a pasta `tests/` com os primeiros casos (retrieval e cache).
> - Definir cobertura mínima (ex.: 60% nos módulos `rag/` e `cache/`).
> - Adicionar `pytest` ao CI (ver [Contribuindo](contribuindo.md)).
