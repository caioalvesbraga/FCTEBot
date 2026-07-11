# ADR-0003 — Cache multinível com Redis

- **Status:** Aceito
- **Data:** 2026-06-01
- **Decisores:** Caio Braga

## Contexto

A geração local em CPU é cara (segundos por resposta). Muitas perguntas de
estudantes se repetem literalmente ou com pequenas variações ("como faço
matrícula?" vs. "como me matriculo?"). Recomputar o pipeline inteiro a cada
pergunta desperdiça recursos e piora a latência percebida.

## Decisão

Implementar um **cache multinível** em Redis:

- **L1 (exato):** chave = hash da pergunta normalizada. Responde instantaneamente
  a repetições literais. TTL `CACHE_L1_TTL` (7 dias).
- **L2 (semântico):** compara o embedding da nova pergunta com perguntas
  anteriores; reaproveita a resposta se a similaridade de cosseno ≥
  `CACHE_L2_SIMILARITY_THRESHOLD` (0.95). TTL `CACHE_L2_TTL` (30 dias).

## Alternativas consideradas

- **Sem cache:** simples, porém latência e custo altos sob repetição.
- **Apenas cache exato (L1):** não cobre variações de linguagem naturais.
- **Cache em memória do processo:** perde-se ao reiniciar o contêiner e não
  compartilha entre réplicas.

## Consequências

- **Positivas:** grande redução de latência e carga do LLM em perguntas
  recorrentes; persistência entre reinícios.
- **Trade-offs:** risco de servir resposta **desatualizada** após mudança na base
  de conhecimento — por isso o cache **deve ser limpo** após reingestão
  (`redis-cli FLUSHALL`; ver [Runbook](../../operacao/runbook.md)).
- **Riscos:** limiar L2 muito baixo pode retornar resposta de pergunta diferente
  — mitigado com 0.95 e monitoramento.

## Referências

- `src/cache/redis_cache.py`
- Variáveis: `REDIS_URL`, `CACHE_L1_TTL`, `CACHE_L2_TTL`, `CACHE_L2_SIMILARITY_THRESHOLD`
