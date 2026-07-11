"""
Handler do bot Telegram — interface de usuário do FCTEBot.

Funcionalidades:
  /start  → apresentação do bot
  /help   → lista de capacidades e exemplos
  /reset  → limpa histórico de conversa
  /status → informações do sistema
  <mensagem> → consulta ao pipeline RAG

Design:
  - Assíncrono via python-telegram-bot v21+
  - "Digitando..." exibido durante processamento
  - Resposta formatada com fontes e aviso quando usando fallback
  - Rate limiting integrado ao pipeline
"""
from __future__ import annotations

import asyncio
import html
import re
from typing import Optional

from loguru import logger
from telegram import Update, BotCommand, Message
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.config import Settings
from src.rag.pipeline import RAGPipeline
from src.rag.generator import GenerationMode


# ──────────────────────────────────────────────────────────────────────────────
# Mensagens estáticas
# ──────────────────────────────────────────────────────────────────────────────

_WELCOME = """\
👋 Olá! Sou o <b>FCTEBot</b>, assistente virtual da \
Faculdade de Ciências e Tecnologias em Engenharia (FCTE) da UnB.

Posso te ajudar com:
• 📋 Matrícula e ajuste de matrícula
• 🎓 Estágio obrigatório e não-obrigatório
• ⏰ Horas complementares
• 🔒 Trancamento parcial e total
• 💰 Assistência estudantil e bolsas
• 📅 Calendário acadêmico e prazos
• 📚 Estrutura curricular
• 🎓 TCC e diploma

Basta <b>me fazer sua pergunta</b> em linguagem natural!

⚠️ Sou uma IA e posso cometer erros. Sempre confirme informações \
importantes diretamente com a secretaria.

Use /help para ver exemplos de perguntas.
"""

_HELP = """\
❓ <b>Como usar o FCTEBot</b>

<b>Exemplos de perguntas:</b>
• "Qual o prazo para trancamento parcial?"
• "Quais documentos preciso para estágio obrigatório?"
• "Como validar horas complementares?"
• "Quais são os contatos da coordenação de Engenharia de Software?"
• "Quais são os critérios de desligamento?"
• "Como funciona o processo de colação de grau?"

<b>Comandos disponíveis:</b>
/start  → Apresentação
/help   → Esta mensagem
/reset  → Limpar conversa
/status → Estado do sistema

📧 Secretaria: secretaria.fcte@unb.br
📞 (61) 3107-8901
"""

_STATUS_TEMPLATE = """\
🤖 <b>Status do FCTEBot</b>

🔍 Índice: {index_chunks} chunks indexados
💾 Cache L1: {l1_entries} entradas
🧠 Modelo local: {ollama_model}
🌐 Fallback: {fallback_status}
"""

_ERROR_MSG = (
    "⚠️ Ocorreu um erro ao processar sua pergunta. "
    "Por favor, tente novamente ou contate a secretaria: secretaria.fcte@unb.br"
)


# ──────────────────────────────────────────────────────────────────────────────
# Formatação e envio seguro
# ──────────────────────────────────────────────────────────────────────────────

