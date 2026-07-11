#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# FCTEBot — Setup Oracle Cloud Free Tier (Ubuntu 22.04 ARM)
#
# Execute UMA VEZ logo após provisionar a instância:
#   ssh ubuntu@<IP_PUBLICO>
#   curl -fsSL https://raw.githubusercontent.com/<USER>/FCTEBot/main/scripts/oracle-setup.sh | bash
#
# Ou copie o projeto primeiro e rode:
#   chmod +x scripts/oracle-setup.sh
#   ./scripts/oracle-setup.sh
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
die()  { echo -e "${RED}❌ $1${NC}"; exit 1; }

echo "=== FCTEBot — Setup Oracle Cloud Free Tier ==="
echo ""

# ── 1. Verificar SO ───────────────────────────────────────────────────────────
if [[ ! -f /etc/os-release ]]; then
  die "Não foi possível detectar o SO. Use Ubuntu 22.04."
fi
source /etc/os-release
ok "SO: $PRETTY_NAME"

# ── 2. Atualizar pacotes ──────────────────────────────────────────────────────
echo "→ Atualizando pacotes..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
ok "Pacotes atualizados"

# ── 3. Instalar dependências base ─────────────────────────────────────────────
echo "→ Instalando git, curl, make..."
sudo apt-get install -y -qq git curl make unzip
ok "Dependências instaladas"

# ── 4. Instalar Docker ────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
  ok "Docker já instalado: $(docker --version)"
else
  echo "→ Instalando Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  ok "Docker instalado"
  warn "Grupo docker aplicado. Se não funcionar, rode: newgrp docker"
fi

# ── 5. Instalar Docker Compose (plugin) ──────────────────────────────────────
if docker compose version &>/dev/null 2>&1; then
  ok "Docker Compose plugin já disponível"
else
  echo "→ Instalando Docker Compose plugin..."
  DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
  ARCH=$(uname -m)
  curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-${ARCH}" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  ok "Docker Compose instalado: $(docker compose version)"
fi

# ── 6. Configurar firewall (Oracle Cloud usa iptables, não ufw) ───────────────
echo "→ Configurando firewall (iptables)..."
# Oracle Cloud bloqueia tudo por padrão via Security List na console.
# Estas regras liberam as portas no SO (a Security List também precisa ser ajustada).
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p udp --dport 443 -j ACCEPT

# Persistir regras entre reboots
if ! dpkg -l iptables-persistent &>/dev/null; then
  echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
  echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections
  sudo apt-get install -y -qq iptables-persistent
fi
sudo netfilter-persistent save
ok "Portas 80 e 443 liberadas no SO"
warn "Não esqueça de abrir as portas 80 e 443 na Security List do Oracle Cloud Console"

# ── 7. Clonar ou atualizar repositório ───────────────────────────────────────
REPO_DIR="$HOME/FCTEBot"
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "→ Repositório já existe — atualizando..."
  git -C "$REPO_DIR" pull --ff-only
  ok "Repositório atualizado"
elif [[ -d "$REPO_DIR" ]]; then
  warn "Diretório $REPO_DIR existe mas não é um git repo. Pulando clone."
else
  echo "→ Clonando repositório..."
  warn "Defina REPO_URL antes de rodar este script ou clone manualmente:"
  warn "  git clone <seu-repo> $REPO_DIR"
  # git clone "${REPO_URL:-https://github.com/SEU_USUARIO/FCTEBot.git}" "$REPO_DIR"
fi

cd "$REPO_DIR" 2>/dev/null || { warn "Entre no diretório do projeto manualmente: cd ~/FCTEBot"; exit 0; }

# ── 8. Configurar .env ────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  cp .env.example .env
  warn ".env criado a partir do .env.example"
  warn "IMPORTANTE: edite o .env agora:"
  warn "  nano .env"
  warn "  → Defina GEMINI_API_KEY (fallback)"
  warn "  → Defina DOMAIN (seu domínio ou IP)"
  warn "  → Revise LLM_STRATEGY=local_first"
  echo ""
  echo "Depois de editar o .env, rode:"
  echo "  make prod-up"
  exit 0
else
  ok ".env já existe"
fi

# ── 9. Verificar variável DOMAIN ──────────────────────────────────────────────
if ! grep -q "^DOMAIN=" .env || grep -q "^DOMAIN=$" .env; then
  warn "Variável DOMAIN não definida no .env!"
  warn "Adicione: DOMAIN=seu-dominio.com (ou IP público para teste sem HTTPS)"
fi

# ── 10. Subir serviços ────────────────────────────────────────────────────────
echo ""
echo "→ Build e start dos serviços de produção..."
docker compose -f docker-compose.prod.yml up -d --build

# ── 11. Baixar modelo Ollama ──────────────────────────────────────────────────
MODEL=$(grep "^OLLAMA_MODEL=" .env | cut -d= -f2 || echo "qwen2.5:0.5b")
MODEL="${MODEL:-qwen2.5:0.5b}"
echo ""
echo "→ Baixando modelo Ollama: $MODEL..."
echo "  (pode levar alguns minutos na primeira vez)"
docker exec fctebot-ollama ollama pull "$MODEL" || warn "Falha ao baixar modelo. Tente manualmente: docker exec fctebot-ollama ollama pull $MODEL"
ok "Modelo $MODEL disponível"

# ── 12. Aguardar healthcheck ──────────────────────────────────────────────────
echo ""
echo "→ Aguardando API ficar saudável (até 3 minutos)..."
for i in $(seq 1 18); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    ok "API respondendo"
    break
  fi
  echo "  tentativa $i/18..."
  sleep 10
done

# ── 13. Teste rápido ──────────────────────────────────────────────────────────
echo ""
echo "→ Teste rápido da API..."
curl -sf -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual o prazo para trancamento parcial?"}' \
  | python3 -m json.tool 2>/dev/null || warn "API ainda inicializando (normal na primeira subida)"

echo ""
echo "════════════════════════════════════════════"
ok "Setup concluído!"
echo ""
DOMAIN_VAL=$(grep "^DOMAIN=" .env | cut -d= -f2 || echo "<seu-dominio>")
echo "  Interface web: https://${DOMAIN_VAL}"
echo "  API health:    https://${DOMAIN_VAL}/health"
echo ""
echo "Comandos úteis:"
echo "  make prod-logs    → logs em tempo real"
echo "  make prod-down    → parar serviços"
echo "  make prod-up      → subir serviços"
echo "════════════════════════════════════════════"
