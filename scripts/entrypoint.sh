#!/usr/bin/env bash
# =============================================================================
# FCTEBot — Entrypoint do container Docker
#
# Fluxo na PRIMEIRA subida (data/.initialized ausente):
#   1. Atualiza calendários acadêmicos  (update_calendario.py)
#   2. Atualiza normativos da UnB       (update_normativos.py)
#   3. Constrói os índices RAG          (ingest.py --force)
#   4. Marca como inicializado          (data/.initialized)
#   5. Sobe a aplicação                 (uvicorn)
#
# Subidas seguintes: pula os passos 1-4 e vai direto para o uvicorn.
#
# Para forçar re-inicialização:
#   docker exec fctebot-app rm /app/data/.initialized
#   docker restart fctebot-app
#
# Variáveis de ambiente relevantes:
#   SKIP_FIRST_RUN_SETUP=true  → pula sempre (útil em CI ou testes)
#   FORCE_SETUP=true           → força mesmo se já inicializado
# =============================================================================

set -euo pipefail

PYTHON="python"
DATA_DIR="/app/data"
SENTINEL="$DATA_DIR/.initialized"
LOG_DIR="/app/logs"

# ─── Funções auxiliares ───────────────────────────────────────────────────────

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] $*"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ENTRYPOINT] ⚠️  $*" >&2; }

run_step() {
    local label="$1"
    shift
    log "▶ $label"
    if "$@"; then
        log "✅ $label concluído"
    else
        warn "$label falhou (código $?). Continuando..."
    fi
}

# ─── Verificação de pré-requisitos ────────────────────────────────────────────

mkdir -p "$DATA_DIR" "$LOG_DIR"

# ─── Decisão: rodar setup ou não ──────────────────────────────────────────────

SKIP="${SKIP_FIRST_RUN_SETUP:-false}"
FORCE="${FORCE_SETUP:-false}"

if [[ "$SKIP" == "true" ]]; then
    log "SKIP_FIRST_RUN_SETUP=true — pulando setup inicial"
elif [[ "$FORCE" == "true" ]]; then
    log "FORCE_SETUP=true — forçando re-inicialização"
    rm -f "$SENTINEL"
fi

if [[ -f "$SENTINEL" && "$FORCE" != "true" ]]; then
    log "Sentinela encontrado ($SENTINEL) — setup já realizado anteriormente"
    log "Para re-executar: rm $SENTINEL && docker restart fctebot-app"
else
    log "======================================================="
    log "PRIMEIRA SUBIDA — iniciando setup da base de conhecimento"
    log "======================================================="

    # 1. Calendários acadêmicos
    run_step "Atualização do calendário acadêmico" \
        $PYTHON scripts/update_calendario.py --no-ingest

    # 2. Normativos da UnB
    run_step "Atualização dos normativos" \
        $PYTHON scripts/update_normativos.py --no-ingest

    # 3. Ingestão RAG (constrói FAISS + TF-IDF)
    log "▶ Construindo índices RAG..."
    if $PYTHON scripts/ingest.py --force; then
        log "✅ Índices RAG construídos"
    else
        warn "ingest.py falhou — API vai subir sem índices (pipeline RAG indisponível)"
        warn "Re-execute manualmente: docker exec fctebot-app python scripts/ingest.py --force"
    fi

    # 4. Marcar como inicializado
    date -Iseconds > "$SENTINEL"
    log "Sentinela criado: $SENTINEL"
    log "======================================================="
    log "Setup concluído — subindo aplicação"
    log "======================================================="
fi

# ─── Subir a aplicação ────────────────────────────────────────────────────────

_LOG_LEVEL="${LOG_LEVEL:-info}"
exec $PYTHON -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level "${_LOG_LEVEL,,}"
