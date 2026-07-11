#!/usr/bin/env bash
# Setup FCTEBot em Pod RunPod com GPU NVIDIA
#
# Uso (dentro do Pod, na pasta FCTEBot):
#   chmod +x scripts/runpod-setup.sh
#   ./scripts/runpod-setup.sh
set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.gpu.yml"

echo "=== FCTEBot — Setup RunPod GPU ==="

# ── 1. Verificar GPU ──────────────────────────────────────────────────────────
if ! command -v nvidia-smi &>/dev/null; then
  echo "❌ nvidia-smi não encontrado — selecione um template com CUDA/GPU"
  exit 1
fi
echo "✅ GPU detectada:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# ── 2. Verificar Docker + NVIDIA runtime ─────────────────────────────────────
if ! docker info 2>/dev/null | grep -qi nvidia; then
  echo "⚠️  NVIDIA Container Toolkit não detectado — tentando instalar..."
  if command -v apt-get &>/dev/null; then
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt-get update -qq
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker 2>/dev/null || sudo service docker restart
    echo "✅ NVIDIA Container Toolkit instalado"
  else
    echo "❌ Instale nvidia-container-toolkit manualmente e rode de novo"
    exit 1
  fi
fi

# ── 3. Verificar .env ─────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  echo "❌ Arquivo .env não encontrado — copie .env.example e configure TELEGRAM_TOKEN"
  exit 1
fi
echo "✅ .env encontrado"

# ── 4. Subir stack (app + ollama + redis) ─────────────────────────────────────
echo ""
echo "→ Build e start dos containers..."
$COMPOSE up -d --build app ollama redis

# ── 5. Baixar modelo Ollama ───────────────────────────────────────────────────
MODEL="${OLLAMA_MODEL:-qwen2.5:0.5b}"
echo ""
echo "→ Baixando modelo Ollama: $MODEL (pode levar alguns minutos)..."
docker exec fctebot-ollama ollama pull "$MODEL"

# ── 6. Ingestão (se índices não existirem) ────────────────────────────────────
if [[ ! -f data/faiss.index ]]; then
  echo ""
  echo "→ Índices não encontrados — rodando ingestão..."
  docker exec fctebot-app python scripts/ingest.py --force
else
  echo "✅ Índices FAISS já existem em data/ — pulando ingestão"
fi

# ── 7. Teste rápido ───────────────────────────────────────────────────────────
echo ""
echo "→ Aguardando health check..."
sleep 5
curl -sf http://localhost:8000/health | python3 -m json.tool || true

echo ""
echo "=== Setup concluído ==="
echo ""
echo "Teste local no Pod:"
echo '  curl -s -X POST http://localhost:8000/query \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"query": "Qual o prazo para trancamento parcial?"}'"'"' | python3 -m json.tool'
echo ""
echo "⚠️  IMPORTANTE: pare o FCTEBot local (WSL) antes de usar o Telegram aqui"
echo "    — só um processo pode fazer polling com o mesmo token."
echo ""
echo "Para parar e economizar: docker compose down"
