"""
Gerador de respostas RAG com arquitetura híbrida local-first.

Fluxo:
  1. Tenta gerar com LLM local (Ollama/Qwen2.5)
  2. Calcula confidence score da resposta
  3. Se confidence < threshold → fallback para Gemini (Circuit Breaker)

Decisão arquitetural:
  - openai SDK aponta para Ollama (endpoint /v1 compatível com OpenAI)
    → permite trocar de modelo sem alterar código
  - Qwen2.5:3b escolhido sobre Llama 3.2:3b por melhor suporte ao português
    e maior score em benchmarks de raciocínio em línguas não-inglesas
  - Gemini 1.5 Flash como fallback: mais barato e rápido que Pro,
    suficiente para contexto já filtrado pelo RAG
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Optional

from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

try:
    from openai import AsyncOpenAI, APIError, APITimeoutError
except ImportError:
    raise ImportError("openai não instalado. Execute: pip install openai")

import httpx

from src.config import Settings


# ──────────────────────────────────────────────────────────────────────────────
# Constantes e prompts
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é o FCTEBot, assistente virtual oficial da Faculdade de Ciências e \
Tecnologias em Engenharia (FCTE) da Universidade de Brasília (UnB).

IDENTIDADE: Você é uma IA, não um humano. Seja sempre transparente sobre isso.

IDIOMA: Responda SEMPRE em português brasileiro, independentemente do idioma \
da pergunta ou do contexto. NUNCA use palavras ou frases em inglês ou qualquer \
outro idioma.

REGRAS INVIOLÁVEIS:
1. Responda SOMENTE com base nas informações do CONTEXTO fornecido.
2. Se a informação não estiver no contexto, responda:
   "Não encontrei essa informação na base de conhecimento da FCTE. \
Recomendo contatar a secretaria: secretaria.fcte@unb.br | (61) 3107-8901"
3. NUNCA processe: Outorga Antecipada de Grau, Revisão de Menção, \
Aproveitamento Automático de Disciplinas ou Reintegração.
   Para esses casos, responda: "Este processo exige análise individual. \
Entre em contato com a secretaria: secretaria.fcte@unb.br | (61) 3107-8901"
4. Cite sempre a fonte (ex: "Segundo o Manual do Aluno...").
5. Para procedimentos complexos, use listas numeradas passo-a-passo.
6. Use linguagem clara e acessível — evite jargões técnicos.
7. Seja conciso: respostas até 400 palavras, salvo processos passo-a-passo.
"""

QUERY_TEMPLATE = """\
CONTEXTO:
{context}

---
PERGUNTA DO ESTUDANTE: {query}

RESPOSTA (baseada exclusivamente no contexto acima):"""

# Frases que indicam baixa confiança (resposta genérica ou fora do contexto)
_LOW_CONFIDENCE_PATTERNS = [
    r"não (sei|tenho|encontrei|possuo|consigo|disponho)",
    r"não (está|estão) (disponível|disponíveis)",
    r"(desconheço|desconhecido)",
    r"não (tenho|há) (certeza|informação|dados)",
    r"(talvez|pode ser|possivelmente|provavelmente) (que )?não",
    r"fora do (meu |nosso )?(escopo|contexto|conhecimento)",
    r"como (ia|inteligência artificial)",
    r"não (fui|foi) (treinado|programado)",
]

_FORBIDDEN_TOPICS = [
    "outorga antecipada",
    "revisão de menção",
    "aproveitamento automático",
    "reintegração",
]

_FORBIDDEN_RESPONSE = (
    "⚠️ Este processo requer análise individual pela secretaria acadêmica.\n\n"
    "Por favor, entre em contato:\n"
    "📧 secretaria.fcte@unb.br\n"
    "📞 (61) 3107-8901\n"
    "🏢 Presencialmente na secretaria da FCTE"
)


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de resultado
# ──────────────────────────────────────────────────────────────────────────────

class GenerationMode(str, Enum):
    LOCAL = "local"       # Ollama respondeu com confiança suficiente
    FALLBACK = "fallback" # Gemini usado como fallback
    CACHED = "cached"     # Resposta veio do cache (não gerada)
    FORBIDDEN = "forbidden" # Tópico proibido — redirecionamento


