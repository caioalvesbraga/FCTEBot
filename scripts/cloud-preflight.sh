#!/usr/bin/env bash
# Valida ambiente GPU cloud ANTES de gastar tempo no deploy.
# Rode nos primeiros 2 minutos após alugar a máquina.
#
# Uso: ./scripts/cloud-preflight.sh
set -euo pipefail

FAIL=0
ok()  { echo "✅ $1"; }
bad() { echo "❌ $1"; FAIL=1; }

echo "=== FCTEBot — Preflight GPU Cloud ==="

# Data/hora (SSL quebra se errada)
YEAR=$(date +%Y)
if [[ "$YEAR" -lt 2024 || "$YEAR" -gt 2030 ]]; then
  bad "Data/hora incorreta: $(date)"
else
  ok "Data/hora: $(date)"
fi

# GPU
if nvidia-smi &>/dev/null; then
  ok "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
else
  bad "nvidia-smi falhou"
fi

# HTTPS (host ruim = abortar cedo)
if curl -sf --max-time 10 -I https://registry-1.docker.io/v2/ >/dev/null; then
  ok "HTTPS Docker Hub OK"
else
  bad "HTTPS Docker Hub FALHOU — troque de instância/host"
fi

if curl -sf --max-time 10 -I https://pypi.org >/dev/null; then
  ok "HTTPS PyPI OK"
else
  bad "HTTPS PyPI FALHOU — troque de instância/host"
fi

# Docker
if command -v docker &>/dev/null; then
  ok "Docker: $(docker --version)"
else
  bad "Docker não instalado"
fi

# NVIDIA Container Toolkit
if docker info 2>/dev/null | grep -qi nvidia; then
  ok "NVIDIA Container Toolkit detectado"
elif docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi &>/dev/null; then
  ok "docker run --gpus all OK"
else
  bad "GPU no Docker não funciona — instale nvidia-container-toolkit"
fi

# Teste pull mínimo
if docker pull hello-world &>/dev/null; then
  ok "docker pull hello-world OK"
else
  bad "docker pull falhou"
fi

echo ""
if [[ $FAIL -eq 0 ]]; then
  echo "✅ Ambiente OK — pode rodar docker compose."
  exit 0
else
  echo "❌ Problemas detectados — NÃO continue neste host. Destroy e alugue outro."
  exit 1
fi
