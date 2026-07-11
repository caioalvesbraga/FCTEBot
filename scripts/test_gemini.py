#!/usr/bin/env python3
"""
Testa conectividade com a API Gemini usando as variáveis do .env.

Uso:
  python scripts/test_gemini.py
  python scripts/test_gemini.py --try-all-models
  docker exec fctebot-app python scripts/test_gemini.py --try-all-models
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Garantir que o módulo src seja encontrado independente do diretório de execução
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from src.config import get_settings

# Modelos ativos na API v1beta (2026)
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def _hint_for_error(status: int, body: str) -> str:
    if "API_KEY_SERVICE_BLOCKED" in body:
        return (
            "\nDica: restrinja a chave a 'Generative Language API' (Gemini) no AI Studio "
            "ou Google Cloud Console → Credentials → Edit API key → API restrictions"
        )
    if status == 400:
        return "\nDica: modelo não disponível ou nome incorreto"
    if status == 401:
        return "\nDica: chave inválida ou expirada — gere uma nova no AI Studio"
    if status == 403:
        return "\nDica: API bloqueada para esta chave — verifique restrições no AI Studio"
    if status == 429:
        if "prepayment credits are depleted" in body.lower():
            return (
                "\nDica: créditos pré-pagos do projeto AI Studio esgotados.\n"
                "   → https://ai.studio/projects → selecione o projeto → Billing / Add credits\n"
                "   → Ou crie um projeto novo com tier gratuito (se disponível)\n"
                "   → Para o TCC: use LLM_STRATEGY=local_only (Ollama)"
            )
        if "limit: 0" in body:
            return (
                "\nDica: cota free tier = 0 para este modelo/conta. Opções:\n"
                "   1. Verifique uso em https://ai.dev/rate-limit\n"
                "   2. Aguarde reset diário (meia-noite PT)\n"
                "   3. Ative billing no Google Cloud\n"
                "   4. Use LLM_STRATEGY=local_only (Ollama) — ideal para o TCC"
            )
        return "\nDica: rate limit / cota esgotada — aguarde ou verifique billing em ai.studio/projects"
    return ""


async def _test_model(client: httpx.AsyncClient, model: str, api_key: str) -> tuple[int, str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": "Responda apenas: OK"}]}],
        "generationConfig": {"maxOutputTokens": 10},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    resp = await client.post(url, json=payload, headers=headers)
    return resp.status_code, resp.text


async def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico da API Gemini")
    parser.add_argument(
        "--try-all-models",
        action="store_true",
        help="Testa vários modelos quando o configurado falha por cota",
    )
    args = parser.parse_args()

    settings = get_settings()

    print("=== Diagnóstico Gemini ===")
    print(f"Modelo configurado: {settings.gemini_model}")
    print(f"LLM_STRATEGY: {settings.llm_strategy}")

    if not settings.has_gemini:
        print("\n❌ GEMINI_API_KEY não configurada no .env")
        print("   Obtenha em: https://aistudio.google.com/app/apikey")
        return 1

    key = settings.gemini_api_key.strip()
    masked = f"{key[:10]}...{key[-4:]}" if len(key) > 14 else "(muito curta)"
    print(f"Chave: {masked} (tipo: {settings.gemini_key_type})")

    if not settings.gemini_key_valid:
        print("\n❌ Formato de chave desconhecido!")
        print("   Chaves AI Studio válidas começam com AIza... (legado) ou AQ.... (auth key)")
        return 1

    models_to_test = [settings.gemini_model]
    if args.try_all_models:
        models_to_test = list(dict.fromkeys([settings.gemini_model, *FALLBACK_MODELS]))

    print(f"\n✅ Autenticação OK — chave {settings.gemini_key_type} aceita pela API")
    print(f"Testando {len(models_to_test)} modelo(s)...\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for model in models_to_test:
                print(f"  → {model} ... ", end="", flush=True)
                status, body = await _test_model(client, model, key)

                if status == 200:
                    data = json.loads(body)
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    print(f"✅ OK — respondeu {text.strip()!r}")
                    if model != settings.gemini_model:
                        print(f"\n💡 Use no .env: GEMINI_MODEL={model}")
                    return 0

                if status == 429 and "prepayment credits are depleted" in body.lower():
                    print("❌ créditos pré-pagos esgotados")
                elif status == 429 and "limit: 0" in body:
                    print("❌ cota free tier = 0")
                elif status == 429:
                    print("❌ rate limit / cota esgotada")
                else:
                    print(f"❌ HTTP {status}")

            # Nenhum modelo funcionou — mostrar detalhe do modelo principal
            print(f"\n❌ Nenhum modelo disponível com cota free tier nesta conta.")
            status, body = await _test_model(client, settings.gemini_model, key)
            print(f"\nDetalhe ({settings.gemini_model}, HTTP {status}):")
            print(body[:800])
            print(_hint_for_error(status, body))
            return 1

    except httpx.TimeoutException:
        print("\n❌ Timeout — verifique conectividade de rede do container")
        return 1
    except Exception as e:
        print(f"\n❌ Erro: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