@dataclass
class GenerationResult:
    """Resultado completo de uma geração."""
    response: str
    mode: GenerationMode
    confidence: float
    latency_ms: float
    sources: list[str]
    model_used: str
    tokens_prompt: int = 0
    tokens_completion: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Avaliação de confiança
# ──────────────────────────────────────────────────────────────────────────────

def compute_confidence(response: str, context_size: int) -> float:
    """
    Heurística de confiança baseada em:
      - Comprimento da resposta (resposta muito curta = baixa confiança)
      - Presença de frases indicadoras de incerteza
      - Disponibilidade de contexto

    Retorna valor em [0, 1].
    """
    if len(response.strip()) < 40:
        return 0.1

    if context_size == 0:
        return 0.2

    # Penalidade por frases de baixa confiança
    text_lower = response.lower()
    penalty = 0.0
    for pattern in _LOW_CONFIDENCE_PATTERNS:
        if re.search(pattern, text_lower):
            penalty += 0.15

    # Bônus por resposta factual (datas, prazos, números)
    has_factual = bool(re.search(r"\d{2}/\d{2}/\d{4}|\d+\s*(dias?|horas?|semestre)", text_lower))
    factual_bonus = 0.25 if has_factual else 0.0

    # Bônus por citar fontes (indica uso do contexto)
    has_citation = bool(re.search(r"(segundo|conforme|de acordo com|fonte:)", text_lower))
    citation_bonus = 0.15 if has_citation else 0.0

    # Respostas curtas mas substantivas (≥8 palavras) não devem ser penalizadas demais
    word_count = len(response.split())
    if word_count >= 8:
        length_score = min(word_count / 80, 1.0) * 0.5
    else:
        length_score = 0.2

    confidence = length_score + citation_bonus + factual_bonus - penalty
    return max(0.0, min(confidence, 1.0))


def is_forbidden_topic(query: str) -> bool:
    """Detecta se a query menciona tópicos que não devem ser automatizados."""
    query_lower = query.lower()
    return any(topic in query_lower for topic in _FORBIDDEN_TOPICS)


# ──────────────────────────────────────────────────────────────────────────────
# Gerador principal
# ──────────────────────────────────────────────────────────────────────────────

