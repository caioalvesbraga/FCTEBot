# Dívida técnica

Pendências conhecidas, com impacto e sugestão de correção. Mantenha esta lista
viva: ao resolver um item, remova-o e registre no CHANGELOG.

## Inconsistências de configuração/documentação

| # | Item | Impacto | Correção sugerida |
|---|---|---|---|
| 1 | **Path da KB divergente:** runtime usa `Infos Adms UnB/`, mas `knowledge_base/README.md` e o README raiz apontam para `knowledge_base/` | Confunde novos mantenedores | Padronizar docs para `Infos Adms UnB/` ou migrar a KB para `knowledge_base/` e ajustar `.env` |
| 2 | **GitHub Actions** monitora `knowledge_base/**` | Ingestão automática não dispara nas mudanças reais | Ajustar o `paths` do workflow para a pasta real |
| 3 | **Portas no README:** Grafana citado em `:3000`, mas o frontend ocupa `:3000` e Grafana `:3001` | Documentação incorreta | Corrigir o README |
| 4 | **Default de `KNOWLEDGE_BASE_PATH`** em `config.py` é `knowledge_base`, mas `.env.example` usa `Infos Adms UnB` | Comportamento depende do `.env` | Alinhar o default ao path real |

## Segurança

| # | Item | Impacto | Correção sugerida |
|---|---|---|---|
| 5 | **`POST /ingest` sem autenticação**, apesar de o CI enviar `Bearer` | Reingestão pode ser disparada por qualquer um se exposta | Exigir token/segredo na rota |

## Legado e duplicação

| # | Item | Impacto | Correção sugerida |
|---|---|---|---|
| 6 | **Código legado v1** na raiz (`main.py`, `rag_logic.py`, `handlers/`, `utils/`, scripts Pinecone/MySQL) convive com a v2 | Ruído; risco de rodar o arquivo errado | Arquivar em `legacy/` ou remover; documentar a transição |
| 7 | **Duas UIs de chat:** Vue (`frontend/`) e estática em `/chat` (FastAPI) | Ambiguidade sobre qual é oficial | Definir a oficial e remover/depreciar a outra |

## Qualidade

| # | Item | Impacto | Correção sugerida |
|---|---|---|---|
| 8 | **Sem testes automatizados** (`tests/` inexistente) | Regressões passam despercebidas | Criar suíte pytest + CI (ver [Testes](../desenvolvimento/testes.md)) |
| 9 | **Sem rotação de logs** | `logs/` cresce indefinidamente | `logrotate` ou limites no driver de log do Docker |
| 10 | **`MAX_TOKENS` padrão baixo (300)** no `.env.example` | Respostas truncadas se copiado sem ajuste | Elevar o padrão para ~2048 |

> Cada item resolvido merece uma nota no
> [CHANGELOG](https://github.com/SEU_USUARIO/FCTEBot/blob/main/CHANGELOG.md) e,
> quando for decisão arquitetural, um [ADR](../arquitetura/decisoes/index.md).
