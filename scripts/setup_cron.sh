#!/usr/bin/env bash
# =============================================================================
# FCTEBot — Configuração do cron mensal para atualização do calendário
#
# Executa no 1º dia de cada mês às 06:00 (horário de Brasília, UTC-3).
# O script update_calendario.py verifica o site SAA e atualiza o .md
# automaticamente se houver novo calendário disponível.
#
# Uso:
#   bash scripts/setup_cron.sh
#   bash scripts/setup_cron.sh --remove   # remove a entrada do cron
#   bash scripts/setup_cron.sh --status   # mostra o cron atual
# =============================================================================

set -euo pipefail

# Detectar caminho do projeto (onde este script está)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Caminhos dentro do projeto
UPDATE_SCRIPT="$SCRIPT_DIR/update_calendario.py"
LOG_FILE="$PROJECT_DIR/logs/update_calendario.log"
LOG_DIR="$PROJECT_DIR/logs"

# Caminhos dos scripts de atualização
NORMATIVOS_SCRIPT="$SCRIPT_DIR/update_normativos.py"
LOG_NORMATIVOS="$PROJECT_DIR/logs/update_normativos.log"

# Cron: 1º dia de cada mês, 06:00 BRT (09:00 UTC)
CRON_SCHEDULE="0 9 1 * *"
CRON_CMD="$PYTHON_BIN $UPDATE_SCRIPT >> $LOG_FILE 2>&1"
CRON_CMD_NORMATIVOS="0 9 2 * * $PYTHON_BIN $NORMATIVOS_SCRIPT >> $LOG_NORMATIVOS 2>&1"
CRON_LINE="$CRON_SCHEDULE $CRON_CMD"
CRON_MARKER="# FCTEBot-calendario-update"

print_banner() {
    echo "=============================================="
    echo "  FCTEBot — Configuração do cron mensal"
    echo "=============================================="
}

check_dependencies() {
    if ! command -v crontab &>/dev/null; then
        echo "❌ crontab não encontrado. Instale com:"
        echo "   sudo apt install cron"
        exit 1
    fi

    if ! "$PYTHON_BIN" -c "import requests; import bs4" &>/dev/null 2>&1; then
        echo "⚠️  Dependências Python faltando. Instalando..."
        "$PYTHON_BIN" -m pip install requests beautifulsoup4 pdfplumber --quiet
    fi
}

add_cron() {
    mkdir -p "$LOG_DIR"
    touch "$LOG_FILE"
    touch "$LOG_NORMATIVOS"

    # Verificar se já existe
    if crontab -l 2>/dev/null | grep -q "FCTEBot-calendario-update"; then
        echo "✅ Entrada cron já existe. Use --remove para remover antes de re-adicionar."
        crontab -l 2>/dev/null | grep -A1 "FCTEBot"
        return
    fi

    # Adicionar ao crontab atual
    # Dia 1: calendário acadêmico | Dia 2: normativos (escalonado para não sobrecarregar)
    (
        crontab -l 2>/dev/null || true
        echo ""
        echo "# FCTEBot-calendario-update (dia 1 de cada mês às 06:00 BRT)"
        echo "$CRON_SCHEDULE $CRON_CMD"
        echo "# FCTEBot-normativos-update (dia 2 de cada mês às 06:00 BRT)"
        echo "$CRON_CMD_NORMATIVOS"
    ) | crontab -

    echo "✅ Crons configurados com sucesso!"
    echo ""
    echo "  Calendário : dia 1 de cada mês às 06:00 BRT"
    echo "               log: $LOG_FILE"
    echo "  Normativos : dia 2 de cada mês às 06:00 BRT"
    echo "               log: $LOG_NORMATIVOS"
    echo ""
    echo "Entradas adicionadas:"
    crontab -l 2>/dev/null | grep -A1 "FCTEBot"
}

remove_cron() {
    if ! crontab -l 2>/dev/null | grep -q "FCTEBot-calendario-update"; then
        echo "ℹ️  Nenhuma entrada FCTEBot encontrada no crontab."
        return
    fi

    # Remove as duas linhas (marker + comando)
    crontab -l 2>/dev/null \
        | grep -v "FCTEBot-calendario-update" \
        | grep -v "update_calendario.py" \
        | crontab -

    echo "✅ Entrada FCTEBot removida do crontab."
}

show_status() {
    echo "📋 Crontab atual:"
    echo ""
    crontab -l 2>/dev/null || echo "  (vazio)"
    echo ""
    echo "📄 Log mais recente ($LOG_FILE):"
    if [ -f "$LOG_FILE" ]; then
        tail -n 30 "$LOG_FILE"
    else
        echo "  (log ainda não existe — será criado na 1ª execução)"
    fi
}

test_run() {
    echo "🧪 Executando em modo dry-run para testar..."
    echo ""
    "$PYTHON_BIN" "$UPDATE_SCRIPT" --dry-run
}

# ─── Main ─────────────────────────────────────────────────────────────────────

print_banner

case "${1:-install}" in
    --remove)
        remove_cron
        ;;
    --status)
        show_status
        ;;
    --test)
        test_run
        ;;
    install|"")
        check_dependencies
        add_cron
        echo ""
        echo "Para testar agora sem esperar o cron:"
        echo "  python $UPDATE_SCRIPT --dry-run"
        echo ""
        echo "Para forçar uma atualização imediata:"
        echo "  python $UPDATE_SCRIPT --force"
        ;;
    *)
        echo "Uso: $0 [install|--remove|--status|--test]"
        exit 1
        ;;
esac