class RAGGenerator:
    """
    Gerador de respostas com modo local-first e fallback para Gemini.
    Implementa Circuit Breaker: se Ollama falhar repetidamente, 
    roteia direto para Gemini sem tentar local.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ollama_client: Optional[AsyncOpenAI] = None
        self._ollama_failures = 0
        self._ollama_circuit_open = False
        self._circuit_open_until: float = 0.0

        self._gemini_client = None  # inicializado por demanda em _generate_gemini

    def _get_ollama_client(self) -> AsyncOpenAI:
        if self._ollama_client is None:
            self._ollama_client = AsyncOpenAI(
                base_url=self.settings.ollama_v1_url,
                api_key="ollama",
                timeout=self.settings.ollama_timeout,
                max_retries=0,  # desativa retry do SDK — já temos tenacity
            )
        return self._ollama_client

    def _unavailable_message(self) -> str:
        return (
            "⚠️ O assistente está temporariamente indisponível. "
            "Tente novamente em alguns instantes ou contate a secretaria: "
            "secretaria.fcte@unb.br | (61) 3107-8901"
        )

    def _timeout_message(self) -> str:
        return (
            f"⏱️ A geração local excedeu o limite de {self.settings.ollama_timeout}s. "
            "O modelo pode estar sobrecarregado — aguarde 30s e tente novamente. "
            "Se persistir, reinicie o Ollama: docker restart fctebot-ollama\n\n"
            "📧 Secretaria: secretaria.fcte@unb.br | (61) 3107-8901"
        )

    def _is_circuit_open(self) -> bool:
        """Circuit breaker: evita tentativas ao Ollama após falhas consecutivas."""
        if not self._ollama_circuit_open:
            return False
        if time.monotonic() > self._circuit_open_until:
            # Meio-aberto: tenta novamente após cooldown de 60s
            self._ollama_circuit_open = False
            self._ollama_failures = 0
            logger.info("Circuit breaker: tentando Ollama novamente (cooldown expirado)")
            return False
        return True

    def _record_ollama_failure(self) -> None:
        self._ollama_failures += 1
        if self._ollama_failures >= 3:
            self._ollama_circuit_open = True
            self._circuit_open_until = time.monotonic() + 60.0
            logger.warning("Circuit breaker aberto: Ollama indisponível, usando Gemini por 60s")

    def _record_ollama_success(self) -> None:
        self._ollama_failures = 0
        self._ollama_circuit_open = False

    def _build_prompt(self, query: str, context: str) -> str:
        return QUERY_TEMPLATE.format(context=context, query=query)

    # ── Geração local (Ollama) ─────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((APIError, APITimeoutError)),
        stop=stop_after_attempt(1),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _generate_local(self, query: str, context: str) -> tuple[str, int, int]:
        """Gera resposta usando Ollama. Retorna (response, prompt_tokens, completion_tokens)."""
        client = self._get_ollama_client()
        prompt = self._build_prompt(query, context)

        response = await client.chat.completions.create(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )

        text = response.choices[0].message.content or ""
        usage = response.usage
        return (
            text,
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
        )

    # ── Geração Gemini (fallback) ──────────────────────────────────────────

    async def _generate_gemini(self, query: str, context: str) -> tuple[str, int, int]:
        """
        Gera resposta usando Google Gemini via REST API (httpx direto).

        Suporta chaves AI Studio: AIza (legado) e AQ. (auth key, padrão desde 2026).
        Obtenha em: https://aistudio.google.com/app/apikey
        """
        if not self.settings.has_gemini:
            raise RuntimeError("GEMINI_API_KEY não configurada")

        if not self.settings.gemini_key_valid:
            raise RuntimeError(
                "GEMINI_API_KEY inválida: use uma chave do Google AI Studio (AIza... ou AQ....)."
            )

        prompt = f"{SYSTEM_PROMPT}\n\n{self._build_prompt(query, context)}"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.settings.temperature,
                "maxOutputTokens": self.settings.max_tokens,
            },
        }
        api_key = self.settings.gemini_api_key.strip()
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    try:
                        retry_s = int(
                            resp.json()
                            .get("error", {})
                            .get("details", [{}])[0]
                            .get("retryDelay", "30s")
                            .replace("s", "")
                        )
                    except Exception:
                        retry_s = 30
                    logger.warning(
                        f"Gemini 429 rate limit — aguardando {retry_s}s (tentativa {attempt + 1}/3)"
                    )
                    await asyncio.sleep(retry_s)
                    continue

                if resp.status_code >= 400:
                    error_msg = resp.text[:500]
                    logger.error(f"Gemini HTTP {resp.status_code}: {error_msg}")
                    if "API_KEY_SERVICE_BLOCKED" in error_msg:
                        logger.error(
                            "Chave bloqueada para generativelanguage.googleapis.com — "
                            "no AI Studio, restrinja a chave a 'Generative Language API' (Gemini)"
                        )
                    resp.raise_for_status()

                break
            else:
                raise RuntimeError("Gemini rate limit excedido após 3 tentativas")

            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return (
            text,
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )

    # ── Geração de streaming (Ollama) ─────────────────────────────────────

    async def stream_local(
        self, query: str, context: str
    ) -> AsyncGenerator[str, None]:
        """Streaming de tokens para UX mais responsiva no Telegram."""
        client = self._get_ollama_client()
        prompt = self._build_prompt(query, context)

        async with client.chat.completions.stream(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    # ── Método principal ───────────────────────────────────────────────────

    async def generate(
        self,
        query: str,
        context: str,
        sources: list[str],
    ) -> GenerationResult:
        """
        Gera resposta com estratégia local-first + fallback.

        Args:
            query: Pergunta do usuário
            context: Contexto formatado pelos chunks re-ranqueados
            sources: Lista de fontes dos chunks

        Returns:
            GenerationResult com resposta, modo, confiança e metadados
        """
        # Verificação de tópicos proibidos (antes de qualquer geração)
        if is_forbidden_topic(query):
            logger.info(f"Tópico proibido detectado: '{query[:60]}'")
            return GenerationResult(
                response=_FORBIDDEN_RESPONSE,
                mode=GenerationMode.FORBIDDEN,
                confidence=1.0,
                latency_ms=0.0,
                sources=[],
                model_used="rule-based",
            )

        start = time.perf_counter()
        mode = GenerationMode.LOCAL
        model_used = self.settings.ollama_model
        prompt_tokens = 0
        completion_tokens = 0
        response_text = ""
        confidence = 0.0
        strategy = self.settings.llm_strategy

        async def _try_gemini(reason: str) -> bool:
            nonlocal mode, model_used, response_text, prompt_tokens, completion_tokens, confidence
            if not self.settings.has_gemini:
                logger.warning(f"{reason} — GEMINI_API_KEY não configurada")
                return False
            if not self.settings.gemini_key_valid:
                logger.error(
                    f"{reason} — GEMINI_API_KEY com formato desconhecido "
                    f"(esperado: AIza... ou AQ....)"
                )
                return False
            try:
                logger.info(f"{reason} — usando Gemini ({self.settings.gemini_model})")
                mode = GenerationMode.FALLBACK
                model_used = self.settings.gemini_model
                response_text, prompt_tokens, completion_tokens = await self._generate_gemini(
                    query, context
                )
                confidence = compute_confidence(response_text, len(context))
                return True
            except Exception as gemini_err:
                logger.warning(f"Gemini falhou ({type(gemini_err).__name__}): {gemini_err}")
                return False

        # ── gemini_only: pular Ollama ─────────────────────────────────────────
        if strategy == "gemini_only":
            if not await _try_gemini("LLM_STRATEGY=gemini_only"):
                response_text = self._unavailable_message()
                confidence = 0.0

        # ── local_only: nunca usa Gemini ──────────────────────────────────────
        elif strategy == "local_only":
            if self._is_circuit_open():
                logger.warning("Circuit breaker aberto — Ollama indisponível (local_only)")
                response_text = self._unavailable_message()
                confidence = 0.0
            else:
                try:
                    response_text, prompt_tokens, completion_tokens = await self._generate_local(
                        query, context
                    )
                    self._record_ollama_success()
                    confidence = compute_confidence(response_text, len(context))
                except APITimeoutError as e:
                    self._record_ollama_failure()
                    logger.warning(f"Ollama timeout ({self.settings.ollama_timeout}s): {e}")
                    response_text = self._timeout_message()
                    confidence = 0.0
                except (APIError, Exception) as e:
                    self._record_ollama_failure()
                    logger.warning(f"Ollama falhou ({type(e).__name__}): {e}")
                    response_text = self._unavailable_message()
                    confidence = 0.0
        elif self._is_circuit_open():
            if not await _try_gemini("Circuit breaker aberto"):
                response_text = self._unavailable_message()
                confidence = 0.0
        else:
            try:
                response_text, prompt_tokens, completion_tokens = await self._generate_local(
                    query, context
                )
                self._record_ollama_success()
                confidence = compute_confidence(response_text, len(context))
                logger.debug(
                    f"Local confidence: {confidence:.3f} "
                    f"(threshold: {self.settings.confidence_threshold})"
                )

                if (
                    confidence < self.settings.confidence_threshold
                    and self.settings.has_gemini
                ):
                    logger.info(
                        f"Confiança local baixa ({confidence:.2f}), acionando fallback Gemini"
                    )
                    if not await _try_gemini("Confiança baixa"):
                        mode = GenerationMode.LOCAL
                        model_used = self.settings.ollama_model

            except APITimeoutError as e:
                self._record_ollama_failure()
                logger.warning(f"Ollama timeout ({self.settings.ollama_timeout}s): {e}")
                response_text = self._timeout_message()
                confidence = 0.0
            except (APIError, Exception) as e:
                self._record_ollama_failure()
                logger.warning(f"Ollama falhou ({type(e).__name__}): {e}")
                if not await _try_gemini("Fallback após falha do Ollama"):
                    response_text = self._unavailable_message()
                    confidence = 0.0

        latency_ms = (time.perf_counter() - start) * 1000
        error_messages = (self._unavailable_message(), self._timeout_message())
        if response_text and response_text not in error_messages:
            confidence = compute_confidence(response_text, len(context))

        logger.info(
            f"Geração | mode={mode.value} | model={model_used} | "
            f"latency={latency_ms:.0f}ms | confidence={confidence:.2f}"
        )

        return GenerationResult(
            response=response_text,
            mode=mode,
            confidence=confidence,
            latency_ms=latency_ms,
            sources=sources,
            model_used=model_used,
            tokens_prompt=prompt_tokens,
            tokens_completion=completion_tokens,
        )
