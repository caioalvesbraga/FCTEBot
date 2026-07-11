# ADR-0001 — RAG híbrido (TF-IDF + FAISS + RRF)

- **Status:** Aceito
- **Data:** 2026-06-01
- **Decisores:** Caio Braga

## Contexto

A base de conhecimento contém documentos administrativos da UnB com muitos
termos exatos e de baixa frequência (códigos de disciplina, siglas como SIGAA e
CAO, nomes de formulários), mas também exige compreensão semântica das perguntas
dos estudantes, que raramente usam a terminologia oficial.

- Recuperação puramente **densa** (embeddings) erra em correspondências léxicas
  exatas (ex.: `FGA0003`).
- Recuperação puramente **esparsa** (TF-IDF/BM25) erra quando a pergunta usa
  sinônimos ou linguagem coloquial.

## Decisão

Usar **recuperação híbrida**: combinar um recuperador esparso (TF-IDF) e um
denso (FAISS com embeddings `intfloat/multilingual-e5-base`), fundindo os
rankings com **Reciprocal Rank Fusion (RRF)**. Um **cross-encoder** faz o
re-ranking final (ver [pipeline](../pipeline-rag.md)).

Pesos e parâmetros são configuráveis: `RETRIEVAL_TFIDF_WEIGHT=0.4`,
`RETRIEVAL_DENSE_WEIGHT=0.6`, `RETRIEVAL_TOP_K=6`.

## Alternativas consideradas

- **Somente FAISS (denso):** mais simples, mas falha em termos exatos/siglas.
- **Somente TF-IDF/BM25 (esparso):** leve, mas frágil a variações de linguagem.
- **Weighted score fusion em vez de RRF:** exige normalizar escores de espaços
  diferentes; RRF opera sobre *ranks*, sendo mais robusto e simples de calibrar.

## Consequências

- **Positivas:** melhor cobertura de recuperação; robustez a diferentes estilos
  de pergunta; parâmetros ajustáveis por `.env`.
- **Trade-offs:** dois índices para manter e reconstruir na ingestão; maior custo
  de CPU/memória do que uma abordagem única.
- **Riscos:** desbalanceamento dos pesos pode degradar resultados — mitigado
  medindo com o dataset de avaliação (ver [Qualidade](../../qualidade/avaliacao.md)).

## Referências

- `src/rag/retrieval.py`, `src/rag/ingestion.py`
- Dataset de avaliação: `evaluation/questions.json`
