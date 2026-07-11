# Scripts de automação

Todos os scripts ficam em `scripts/`. Esta página resume o propósito e o uso de
cada um relacionado à base de conhecimento e à ingestão.

## Ingestão

### `ingest.py`

Reindexa toda a base de conhecimento (FAISS + TF-IDF) a partir de
`KNOWLEDGE_BASE_PATH`.

```bash
python scripts/ingest.py --force        # recria os índices mesmo que já existam
python scripts/ingest.py --kb-path /caminho/docs/
# no contêiner:
docker exec fctebot-app python scripts/ingest.py --force
```

Sem `--force`, o script pergunta antes de sobrescrever um índice existente.

### `ingest_pdf.py`

Pipeline genérico PDF → Markdown → ingestão, para adicionar documentos sem
depender de edição manual.

```bash
python scripts/ingest_pdf.py --url "https://.../norma.pdf" --name "norma-xyz"
python scripts/ingest_pdf.py --file ./norma.pdf --name "politica-tcc-2026"
# flags: --title "Título" | --no-ingest | --force | --dry-run
```

## Atualização automática de conteúdo oficial

### `update_calendario.py`

Verifica o site da SAA, detecta o calendário acadêmico mais recente por semestre
e o ingere automaticamente.

```bash
python scripts/update_calendario.py             # verifica e atualiza se houver novo
python scripts/update_calendario.py --dry-run    # só verifica
python scripts/update_calendario.py --force      # força mesmo sem versão nova
python scripts/update_calendario.py --no-ingest  # atualiza o .md sem reindexar
```

### `update_normativos.py`

Faz scraping de normativos da SAA/UnB, usando um **manifesto de hash** para
detectar mudanças e reingerir apenas o que mudou.

### `setup_cron.sh`

Agenda a atualização mensal (calendário + normativos) via cron no WSL/Linux.

```bash
bash scripts/setup_cron.sh            # instala (dia 1º às 06:00 BRT)
bash scripts/setup_cron.sh --status   # ver agendamento
bash scripts/setup_cron.sh --remove   # remover
```

## Infra / deploy (referência cruzada)

Estes não mexem na KB, mas participam do ciclo de vida:

| Script | Uso |
|---|---|
| `entrypoint.sh` | Entrypoint do contêiner: na 1ª subida atualiza docs, ingere e sobe a API |
| `oracle-setup.sh`, `vast-setup.sh`, `runpod-setup.sh` | Setup por provedor |
| `bundle-for-cloud.sh`, `cloud-preflight.sh` | Empacotamento e validação para GPU cloud |
| `test_gemini.py` | Testa conectividade/modelos Gemini via `.env` |

Ver [Operação → Deploy](../operacao/deploy.md).

## Ingestão via CI

Há um workflow em `.github/workflows/ingest.yml` que dispara `POST /ingest` no
servidor remoto.

!!! warning "Pendências do workflow"
    - Ele monitora `knowledge_base/**`, mas a pasta real é `Infos Adms UnB/`.
    - Envia `Authorization: Bearer`, porém a rota `/ingest` **não implementa
      autenticação**. Ver [Dívida técnica](../continuidade/divida-tecnica.md).
