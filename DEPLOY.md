# Deploy FCTEBot — Oracle Cloud Free Tier

Guia completo para hospedar o FCTEBot em um VPS gratuito e permanente para testes com alunos e secretaria.

---

## Por que Oracle Cloud Free Tier?

- **Grátis para sempre**: 4 OCPU ARM + 24 GB RAM + 200 GB storage
- RAM suficiente para rodar Ollama (`qwen2.5:0.5b`) em CPU (~10–15s de latência)
- IP público fixo, HTTPS automático via Caddy + Let's Encrypt
- Sem cartão de crédito obrigatório para o tier gratuito

---

## Parte 1 — Criar a instância Oracle Cloud

### 1.1 Criar conta
1. Acesse [cloud.oracle.com](https://cloud.oracle.com) e crie uma conta
2. Selecione a região mais próxima (ex: **Brazil East (São Paulo)**)
3. Complete a verificação (cartão de crédito pode ser pedido, mas não será cobrado)

### 1.2 Provisionar instância

1. No menu: **Compute → Instances → Create Instance**
2. Configure:
   - **Name**: `fctebot`
   - **Image**: Ubuntu 22.04 (Minimal)
   - **Shape**: `VM.Standard.A1.Flex` (ARM) — selecione **4 OCPUs** e **24 GB RAM**
   - **Boot volume**: 50 GB (padrão é suficiente)
3. Em **Add SSH keys**: faça upload da sua chave pública (`~/.ssh/id_rsa.pub`)
   - Se não tiver: `ssh-keygen -t rsa -b 4096`
4. Clique **Create**

### 1.3 Liberar portas no Security List

1. Vá em: **Networking → Virtual Cloud Networks → sua VCN → Security Lists → Default**
2. Clique **Add Ingress Rules** e adicione:

| Source CIDR | Protocol | Port Range | Descrição |
|---|---|---|---|
| `0.0.0.0/0` | TCP | `80` | HTTP |
| `0.0.0.0/0` | TCP | `443` | HTTPS |

> ⚠️ Sem esta etapa, o Caddy não consegue obter certificado TLS.

### 1.4 Apontar domínio (opcional, mas recomendado)

Se tiver um domínio (ex: no [Registro.br](https://registro.br)):
1. Crie um registro `A` apontando para o IP público da instância
2. Aguarde propagação (1–5 minutos com TTL baixo)

Se **não tiver domínio**: use o IP público diretamente (sem HTTPS — veja seção alternativa).

---

## Parte 2 — Configurar o servidor

### 2.1 Conectar via SSH

```bash
ssh ubuntu@<IP_PUBLICO>
```

### 2.2 Clonar o projeto

```bash
git clone https://github.com/SEU_USUARIO/FCTEBot.git ~/FCTEBot
cd ~/FCTEBot
```

> Se o repositório for privado, use um Personal Access Token ou configure SSH no servidor.

### 2.3 Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env
```

Variáveis obrigatórias para produção:

```env
# Domínio configurado (ou IP público)
DOMAIN=fctebot.seu-dominio.com

# Fallback LLM (recomendado configurar mesmo em local_first)
GEMINI_API_KEY=AIza...

# Estratégia: local_first usa Ollama + Gemini como fallback
LLM_STRATEGY=local_first

# Modelo pequeno para CPU
OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_TIMEOUT=300
```

### 2.4 Rodar o setup automático

```bash
chmod +x scripts/oracle-setup.sh
./scripts/oracle-setup.sh
```

O script irá:
- Instalar Docker e Docker Compose
- Configurar o firewall interno (iptables)
- Subir todos os serviços
- Baixar o modelo Ollama
- Testar a API

---

## Parte 3 — Verificar o deploy

### Health check
```bash
curl https://fctebot.seu-dominio.com/health
```

### Teste de query
```bash
curl -s -X POST https://fctebot.seu-dominio.com/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual o prazo para trancamento parcial?"}' \
  | python3 -m json.tool
```

### Ver logs
```bash
make prod-logs
```

---

## Parte 4 — Operação do dia a dia

| Comando | O que faz |
|---|---|
| `make prod-up` | Sobe/reinicia os serviços |
| `make prod-down` | Para os serviços |
| `make prod-logs` | Logs em tempo real |
| `make prod-pull` | Atualiza código e reinicia |
| `make prod-model` | Baixa/atualiza modelo Ollama |
| `make ingest` | Re-indexa a base de conhecimento |

---

## Alternativa — Sem domínio (IP puro, sem HTTPS)

Se não tiver domínio, edite o `Caddyfile` para usar HTTP simples:

```caddy
:80 {
    reverse_proxy frontend:80
}
```

E no `.env`, defina:
```env
DOMAIN=:80
```

Acesso: `http://<IP_PUBLICO>`

> ⚠️ Sem HTTPS, navegadores modernos podem exibir aviso. Para testes internos é aceitável.

---

## Alternativa — Deploy em RunPod (GPU, latência baixa)

Para latência < 1s com modelos maiores:

```bash
# No pod RunPod, após upload do projeto:
./scripts/runpod-setup.sh
```

Veja [scripts/runpod-setup.sh](scripts/runpod-setup.sh) para detalhes.

---

## Troubleshooting

### Certificado TLS não gerado
- Verifique se as portas 80/443 estão abertas na Security List do Oracle
- O domínio deve resolver para o IP da instância
- Verifique logs: `docker logs fctebot-caddy`

### Ollama sem memória
- O `qwen2.5:0.5b` precisa de ~1 GB RAM
- Com 24 GB disponíveis na instância ARM free tier, não deve ser problema
- Se houver swap insuficiente: `sudo fallocate -l 4G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`

### API não responde (timeout na primeira subida)
- A primeira subida baixa modelos de embedding (~500 MB) e indexa documentos
- Aguarde 5–10 minutos e tente novamente
- Acompanhe: `docker logs -f fctebot-app`

### Frontend não carrega
- Verifique se o build foi concluído: `docker logs fctebot-frontend`
- Certifique-se de que `fctebot-app` está healthy antes de subir o frontend
