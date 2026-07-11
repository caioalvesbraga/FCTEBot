# Playbook de incidentes

Falhas comuns e como resolvê-las. Para procedimentos de rotina, veja o
[Runbook](runbook.md).

## O bot responde com informação desatualizada

**Sintoma:** a base foi editada, mas a resposta mantém o conteúdo antigo.

**Causas e correção (em ordem):**

1. **Cache** servindo resposta antiga → `docker exec fctebot-redis redis-cli FLUSHALL`.
   (Confirme: se a resposta traz `"cache_hit": "l1"`/`"l2"`, era cache.)
2. **Índice não recarregado** → recrie o backend:
   `docker compose ... up -d --force-recreate app`. O índice é carregado na
   memória ao iniciar.
3. **Ingestão não executada** → `docker exec fctebot-app python scripts/ingest.py --force`.
4. **Arquivo não chegou ao servidor** → confirme:
   `docker exec fctebot-app grep -n "texto novo" "/app/Infos Adms UnB/arquivo.md"`.
5. **Correção de código (`src/`) não aplicada** → se o arquivo em disco já está
   correto mas o `/query` responde o antigo com `"cache_hit": "none"`, a **imagem
   Docker está velha**. O `src/` é embutido na imagem, então `--force-recreate`
   não basta: reconstrua com
   `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build app`.
   Ver [Runbook → Atualizar o código](runbook.md#atualizar-o-codigo-src-exige-build).

## `/health` retorna `degraded` ou `error`

- `degraded` (retriever `false`): índice ausente → rode a ingestão e recrie o app.
- `error` (HTTP 503): backend não inicializou → `docker logs fctebot-app`.

## Ollama fora do ar / respostas não chegam

```bash
docker logs --tail 50 fctebot-ollama
docker exec fctebot-ollama ollama list      # modelo baixado?
curl -s http://localhost:11434/api/tags     # servidor responde?
```

- Modelo ausente → `make prod-model` ou `ollama pull <modelo>`.
- Timeout em CPU → aumente `OLLAMA_TIMEOUT` (ex.: 300) e recrie o app.
- Mitigação temporária → `LLM_STRATEGY=gemini_only` (exige `GEMINI_API_KEY`).

## Resposta truncada / cortada

Verifique `MAX_TOKENS` no `.env` (valor baixo, ex.: 300, corta respostas longas).
Ajuste para 2048 e recrie o app:

```bash
sed -i 's/^MAX_TOKENS=.*/MAX_TOKENS=2048/' .env
docker compose ... up -d --force-recreate app
```

## Resposta com trechos em inglês ou siglas inventadas

- Trechos em inglês: comportamento do LLM; limpe o cache e valide de novo. Se
  persistir, revise o prompt em `src/rag/generator.py`.
- Siglas inventadas (ex.: expandir "CAO" errado): garanta que a sigla está
  definida na base (ver [Glossário](../base-conhecimento/glossario.md)) e
  reindexe.

## Frontend não carrega / não renderiza a resposta

```bash
docker logs --tail 30 fctebot-frontend
```

- Confirme que `fctebot-app` está `healthy` antes do frontend.
- Erros de renderização de Markdown já ocorreram (`marked` recebendo `null`);
  garanta que o backend retorna `response` não vazio.

## Certificado TLS não gerado (produção Caddy)

- Portas 80/443 abertas no firewall/security list.
- Domínio resolvendo para o IP correto.
- `docker logs fctebot-caddy`.

> **TODO (continuidade):** registrar aqui novos incidentes conforme ocorrerem,
> com sintoma → causa → correção.
