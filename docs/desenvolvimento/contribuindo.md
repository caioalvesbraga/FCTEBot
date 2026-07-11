# Contribuindo

Guia para quem for evoluir o FCTEBot. Veja também o
[`CONTRIBUTING.md`](https://github.com/caioalvesbraga/FCTEBot/blob/main/CONTRIBUTING.md)
na raiz.

## Fluxo de trabalho (Git)

1. Crie um branch a partir de `main`: `feat/…`, `fix/…`, `docs/…`, `refactor/…`.
2. Faça commits pequenos e descritivos (ver convenção abaixo).
3. Abra um Pull Request usando o template; descreva o *porquê* e como testar.
4. Garanta que o build do frontend e a subida do backend funcionam.

## Convenção de commits

Recomenda-se **Conventional Commits**:

```
tipo(escopo): descrição curta no imperativo

Corpo opcional explicando o porquê.
```

Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.
Exemplo: `fix(kb): corrige prazo de envio do TCE para 15 dias`.

## Estilo de código

- **Python:** siga PEP 8. Sugestão de ferramentas: `ruff` (lint) e `black`
  (format). Type hints onde fizer sentido.
- **Vue/TS:** siga o estilo existente; componentes em PascalCase; stores Pinia
  por domínio.
- **Comentários:** expliquem *decisões/intenção*, não o óbvio.

## Ao mexer na base de conhecimento

Siga o [Manual da KB](../base-conhecimento/manual.md): editar → enviar →
`ingest --force` → recriar `app` → `FLUSHALL` → validar.

## Ao tomar decisões arquiteturais

Registre um [ADR](../arquitetura/decisoes/index.md) usando o template.

## Documentação

Esta documentação vive em `docs/` (MkDocs Material). Para pré-visualizar:

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

> **TODO (continuidade):** adicionar CI de lint/format/testes/build
> (`.github/workflows/`); hoje só existe o workflow de ingestão.
