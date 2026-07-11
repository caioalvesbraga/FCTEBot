"""
Benchmark comparativo: Arquitetura Baseline vs. FCTEBot Otimizado.

Reproduz a metodologia do TCC:
  - Mesmas 25 perguntas do dataset de avaliação
  - Mede latência, taxa de sucesso, modo de geração
  - Gera tabela comparativa e gráficos (boxplot, performance por categoria)

Alinhado com a metodologia da Seção 3.2 do TCC.
"""
from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx
from loguru import logger

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib não instalado — gráficos desativados")

RESULTS_DIR = Path("evaluation/results")
API_BASE = "http://localhost:8000"


async def benchmark_optimized(questions: list[dict]) -> list[dict]:
    """Executa benchmark no sistema otimizado (FCTEBot v2)."""
    results = []
    async with httpx.AsyncClient() as client:
        for q in questions:
            start = time.perf_counter()
            try:
                resp = await client.post(
                    f"{API_BASE}/query",
                    json={"query": q["question"], "user_id": "benchmark"},
                    timeout=60.0,
                )
                elapsed = (time.perf_counter() - start) * 1000
                data = resp.json()
                results.append({
                    **q,
                    "latency_ms": elapsed,
                    "success": resp.status_code == 200,
                    "mode": data.get("mode", "unknown"),
                    "cache_hit": data.get("cache_hit", "none"),
                    "confidence": data.get("confidence", 0),
                })
            except Exception as e:
                results.append({
                    **q,
                    "latency_ms": (time.perf_counter() - start) * 1000,
                    "success": False,
                    "mode": "error",
                    "cache_hit": "none",
                    "confidence": 0,
                })
            await asyncio.sleep(1.0)
    return results


def generate_comparison_table(optimized: list[dict]) -> str:
    """Gera tabela Markdown comparativa (baseline vem do TCC1)."""
    # Valores do baseline do TCC (medidos com Gemini + Pinecone/TF-IDF)
    BASELINE = {
        "latency_mean_ms": 4250,
        "latency_median_ms": 4400,
        "latency_stdev_ms": 1430,
        "latency_p95_ms": 6800,
        "success_rate": 1.00,
        "cost_per_year_brl": 600,
        "cache_hit_rate": 0.0,
        "fallback_rate": 0.0,
        "local_processing": 0.0,
    }

    suc = [r for r in optimized if r["success"]]
    lats = [r["latency_ms"] for r in suc]

    def pct(lst, p):
        s = sorted(lst)
        return s[int(len(s) * p / 100)]

    OPT = {
        "latency_mean_ms": statistics.mean(lats) if lats else 0,
        "latency_median_ms": statistics.median(lats) if lats else 0,
        "latency_stdev_ms": statistics.stdev(lats) if len(lats) > 1 else 0,
        "latency_p95_ms": pct(lats, 95) if lats else 0,
        "success_rate": len(suc) / len(optimized) if optimized else 0,
        "cost_per_year_brl": 2052,  # conforme análise do TCC
        "cache_hit_rate": sum(1 for r in optimized if r["cache_hit"] != "none") / len(optimized),
        "fallback_rate": sum(1 for r in optimized if r["mode"] == "fallback") / len(optimized),
        "local_processing": sum(1 for r in optimized if r["mode"] == "local") / len(optimized),
    }

    def delta(opt, base, lower_is_better=True):
        if base == 0:
            return "N/A"
        pct_change = (opt - base) / base * 100
        symbol = "▼" if (pct_change < 0) == lower_is_better else "▲"
        return f"{symbol} {abs(pct_change):.1f}%"

    table = [
        "# Tabela Comparativa: Baseline vs. FCTEBot Otimizado\n",
        "| Dimensão | Protótipo Baseline | FCTEBot Otimizado | Variação |",
        "|---|---|---|---|",
        f"| Latência Média | {BASELINE['latency_mean_ms']:.0f}ms | {OPT['latency_mean_ms']:.0f}ms | {delta(OPT['latency_mean_ms'], BASELINE['latency_mean_ms'])} |",
        f"| Latência Mediana | {BASELINE['latency_median_ms']:.0f}ms | {OPT['latency_median_ms']:.0f}ms | {delta(OPT['latency_median_ms'], BASELINE['latency_median_ms'])} |",
        f"| Latência P95 | {BASELINE['latency_p95_ms']:.0f}ms | {OPT['latency_p95_ms']:.0f}ms | {delta(OPT['latency_p95_ms'], BASELINE['latency_p95_ms'])} |",
        f"| Desvio Padrão | {BASELINE['latency_stdev_ms']:.0f}ms | {OPT['latency_stdev_ms']:.0f}ms | {delta(OPT['latency_stdev_ms'], BASELINE['latency_stdev_ms'])} |",
        f"| Taxa de Sucesso | {BASELINE['success_rate']*100:.1f}% | {OPT['success_rate']*100:.1f}% | {delta(OPT['success_rate'], BASELINE['success_rate'], lower_is_better=False)} |",
        f"| Cache Hit Rate | {BASELINE['cache_hit_rate']*100:.1f}% | {OPT['cache_hit_rate']*100:.1f}% | {delta(OPT['cache_hit_rate'], max(BASELINE['cache_hit_rate'], 0.001), lower_is_better=False)} |",
        f"| Custo Anual (R$) | R$ {BASELINE['cost_per_year_brl']:.0f} | R$ {OPT['cost_per_year_brl']:.0f} | {delta(OPT['cost_per_year_brl'], BASELINE['cost_per_year_brl'])} |",
        f"| Processamento Local | {BASELINE['local_processing']*100:.1f}% | {OPT['local_processing']*100:.1f}% | {delta(OPT['local_processing'], max(BASELINE['local_processing'], 0.001), lower_is_better=False)} |",
    ]
    return "\n".join(table)


