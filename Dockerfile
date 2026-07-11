FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema:
#   curl          → healthcheck
#   build-essential → compilação de extensões Python (faiss, etc.)
#   poppler-utils → pdfplumber precisa para extração de tabelas em PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código-fonte
COPY src/ ./src/
COPY scripts/ ./scripts/

# Tornar entrypoint executável
RUN chmod +x /app/scripts/entrypoint.sh

# knowledge_base é montada como volume no docker-compose (:rw)
# para que o entrypoint possa escrever os .md baixados na primeira subida

# Criar diretórios persistentes
RUN mkdir -p /app/data /app/logs

# Porta da API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
