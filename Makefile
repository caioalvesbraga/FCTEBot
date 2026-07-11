# ──────────────────────────────────────────────────────────────────────────────
# FCTEBot — Makefile
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: help setup up down logs ingest eval baseline clean prod-up prod-down prod-logs prod-pull prod-model

help:
	@echo "FCTEBot — Comandos disponíveis:"
	@echo ""
	@echo "  Desenvolvimento (local):"
	@echo "  make setup        Configura o ambiente (copia .env, baixa modelo)"
	@echo "  make up           Sobe todos os serviços Docker"
	@echo "  make down         Para todos os serviços"
	@echo "  make logs         Exibe logs em tempo real"
	@echo "  make ingest       Executa pipeline de ingestão da base de conhecimento"
	@echo "  make eval         Executa avaliação RAGAS"
	@echo "  make baseline     Executa benchmark comparativo"
	@echo "  make clean        Remove dados gerados (índices, cache)"
	@echo ""
	@echo "  Produção (Oracle Cloud / VPS CPU):"
	@echo "  make prod-up      Sobe stack de produção (Caddy + HTTPS)"
	@echo "  make prod-down    Para stack de produção"
	@echo "  make prod-logs    Logs da stack de produção"
	@echo "  make prod-pull    Atualiza imagens e reinicia"
	@echo "  make prod-model   Baixa modelo Ollama no container de produção"

setup:
	@echo "→ Copiando .env.example para .env..."
	@cp -n .env.example .env || true
	@echo "→ Baixando modelo Qwen2.5:3b no Ollama..."
	@docker exec fctebot-ollama ollama pull qwen2.5:3b || echo "  (Ollama não está rodando, baixe o modelo depois)"
	@echo "✓ Setup concluído. Edite o arquivo .env com seus tokens."

up:
	@echo "→ Subindo serviços FCTEBot..."
	docker compose up -d --build
	@echo "✓ Serviços disponíveis:"
	@echo "   API:        http://localhost:8000"
	@echo "   Grafana:    http://localhost:3000 (admin/fctebot2025)"
	@echo "   Prometheus: http://localhost:9090"

down:
	docker compose down

logs:
	docker compose logs -f app

ingest:
	@echo "→ Executando pipeline de ingestão..."
	docker exec fctebot-app python scripts/ingest.py
	@echo "✓ Ingestão concluída."

eval:
	@echo "→ Executando avaliação RAGAS..."
	docker exec fctebot-app python evaluation/evaluate.py
	@echo "✓ Resultados salvos em evaluation/results/"

baseline:
	@echo "→ Executando benchmark comparativo..."
	docker exec fctebot-app python evaluation/baseline_comparison.py

clean:
	@echo "→ Removendo dados gerados..."
	rm -rf data/faiss.index data/metadata.pkl data/tfidf.pkl data/chunks.pkl
	@echo "✓ Dados removidos. Execute 'make ingest' para recriar."

dev:
	@echo "→ Modo desenvolvimento (sem Docker)..."
	cp -n .env.example .env || true
	pip install -r requirements.txt
	OLLAMA_BASE_URL=http://localhost:11434 REDIS_URL=redis://localhost:6379/0 \
	uvicorn src.main:app --reload --port 8000

# ── Produção ──────────────────────────────────────────────────────────────────

prod-up:
	@echo "→ Subindo stack de produção..."
	@test -f .env || (echo "❌ .env não encontrado. Rode: cp .env.example .env" && exit 1)
	docker compose -f docker-compose.prod.yml up -d --build
	@echo "✓ Stack de produção no ar."
	@echo "   Acesse: https://$$(grep '^DOMAIN=' .env | cut -d= -f2)"

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

prod-pull:
	@echo "→ Atualizando stack de produção..."
	git pull --ff-only
	docker compose -f docker-compose.prod.yml pull
	docker compose -f docker-compose.prod.yml up -d --build
	@echo "✓ Atualização concluída."

prod-model:
	@MODEL=$$(grep '^OLLAMA_MODEL=' .env | cut -d= -f2 || echo "qwen2.5:0.5b"); \
	echo "→ Baixando modelo: $$MODEL"; \
	docker exec fctebot-ollama ollama pull $$MODEL
