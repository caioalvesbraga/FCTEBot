# Manual da base de conhecimento

A **base de conhecimento (KB)** é o conjunto de documentos que o FCTEBot usa para
responder. Manter esses documentos corretos e atualizados é a atividade de
manutenção mais frequente e de maior impacto na qualidade das respostas.

## Onde ficam os documentos

- **Pasta efetiva:** `Infos Adms UnB/` (na raiz do projeto) — ~45 arquivos
  Markdown, montados no contêiner via volume `:rw` e definidos por
  `KNOWLEDGE_BASE_PATH=Infos Adms UnB` no `.env`.
- **Índices gerados:** `data/` (`faiss.index`, `tfidf.pkl`, metadados) — criados
  pela ingestão; não edite à mão.

!!! warning "Inconsistência conhecida"
    Existe uma pasta `knowledge_base/` com apenas um `README.md` descrevendo uma
    estrutura planejada que **não é a usada em runtime**. A fonte real é
    `Infos Adms UnB/`. Ver [Dívida técnica](../continuidade/divida-tecnica.md).

## Anatomia de um documento

Cada arquivo `.md` cobre um tema (matrícula, estágio, TCC…). Boas práticas:

- Comece com um título `#` e use subtítulos `##`/`###` por assunto.
- Escreva em **português**, de forma objetiva e factual.
- Ao final, inclua **fonte** e **data de atualização**:

```markdown
# Estágio — FCTE/UnB

## Termo de Compromisso de Estágio (TCE)
- Deve ser enviado à coordenação do curso com pelo menos 15 dias de antecedência...

**Fonte:** DEG/UnB — Orientações Gerais Sobre Estágio
Atualização: 10/07/2026
```

## Como atualizar (fluxo recomendado)

1. **Edite** o `.md` correspondente em `Infos Adms UnB/`.
2. **Envie** ao servidor (deploy remoto):

    ```bash
    scp -P <PORT> -i ~/.ssh/<chave> -r \
      "/mnt/c/Users/caiob/Downloads/TCC/FCTEBot/Infos Adms UnB" \
      root@<HOST>:/root/FCTEBot/
    ```

3. **Reindexe + recrie o app + limpe o cache** (os três passos são obrigatórios;
   ver [Runbook](../operacao/runbook.md)):

    ```bash
    ssh -p <PORT> -i ~/.ssh/<chave> root@<HOST> "
      cd /root/FCTEBot &&
      docker exec fctebot-app python scripts/ingest.py --force &&
      docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --force-recreate app &&
      docker exec fctebot-redis redis-cli FLUSHALL
    "
    ```

4. **Valide** com uma pergunta relacionada ao que mudou.

## Adicionar documentos a partir de PDFs

O script `ingest_pdf.py` baixa/converte um PDF em Markdown e o adiciona à KB:

```bash
# a partir de uma URL
python scripts/ingest_pdf.py --url "https://deg.unb.br/norma.pdf" --name "norma-xyz"
# a partir de um arquivo local
python scripts/ingest_pdf.py --file /caminho/norma.pdf --name "politica-tcc-2026"
```

Detalhes e outros scripts em [Scripts de automação](scripts-automacao.md).

## Dicas de qualidade

- **Um tema por arquivo:** facilita a recuperação e evita *chunks* misturados.
- **Evite duplicação:** conteúdo repetido em vários arquivos degrada o retrieval.
- **Defina siglas ao menos uma vez** (ver [Glossário](glossario.md)) para o LLM
  não inventar expansões.
- **Datas explícitas:** ajudam o modelo e o mantenedor a saber o que está velho.
- Após grandes mudanças, rode a [avaliação](../qualidade/avaliacao.md) para
  detectar regressões.

## Chunking

Controlado por `CHUNK_SIZE` (512) e `CHUNK_OVERLAP` (64). Se documentos muito
longos estiverem sendo cortados no meio de ideias, ajuste esses valores e
reindexe.
