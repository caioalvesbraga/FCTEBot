"""
Avaliação do FCTEBot usando o framework RAGAS.

Métricas coletadas (alinhadas com o TCC):
  - faithfulness       : resposta fundamentada apenas no contexto?
  - answer_relevancy   : resposta aborda a pergunta?
  - context_recall     : contexto contém a informação necessária?
  - context_precision  : contexto recuperado é relevante (sem ruído)?
  - latency_p50/p95    : latência em percentis
  - success_rate       : taxa de respostas sem erro

Uso:
  python evaluation/evaluate.py [--baseline] [--output results/]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger


RESULTS_DIR = Path("evaluation/results")
API_BASE = "http://localhost:8000"


# ──────────────────────────────────────────────────────────────────────────────
# Coleta de dados brutos
# ──────────────────────────────────────────────────────────────────────────────

async def run_query(client: httpx.AsyncClient, question: dict) -> dict:
    """Executa uma pergunta via API e retorna resultado com metadados."""
    start = time.perf_counter()
    try:
        resp = await client.post(
            f"{API_BASE}/query",
            json={"query": question["question"], "user_id": "eval"},
            timeout=60.0,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        data = resp.json()
        return {
            "id": question["id"],
            "category": question["category"],
            "complexity": question["complexity"],
            "question": question["question"],
            "response": data["response"],
            "sources": data["sources"],
            "mode": data["mode"],
            "confidence": data["confidence"],
            "api_latency_ms": data["latency_ms"],
            "total_latency_ms": elapsed_ms,
            "cache_hit": data["cache_hit"],
            "model_used": data["model_used"],
            "success": True,
            "error": None,
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(f"Erro em {question['id']}: {e}")
        return {
            "id": question["id"],
            "category": question["category"],
            "complexity": question["complexity"],
            "question": question["question"],
            "response": "",
            "sources": [],
            "mode": "error",
            "confidence": 0.0,
            "api_latency_ms": elapsed_ms,
            "total_latency_ms": elapsed_ms,
            "cache_hit": "none",
            "model_used": "none",
            "success": False,
            "error": str(e),
        }


async def collect_responses(questions: list[dict], delay_s: float = 2.0) -> list[dict]:
    """Coleta respostas para todas as perguntas com delay entre cada uma."""
    results = []
    async with httpx.AsyncClient() as client:
        for i, q in enumerate(questions, 1):
            logger.info(f"[{i}/{len(questions)}] {q['id']}: {q['question'][:60]}...")
            result = await run_query(client, q)
            results.append(result)
            if i < len(questions):
                await asyncio.sleep(delay_s)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Análise estatística
# ──────────────────────────────────────────────────────────────────────────────

def compute_statistics(results: list[dict]) -> dict:
    """Calcula estatísticas descritivas sobre os resultados."""
    successful = [r for r in results if r["success"]]
    latencies = [r["total_latency_ms"] for r in successful]
    confidences = [r["confidence"] for r in successful]

    def pct(lst, p):
        sorted_lst = sorted(lst)
        idx = int(len(sorted_lst) * p / 100)
        return sorted_lst[min(idx, len(sorted_lst) - 1)]

    # Por categoria
    by_category: dict[str, list] = {}
    for r in successful:
        cat = r["category"]
        by_category.setdefault(cat, []).append(r["total_latency_ms"])

    # Por complexidade
    by_complexity: dict[str, list] = {}
    for r in successful:
        c = r["complexity"]
        by_complexity.setdefault(c, []).append(r["total_latency_ms"])

    # Por modo de geração
    mode_counts: dict[str, int] = {}
    for r in results:
        mode_counts[r["mode"]] = mode_counts.get(r["mode"], 0) + 1

    cache_hits = sum(1 for r in results if r["cache_hit"] in ("l1", "l2"))
    fallbacks = sum(1 for r in results if r["mode"] == "fallback")

    return {
        "total_questions": len(results),
        "successful": len(successful),
        "success_rate": round(len(successful) / len(results), 4) if results else 0,
        "latency": {
            "mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
            "median_ms": round(statistics.median(latencies), 1) if latencies else 0,
            "stdev_ms": round(statistics.stdev(latencies), 1) if len(latencies) > 1 else 0,
            "p50_ms": round(pct(latencies, 50), 1) if latencies else 0,
            "p95_ms": round(pct(latencies, 95), 1) if latencies else 0,
            "p99_ms": round(pct(latencies, 99), 1) if latencies else 0,
            "min_ms": round(min(latencies), 1) if latencies else 0,
            "max_ms": round(max(latencies), 1) if latencies else 0,
        },
        "confidence": {
            "mean": round(statistics.mean(confidences), 3) if confidences else 0,
            "min": round(min(confidences), 3) if confidences else 0,
        },
        "cache": {
            "hits": cache_hits,
            "hit_rate": round(cache_hits / len(results), 4) if results else 0,
        },
        "fallbacks": {
            "count": fallbacks,
            "rate": round(fallbacks / len(results), 4) if results else 0,
        },
        "by_mode": mode_counts,
        "by_category": {
            cat: {
                "count": len(lats),
                "mean_ms": round(statistics.mean(lats), 1),
            }
            for cat, lats in sorted(by_category.items(), key=lambda x: statistics.mean(x[1]), reverse=True)
        },
        "by_complexity": {
            c: {
                "count": len(lats),
                "mean_ms": round(statistics.mean(lats), 1),
            }
            for c, lats in by_complexity.items()
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Avaliação RAGAS (opcional — requer LLM para judge)
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_with_ragas(results: list[dict], questions_with_gt: Optional[list[dict]] = None) -> Optional[dict]:
    """
    Calcula métricas RAGAS para avaliar qualidade das respostas RAG.
    Requer que as perguntas tenham ground_truth no dataset.
    """
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
        )
        from datasets import Dataset
    except ImportError:
        logger.warning("ragas não instalado. Pulando avaliação RAGAS.")
        return None

    if not questions_with_gt:
        logger.warning("Sem ground_truth no dataset. Pulando avaliação RAGAS.")
        return None

    # Preparar dataset RAGAS
    gt_map = {q["id"]: q.get("ground_truth", "") for q in questions_with_gt}
    ragas_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for r in results:
        if not r["success"] or not gt_map.get(r["id"]):
            continue
        ragas_data["question"].append(r["question"])
        ragas_data["answer"].append(r["response"])
        ragas_data["contexts"].append(r["sources"])  # simplificação
        ragas_data["ground_truth"].append(gt_map[r["id"]])

    if not ragas_data["question"]:
        return None

    dataset = Dataset.from_dict(ragas_data)
    try:
        score = ragas_evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )
        return score.to_pandas().to_dict(orient="list")
    except Exception as e:
        logger.error(f"Erro na avaliação RAGAS: {e}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main(output_dir: str = "evaluation/results") -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Carregar dataset
    with open("evaluation/questions.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)
    questions = dataset["questions"]

    logger.info(f"Iniciando avaliação: {len(questions)} perguntas")
    logger.info(f"API: {API_BASE}")

    # Verificar se API está disponível
    try:
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{API_BASE}/health", timeout=10)
            if health.status_code != 200:
                logger.error(f"API indisponível: {health.status_code}")
                return
    except Exception as e:
        logger.error(f"Não foi possível conectar à API: {e}")
        return

    # Coletar respostas
    results = await collect_responses(questions, delay_s=2.0)

    # Calcular estatísticas
    stats = compute_statistics(results)

    # Salvar resultados
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"results_{timestamp}.json"
    stats_file = RESULTS_DIR / f"stats_{timestamp}.json"

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Exibir resumo
    print("\n" + "=" * 60)
    print("RESULTADOS DA AVALIAÇÃO FCTEBot")
    print("=" * 60)
    print(f"Taxa de sucesso:     {stats['success_rate']*100:.1f}% ({stats['successful']}/{stats['total_questions']})")
    print(f"Latência média:      {stats['latency']['mean_ms']:.0f}ms")
    print(f"Latência P95:        {stats['latency']['p95_ms']:.0f}ms")
    print(f"Latência mediana:    {stats['latency']['median_ms']:.0f}ms")
    print(f"Desvio padrão:       {stats['latency']['stdev_ms']:.0f}ms")
    print(f"Cache hit rate:      {stats['cache']['hit_rate']*100:.1f}%")
    print(f"Fallback rate:       {stats['fallbacks']['rate']*100:.1f}%")
    print(f"Confiança média:     {stats['confidence']['mean']:.3f}")
    print()
    print("Por modo de geração:")
    for mode, count in stats["by_mode"].items():
        print(f"  {mode}: {count}")
    print()
    print("Top 5 categorias mais lentas:")
    for cat, data in list(stats["by_category"].items())[:5]:
        print(f"  {cat}: {data['mean_ms']:.0f}ms (n={data['count']})")
    print("=" * 60)
    print(f"\nResultados salvos em:")
    print(f"  {results_file}")
    print(f"  {stats_file}")

    logger.success("Avaliação concluída.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Avaliação FCTEBot")
    parser.add_argument("--output", default="evaluation/results", help="Diretório de saída")
    args = parser.parse_args()
    asyncio.run(main(args.output))
