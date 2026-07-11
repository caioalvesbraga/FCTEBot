#!/usr/bin/env bash
# Empacota FCTEBot + índices + modelos ML para deploy em GPU cloud.
#
# Uso (WSL, com fctebot-app rodando ou que já baixou modelos):
#   chmod +x scripts/bundle-for-cloud.sh
#   ./scripts/bundle-for-cloud.sh
#
# Gera em dist/:
#   fctebot-cloud.tar.gz   — projeto + data/ + models/
#   .env                   — copie manualmente ou: cp .env dist/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
MODELS="/tmp/fcte-models-$$"
CONTAINER="${FCTEBOT_CONTAINER:-fctebot-app}"

echo "=== FCTEBot — Bundle para GPU Cloud ==="
mkdir -p "$DIST"

# ── Exportar modelos do container (embedding + reranker) ─────────────────────
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "→ Exportando modelos de $CONTAINER..."
  docker exec "$CONTAINER" python3 -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
import os
os.makedirs('/models', exist_ok=True)
SentenceTransformer('intfloat/multilingual-e5-base').save('/models/multilingual-e5-base')
CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1').save('/models/reranker')
print('Modelos salvos em /models')
"
  docker cp "$CONTAINER:/models" "$MODELS"
else
  echo "⚠️  Container $CONTAINER não está rodando."
  echo "   Suba com: docker compose up -d app"
  echo "   Ou defina FCTEBOT_CONTAINER=nome_do_container"
  exit 1
fi

# ── Montar diretório temporário ───────────────────────────────────────────────
STAGE="/tmp/fctebot-stage-$$"
mkdir -p "$STAGE/FCTEBot/models"
cp -r "$MODELS"/* "$STAGE/FCTEBot/models/"

# Projeto (sem lixo)
rsync -a --exclude '.git' --exclude '__pycache__' --exclude '.venv' \
  --exclude 'dist' --exclude '*.tar.gz' \
  "$ROOT/" "$STAGE/FCTEBot/"

# .env.cloud — paths locais, sem HuggingFace online
cat > "$STAGE/FCTEBot/.env.cloud" << 'EOF'
# Copie para .env no servidor cloud: cp .env.cloud .env
# Adicione TELEGRAM_TOKEN se for usar bot

LLM_STRATEGY=local_only
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=120
EMBEDDING_DEVICE=cuda
EMBEDDING_MODEL=/app/models/multilingual-e5-base
RERANKER_MODEL=/app/models/reranker
CONFIDENCE_THRESHOLD=0.0
RETRIEVAL_TOP_K=6
RERANKER_TOP_K=2
MAX_TOKENS=300
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
KNOWLEDGE_BASE_PATH=Infos Adms UnB
EOF

# ── Compactar ─────────────────────────────────────────────────────────────────
OUT="$DIST/fctebot-cloud.tar.gz"
tar czf "$OUT" -C "$STAGE" FCTEBot
rm -rf "$STAGE" "$MODELS"

SIZE=$(du -h "$OUT" | cut -f1)
echo ""
echo "✅ Bundle criado: $OUT ($SIZE)"
echo ""
echo "Próximos passos:"
echo "  1. scp $OUT user@GPU:/root/"
echo "  2. No servidor: tar xzf fctebot-cloud.tar.gz && cd FCTEBot"
echo "  3. cp .env.cloud .env  (+ TELEGRAM_TOKEN se necessário)"
echo "  4. ./scripts/cloud-preflight.sh"
echo "  5. docker compose -f docker-compose.yml -f docker-compose.cloud.yml up -d --build"
