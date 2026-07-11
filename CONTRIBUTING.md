# Contribuindo com o FCTEBot

Obrigado por contribuir! Este guia resume o essencial. A versão completa está na
documentação: [Desenvolvimento → Contribuindo](docs/desenvolvimento/contribuindo.md).

## Antes de começar

- Rode o projeto localmente: veja [Setup local](docs/desenvolvimento/setup-local.md).
- Entenda a arquitetura: [Visão geral](docs/arquitetura/visao-geral.md).

## Fluxo

1. Crie um branch: `feat/…`, `fix/…`, `docs/…`.
2. Faça commits no padrão **Conventional Commits**
   (`fix(kb): corrige prazo do TCE`).
3. Abra um Pull Request usando o template e descreva o *porquê* e como testar.

## Padrões

- **Python:** PEP 8 (sugestão: `ruff` + `black`).
- **Vue/TS:** siga o estilo existente.
- **Base de conhecimento:** siga o [Manual da KB](docs/base-conhecimento/manual.md)
  e lembre-se: *ingest --force → recreate app → FLUSHALL*.
- **Decisões arquiteturais:** registre um
  [ADR](docs/arquitetura/decisoes/index.md).

## Documentação

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

## Reportando problemas

Abra uma *issue* usando os templates em `.github/ISSUE_TEMPLATE/`.