def _llm_text_to_html(text: str) -> str:
    """Converte markdown comum do LLM (**bold*, *italic*) para HTML seguro."""
    # **bold** → <b>bold</b>
    parts: list[str] = []
    last = 0
    for match in re.finditer(r"\*\*(.+?)\*\*", text):
        parts.append(html.escape(text[last : match.start()]))
        parts.append(f"<b>{html.escape(match.group(1))}</b>")
        last = match.end()
    remainder = text[last:]
    # *italic* simples (fora de **)
    italic_parts: list[str] = []
    last_i = 0
    for match in re.finditer(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", remainder):
        italic_parts.append(html.escape(remainder[last_i : match.start()]))
        italic_parts.append(f"<i>{html.escape(match.group(1))}</i>")
        last_i = match.end()
    italic_parts.append(html.escape(remainder[last_i:]))
    parts.append("".join(italic_parts))
    return "".join(parts)


async def _safe_edit(
    message: Message,
    text: str,
    *,
    plain_fallback: str | None = None,
) -> None:
    """Edita mensagem com HTML; se falhar, edita como texto puro."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        logger.warning(f"Telegram rejeitou HTML na edição ({e}), usando texto puro")
        fallback = plain_fallback or re.sub(r"<[^>]+>", "", text)
        await message.edit_text(fallback)


async def _typing_loop(chat, stop: asyncio.Event) -> None:
    """Mantém indicador 'digitando...' ativo durante processamento longo."""
    while not stop.is_set():
        try:
            await chat.send_action(ChatAction.TYPING)
        except TelegramError:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


async def _safe_reply(message: Message, text: str, *, plain_fallback: str | None = None) -> int:
    """
    Envia mensagem com HTML; se o Telegram rejeitar formatação, reenvia como texto puro.
    Retorna message_id da mensagem enviada.
    """
    try:
        sent = await message.reply_text(text, parse_mode=ParseMode.HTML)
        return sent.message_id
    except BadRequest as e:
        logger.warning(f"Telegram rejeitou HTML ({e}), reenviando como texto puro")
        fallback = plain_fallback or re.sub(r"<[^>]+>", "", text)
        sent = await message.reply_text(fallback)
        return sent.message_id


def _format_response(
    response: str,
    sources: list[str],
    mode: GenerationMode,
    confidence: float,
) -> tuple[str, str]:
    """Formata resposta (HTML + versão plain para fallback)."""
    source_list = "\n".join(f"  • {s}" for s in sources[:5]) if sources else ""

    parts = [_llm_text_to_html(response)]

    if sources:
        parts.append(f"\n\n📄 <b>Fontes:</b>\n{html.escape(source_list)}")

    if mode == GenerationMode.FALLBACK:
        parts.append("\n\n<i>ℹ️ Resposta gerada via API externa (modo fallback).</i>")

    if confidence < 0.4 and mode != GenerationMode.FORBIDDEN:
        parts.append(
            "\n\n⚠️ <i>Esta resposta pode não ser precisa. "
            "Confirme com a secretaria: secretaria.fcte@unb.br</i>"
        )

    html_text = "".join(parts)

    plain_parts = [re.sub(r"\*\*(.+?)\*\*", r"\1", response)]
    if sources:
        plain_parts.append(f"\n\n📄 Fontes:\n{source_list}")
    if mode == GenerationMode.FALLBACK:
        plain_parts.append("\n\nℹ️ Resposta gerada via API externa (modo fallback).")
    if confidence < 0.4 and mode != GenerationMode.FORBIDDEN:
        plain_parts.append(
            "\n\n⚠️ Esta resposta pode não ser precisa. "
            "Confirme com a secretaria: secretaria.fcte@unb.br"
        )
    plain_text = "".join(plain_parts)

    return html_text, plain_text


# ──────────────────────────────────────────────────────────────────────────────
# Handlers de comando
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update.message, _WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update.message, _HELP)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    await update.message.reply_text(
        "🔄 Conversa reiniciada. Pode fazer sua pergunta!"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pipeline: Optional[RAGPipeline] = context.bot_data.get("pipeline")
    if not pipeline:
        await update.message.reply_text("⚠️ Pipeline não inicializado.")
        return

    retriever_stats = pipeline.retriever.stats()
    cache_stats = await pipeline.cache.stats() if pipeline.cache else {}
    settings: Settings = context.bot_data.get("settings")

    text = _STATUS_TEMPLATE.format(
        index_chunks=retriever_stats.get("total_chunks", "?"),
        l1_entries=cache_stats.get("l1_entries", "?"),
        ollama_model=settings.ollama_model if settings else "?",
        fallback_status="✅ Gemini" if (settings and settings.has_gemini) else "❌ Desativado",
    )
    await _safe_reply(update.message, text)


# ──────────────────────────────────────────────────────────────────────────────
# Handler de mensagem (consulta RAG)
# ──────────────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagem de texto como consulta ao pipeline RAG."""
    if not update.message or not update.message.text:
        return

    query = update.message.text.strip()
    user_id = str(update.effective_user.id) if update.effective_user else "unknown"
    username = update.effective_user.username or user_id

    logger.info(f"Query de @{username}: '{query[:80]}'")

    pipeline: Optional[RAGPipeline] = context.bot_data.get("pipeline")
    if not pipeline:
        await update.message.reply_text(
            "⚠️ O assistente ainda está inicializando. Aguarde alguns instantes."
        )
        return

    if not pipeline.retriever.is_loaded():
        await update.message.reply_text(
            "⚠️ A base de conhecimento ainda está sendo carregada. "
            "Tente novamente em 30 segundos."
        )
        return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(update.message.chat, stop_typing))

    status_msg = await update.message.reply_text(
        "⏳ Consultando a base de conhecimento…\n"
        "<i>Na 1ª vez pode levar 1–2 min (CPU). Repetir a pergunta usa cache instantâneo.</i>",
        parse_mode=ParseMode.HTML,
    )

    try:
        result = await pipeline.query(user_query=query, user_id=user_id)
        formatted_html, formatted_plain = _format_response(
            response=result.response,
            sources=result.sources,
            mode=result.mode,
            confidence=result.confidence,
        )
        await _safe_edit(
            status_msg,
            formatted_html,
            plain_fallback=formatted_plain,
        )
        logger.info(
            f"Resposta enviada | user=@{username} | msg_id={status_msg.message_id} | "
            f"mode={result.mode.value} | latency={result.latency_total_ms:.0f}ms | "
            f"cache={result.cache_hit} | preview={result.response[:80]!r}"
        )

    except TelegramError as e:
        logger.error(f"Erro Telegram ao responder @{username}: {e}", exc_info=True)
        try:
            await status_msg.edit_text(_ERROR_MSG)
        except TelegramError:
            await update.message.reply_text(_ERROR_MSG)
    except Exception as e:
        logger.error(f"Erro ao processar query de @{username}: {e}", exc_info=True)
        try:
            await status_msg.edit_text(_ERROR_MSG)
        except TelegramError:
            await update.message.reply_text(_ERROR_MSG)
    finally:
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Construtor da aplicação Telegram
# ──────────────────────────────────────────────────────────────────────────────

