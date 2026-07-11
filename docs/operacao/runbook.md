# Runbook de operação

Procedimentos de **dia a dia** (day-2 operations) para manter o FCTEBot no ar.
Assume deploy via Docker Compose. Ajuste os nomes de contêiner se necessário
(`fctebot-app`, `fctebot-ollama`, `fctebot-redis`, `fctebot-frontend`).

!!! tip "Convenção de acesso (Vast.ai / GPU cloud)"
    Os exemplos usam SSH. Substitua `PORT`, `HOST` e a chave pela conexão atual
    da sua instância (o painel do provedor mostra o comando SSH). Em GPU cloud, o
    Compose costuma ser `docker-compose.yml -f docker-compose.gpu.yml`.

    ```bash
    ssh -p <PORT> -i ~/.ssh/<chave> root@<HOST>
    ```

## Comandos rápidos (Makefile)

| Comando | Ação |
|---|---|
| `make up` / `make down` | Sobe / para a stack de desenvolvimento |
| `make prod-up` / `make prod-down` | Sobe / para a stack de produção (Caddy) |
| `make logs` / `make prod-logs` | Logs em tempo real |
| `make ingest` | Reindexa a base de conhecimento |
| `make prod-model` | Baixa/atualiza o modelo do Ollama |
| `make clean` | Remove índices gerados (`data/`) |

## Verificar saúde

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Interpretação do `status`:

- `ok` — retriever carregado; sistema operacional.
- `degraded` — cache no ar, mas retriever não carregou (índice ausente → rode a ingestão).
- `error` — falha crítica (HTTP 503).

Confira também `index_chunks` (número de trechos indexados) e `ollama: true`.

## Atualizar a base de conhecimento (procedimento padrão)

Sempre que editar arquivos em `Infos Adms UnB/`:

```bash
# 1. (deploy remoto) enviar os .md atualizados
scp -P <PORT> -i ~/.ssh/<chave> -r \
  "/mnt/c/Users/caiob/Downloads/TCC/FCTEBot/Infos Adms UnB" \
  root@<HOST>:/root/FCTEBot/

# 2. reindexar + recriar o app (recarrega o índice na memória) + limpar cache
ssh -p <PORT> -i ~/.ssh/<chave> root@<HOST> "
  cd /root/FCTEBot &&
  docker exec fctebot-app python scripts/ingest.py --force &&
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate app &&
  docker exec fctebot-redis redis-cli FLUSHALL
"
```

!!! warning "Três passos obrigatórios"
    1. **`ingest.py --force`** reconstrói os índices em disco.
    2. **`--force-recreate app`** é essencial: o backend carrega o índice **na
       memória ao iniciar**; sem recriar o contêiner, ele continua servindo o
       índice antigo.
    3. **`FLUSHALL`** limpa respostas antigas do cache (senão as correções não
       aparecem, mesmo com o índice novo).

Validação após atualizar:

```bash
curl -s -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"sua pergunta de teste"}' | python3 -m json.tool
```

## Gerenciar o modelo do Ollama

```bash
# listar modelos baixados
docker exec fctebot-ollama ollama list
# baixar/atualizar o modelo configurado no .env
make prod-model
# baixar um modelo específico
docker exec fctebot-ollama ollama pull qwen2.5:7b
```

Trocar de modelo: ajuste `OLLAMA_MODEL` no `.env`, baixe-o e recrie o `app`.

## Cache

```bash
# estatísticas
curl -s http://localhost:8000/cache/stats | python3 -m json.tool
# limpar tudo (após mudanças na base ou respostas ruins cacheadas)
docker exec fctebot-redis redis-cli FLUSHALL
# ou via API
curl -X DELETE http://localhost:8000/cache
```

## Backup e restauração

O que preservar:

- **`Infos Adms UnB/`** — conteúdo-fonte (idealmente versionado no Git).
- **`data/`** — índices gerados (reconstruíveis via `ingest.py`, mas o backup
  economiza tempo de reindexação).
- **`.env`** — configuração e segredos (**não** versionar).
- **Volume `redis-data`** — cache (não crítico; pode ser descartado).

```bash
# backup dos índices e da base
tar czf backup-$(date +%F).tgz "Infos Adms UnB" data .env
```

## Reiniciar / atualizar código

```bash
# reiniciar apenas o backend
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate app

# atualizar código a partir do Git e reconstruir
git pull --ff-only
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build app
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate app
```

## Rollback

```bash
# voltar para um commit/tag anterior e reconstruir
git checkout <tag_ou_commit>
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

Para reverter apenas a base de conhecimento, restaure `Infos Adms UnB/` do
backup e repita o [procedimento de atualização](#atualizar-a-base-de-conhecimento-procedimento-padrao).

## Logs

```bash
docker logs -f fctebot-app        # backend
docker logs -f fctebot-ollama     # LLM
docker logs -f fctebot-frontend   # nginx do frontend
```

> **TODO (continuidade):** configurar rotação de logs (`logs/` cresce
> indefinidamente) e retenção. Sugestão: `logrotate` no host ou driver de log
> `json-file` com `max-size`/`max-file` no Compose.

## Checklist rápido de plantão

- [ ] `/health` retorna `ok` e `index_chunks` > 0?
- [ ] `ollama: true`? Modelo baixado (`ollama list`)?
- [ ] Frontend acessível e respondendo?
- [ ] Após editar a base: ingest + recreate app + flush cache feitos?

Falhas específicas: ver [Incidentes](incidentes.md).
