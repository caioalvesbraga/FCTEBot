# Changelog

Todas as mudanças relevantes deste projeto serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o versionamento segue [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- Documentação técnica completa em `docs/` (MkDocs Material): arquitetura, ADRs,
  runbook de operação, manual da base de conhecimento, referência de API e
  configuração, glossário, e seção de continuidade (handoff, roadmap, dívida
  técnica).
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CHANGELOG.md` e templates de issue/PR.

## [2.0.0]

### Adicionado
- Arquitetura RAG local-first: recuperação híbrida (TF-IDF + FAISS + RRF),
  re-ranking por cross-encoder, geração via Ollama com fallback Gemini.
- Cache multinível (Redis L1/L2).
- Frontend Vue 3 e observabilidade (Prometheus + Grafana).
- Avaliação com RAGAS e comparação baseline.

### Alterado
- Correções na base de conhecimento a partir da validação com usuários (prazos
  de TCE, trancamentos, contatos da coordenação/secretaria, reintegração,
  aproveitamento de estudos).

## [1.0.0]

### Adicionado
- Versão inicial (legado): bot Telegram com MySQL e Pinecone/Gemini via LangChain.
