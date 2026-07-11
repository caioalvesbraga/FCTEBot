# Deploy

O FCTEBot pode ser implantado em três cenários. Escolha conforme a necessidade
de latência e custo.

| Cenário | Hardware | Latência | Custo | Compose |
|---|---|---|---|---|
| **Oracle Cloud Free Tier** | CPU ARM (4 OCPU/24 GB) | ~10–20 s | Grátis | `docker-compose.prod.yml` |
| **Vast.ai / RunPod (GPU)** | GPU (RTX 3060+) | < 3 s | ~US$0,10–0,40/h | `docker-compose.gpu.yml` |
| **Local (dev)** | CPU | variável | Grátis | `docker-compose.yml` |

O guia detalhado de Oracle Cloud (com HTTPS via Caddy) está em
[`DEPLOY.md`](https://github.com/caioalvesbraga/FCTEBot/blob/main/DEPLOY.md) na raiz
do repositório.

## GPU cloud (Vast.ai) — resumo

1. Alugue uma instância GPU (imagem Ubuntu + CUDA 12.x) expondo as portas
   necessárias.
2. Envie o projeto (via `git clone` ou `scp`) para a instância.
3. Rode o setup: `./scripts/vast-setup.sh` (ou `runpod-setup.sh`).
4. A stack sobe com `docker-compose.yml -f docker-compose.gpu.yml`.
5. Exponha o frontend publicamente (ex.: túnel Cloudflare) e compartilhe a URL.

Detalhes de operação após o deploy: [Runbook](runbook.md).

## Scripts de deploy disponíveis

| Script | Uso |
|---|---|
| `scripts/oracle-setup.sh` | Setup completo Oracle Cloud (Docker, firewall, prod, modelo) |
| `scripts/vast-setup.sh` | Setup em instância GPU do Vast.ai |
| `scripts/runpod-setup.sh` | Setup em pod GPU do RunPod |
| `scripts/bundle-for-cloud.sh` | Empacota projeto + índices + modelos para deploy offline |
| `scripts/cloud-preflight.sh` | Valida ambiente GPU antes do deploy (nvidia-smi, Docker, hora) |
| `scripts/entrypoint.sh` | Entrypoint do contêiner: na 1ª subida atualiza docs, ingere e sobe a API |

> **TODO (continuidade):**
> - Documentar a exposição pública em produção GPU (túnel vs. IP/porta) e como
>   fixar a URL entre reinícios.
> - Consolidar o conteúdo de `DEPLOY.md` (hoje focado em Oracle) aqui, cobrindo
>   os três cenários em um único lugar.