def plot_boxplot(optimized: list[dict], baseline_latencies: list[float] = None) -> None:
    """Gera boxplot comparativo de latências (replicando Figura 4 do TCC)."""
    if not HAS_MATPLOTLIB:
        return

    opt_lats = [r["latency_ms"] for r in optimized if r["success"]]

    # Latências simuladas do baseline (distribuição similar ao TCC)
    if baseline_latencies is None:
        import random
        random.seed(42)
        baseline_latencies = [random.gauss(4250, 1430) for _ in range(25)]
        baseline_latencies = [max(1000, l) for l in baseline_latencies]

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Boxplot
    axes[0].boxplot(
        [baseline_latencies, opt_lats],
        labels=["Baseline\n(Gemini + Pinecone)", "FCTEBot Otimizado\n(Local + FAISS)"],
        patch_artist=True,
        boxprops=dict(facecolor="lightcoral", color="darkred"),
        medianprops=dict(color="darkred", linewidth=2),
    )
    axes[0].set_ylabel("Latência (ms)")
    axes[0].set_title("Comparação de Latências: Baseline vs. Otimizado")
    axes[0].axhline(y=5000, color="orange", linestyle="--", label="Limite RNF001 (5s)")
    axes[0].legend()

    # Por categoria
    by_cat: dict[str, list] = {}
    for r in optimized:
        if r["success"]:
            by_cat.setdefault(r["category"], []).append(r["latency_ms"])

    cats = sorted(by_cat.keys(), key=lambda c: statistics.mean(by_cat[c]), reverse=True)
    means = [statistics.mean(by_cat[c]) for c in cats]
    colors = ["red" if m > 5000 else "green" for m in means]

    axes[1].barh(cats, means, color=colors)
    axes[1].axvline(x=5000, color="orange", linestyle="--", label="Limite 5s")
    axes[1].set_xlabel("Latência Média (ms)")
    axes[1].set_title("Latência por Categoria Temática")
    axes[1].legend()

    plt.tight_layout()
    output_path = RESULTS_DIR / "comparison_plots.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    logger.info(f"Gráficos salvos: {output_path}")
    plt.close()


async def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open("evaluation/questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)["questions"]

    logger.info("Iniciando benchmark comparativo...")

    # Verificar API
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"{API_BASE}/health", timeout=5)
    except Exception as e:
        logger.error(f"API indisponível: {e}")
        return

    # Benchmark sistema otimizado
    logger.info("Testando FCTEBot Otimizado...")
    opt_results = await benchmark_optimized(questions)

    # Gerar tabela comparativa
    table = generate_comparison_table(opt_results)
    print("\n" + table)

    # Gerar gráficos
    plot_boxplot(opt_results)

    # Salvar
    ts = time.strftime("%Y%m%d_%H%M%S")
    with open(RESULTS_DIR / f"benchmark_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(opt_results, f, ensure_ascii=False, indent=2)
    with open(RESULTS_DIR / f"comparison_table_{ts}.md", "w", encoding="utf-8") as f:
        f.write(table)

    logger.success("Benchmark concluído.")


if __name__ == "__main__":
    asyncio.run(main())
