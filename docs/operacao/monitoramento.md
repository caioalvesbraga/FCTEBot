# Monitoramento

O FCTEBot expõe métricas no padrão **Prometheus** e traz dashboards e alertas
provisionados para o **Grafana**.

## Componentes

- **Métricas:** `src/monitoring/metrics.py` — counters/histograms com prefixo
  `fctebot_*`, servidos na porta `METRICS_PORT` (padrão 9090) e/ou em `/metrics`.
- **Prometheus:** `monitoring/prometheus.yml` (coleta) e `monitoring/alerts.yml`
  (regras de alerta).
- **Grafana:** dashboard `monitoring/grafana/dashboards/fctebot.json`, com
  provisioning automático em `monitoring/grafana/provisioning/`.

Acesso em desenvolvimento: Grafana em `http://localhost:3001`
(admin / `fctebot2025`), Prometheus em `http://localhost:9090`.

## Métricas principais

> **TODO:** confirmar os nomes exatos em `src/monitoring/metrics.py` e completar
> a tabela.

| Métrica (prefixo `fctebot_`) | Tipo | O que mede |
|---|---|---|
| `requests_total` | counter | Total de consultas processadas |
| `request_latency_seconds` | histogram | Latência do pipeline (P50/P95) |
| `cache_hits_total` | counter | Acertos de cache (L1/L2) |
| `llm_fallback_total` | counter | Quantas vezes recorreu ao Gemini |
| `errors_total` | counter | Erros no pipeline |

## Alertas configurados

Definidos em `monitoring/alerts.yml` (ex.: latência P95 alta, taxa de erro,
baixo *cache hit*, uso excessivo de *fallback*).

> **TODO (continuidade):** documentar cada regra de alerta, seus limiares e a
> ação esperada (link para o playbook em [Incidentes](incidentes.md)); configurar
> um canal de notificação (e-mail/Telegram) no Grafana.

## O que observar no dia a dia

- **Latência P95** — se subir muito em GPU, verifique o modelo/OLLAMA.
- **Taxa de fallback** — alta pode indicar problema no Ollama ou confiança baixa.
- **Cache hit ratio** — baixo demais após reindexação é esperado (cache limpo).
- **Erros** — correlacione com `docker logs fctebot-app`.
