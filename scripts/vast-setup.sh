#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# FCTEBot — Setup Vast.ai (GPU)
#
# Rode dentro da instância Vast.ai após conectar via SSH:
#   chmod +x scripts/vast-setup.sh
#   ./scripts/vast-setup.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
die()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo "=== FCTEBot — Setup Vast.ai GPU ==="
echo ""

# ── 1. Verificar GPU ──────────────────────────────────────────────────────────
if ! command -v nvidia-smi &>/dev/null; then
  die "nvidia-smi não encontrado. Selecione uma instância com GPU."
fi
echo "GPU detectada:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
echo ""
ok "GPU OK"

# ── 2. Verificar Docker ───────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "→ Instalando Docker..."
  curl -fsSL https://get.docker.com | sh
  ok "Docker instalado"
else
  ok "Docker: $(docker --version)"
fi

# ── 3. Verificar NVIDIA Container Toolkit ────────────────────────────────────
if ! docker info 2>/dev/null | grep -qi nvidia; then
  echo "→ Instalando NVIDIA Container Toolkit..."
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -qq
  apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker 2>/dev/null || service docker restart
  ok "NVIDIA Container Toolkit instalado"
else
  ok "NVIDIA Container Toolkit OK"
fi

# ── 4. Docker Compose plugin ──────────────────────────────────────────────────
if ! docker compose version &>/dev/null 2>&1; then
  echo "→ Instalando Docker Compose plugin..."
  DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  ARCH=$(uname -m)
  COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
  curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  ok "Docker Compose instalado"
else
  ok "Docker Compose: $(docker compose version --short)"
fi

# ── 5. Configurar .env ────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env

  # Ajustes automáticos para GPU
  sed -i 's/^EMBEDDING_DEVICE=.*/EMBEDDING_DEVICE=cuda/' .env
  sed -i 's/^LLM_STRATEGY=.*/LLM_STRATEGY=local_first/' .env
  sed -i 's/^OLLAMA_MODEL=.*/OLLAMA_MODEL=qwen2.5:7b/' .env
  sed -i 's/^OLLAMA_TIMEOUT=.*/OLLAMA_TIMEOUT=120/' .env

  warn ".env criado. Configure GEMINI_API_KEY se quiser fallback:"
  warn "  nano .env"
  echo ""
  read -r -p "Pressione ENTER para continuar ou Ctrl+C para editar o .env agora..."
else
  ok ".env encontrado"
  # Garantir CUDA no .env existente
  sed -i 's/^EMBEDDING_DEVICE=cpu/EMBEDDING_DEVICE=cuda/' .env
fi

# ── 6. Subir stack com GPU ────────────────────────────────────────────────────
echo ""
echo "→ Build e start dos containers (GPU)..."
docker compose -f docker-compose.yml -f docker-compose.gpu.yml \
  up -d --build app ollama redis frontend

# ── 7. Baixar modelo Ollama ───────────────────────────────────────────────────
MODEL=$(grep "^OLLAMA_MODEL=" .env | cut -d= -f2 || echo "qwen2.5:7b")
MODEL="${MODEL:-qwen2.5:7b}"
echo ""
echo "→ Baixando modelo: $MODEL (pode levar alguns minutos)..."
docker exec fctebot-ollama ollama pull "$MODEL"
ok "Modelo $MODEL pronto"

# ── 8. Aguardar API ───────────────────────────────────────────────────────────
echo ""
echo "→ Aguardando API inicializar (até 3 minutos)..."
for i in $(seq 1 18); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    ok "API respondendo"
    break
  fi
  echo "  aguardando... ($i/18)"
  sleep 10
done

# ── 9. Teste rápido ───────────────────────────────────────────────────────────
echo ""
echo "→ Teste rápido..."
curl -sf -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual o prazo para trancamento parcial?"}' \
  | python3 -m json.tool 2>/dev/null || warn "API ainda inicializando — tente em 1 minuto"

# ── 10. Mostrar URLs de acesso ────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
ok "Setup concluído!"
echo ""
echo "Portas internas (acesse via painel Vast.ai):"
echo "  Frontend:  porta 3000"
echo "  API:       porta 8000"
echo ""
echo "No painel Vast.ai, clique em 'Connect' na instância"
echo "para ver as URLs públicas mapeadas para cada porta."
echo ""
echo "Comandos úteis:"
echo "  docker compose logs -f app        → logs da API"
echo "  docker exec fctebot-ollama ollama list  → modelos carregados"
echo "  nvidia-smi                         → uso da GPU em tempo real"
echo "════════════════════════════════════════════"