def build_bot_app(
    settings: Settings,
    pipeline: RAGPipeline,
) -> Application:
    """
    Constrói a aplicação Telegram com todos os handlers registrados.

    Args:
        settings: Configurações da aplicação
        pipeline: Pipeline RAG inicializado

    Returns:
        Application do python-telegram-bot
    """
    if not settings.has_telegram:
        raise ValueError("TELEGRAM_TOKEN não configurado no .env")

    app = Application.builder().token(settings.telegram_token).build()

    # Injetar dependências no contexto compartilhado
    app.bot_data["pipeline"] = pipeline
    app.bot_data["settings"] = settings

    # Registrar handlers de comando
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))

    # Handler de texto (consulta RAG) — qualquer mensagem não-comando
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_error_handler(on_telegram_error)

    logger.info("Bot Telegram configurado com todos os handlers.")
    return app


async def on_telegram_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga erros não tratados dos handlers Telegram."""
    logger.error(f"Erro não tratado no Telegram: {context.error}", exc_info=context.error)


async def setup_bot_commands(app: Application) -> None:
    """Registra os comandos no menu do Telegram."""
    commands = [
        BotCommand("start", "Apresentação do FCTEBot"),
        BotCommand("help", "Exemplos de perguntas e ajuda"),
        BotCommand("reset", "Limpar conversa"),
        BotCommand("status", "Estado do sistema"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Comandos do bot registrados no Telegram.")
