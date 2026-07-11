# Avaliação de qualidade

A qualidade do FCTEBot foi avaliada por duas frentes: **avaliação automática**
(RAGAS + baseline) e **validação com usuários** (questionário). Os artefatos
ficam em `evaluation/`.

## Dataset de avaliação

- `evaluation/questions.json` — **25 perguntas** cobrindo 14 categorias
  (matrícula, estágio, TCC, trancamento, horas complementares, etc.).
- Serve como *golden set* para medir regressões após mudanças na base ou no
  pipeline.

## Avaliação automática (RAGAS)

`evaluation/evaluate.py` calcula métricas RAGAS e de latência:

| Métrica | O que mede |
|---|---|
| `faithfulness` | A resposta é fiel ao contexto recuperado (sem alucinação)? |
| `answer_relevancy` | A resposta é relevante à pergunta? |
| `context_recall` | O contexto recuperou a informação necessária? |
| `context_precision` | O contexto recuperado é enxuto/relevante? |
| Latência P50/P95 | Tempo de resposta |

```bash
make eval        # ou: python evaluation/evaluate.py
```

Resultados são gravados em `evaluation/results/` (gitignored).

## Comparação baseline

`evaluation/baseline_comparison.py` compara a arquitetura otimizada (v2) com a
baseline (v1), gerando gráficos opcionais (matplotlib).

```bash
make baseline
```

## Validação com usuários

Foi aplicado um questionário (Google Forms) com estudantes, avaliando as
respostas do bot em perguntas reais. As respostas ficam no CSV de validação
(ex.: `Formulário de validação FCTEBot TCC2 (respostas).csv`). Esse processo
guiou correções na base de conhecimento (ex.: prazo do TCE, trancamentos,
contato da coordenação).

> **Continuidade:** ao alterar o pipeline ou a base, rode `make eval` e compare
> com a última execução para detectar regressões antes de publicar.

> **TODO:** RAGAS ficou reservado para trabalhos futuros no TCC; documentar aqui
> os números da última execução oficial quando disponível.
