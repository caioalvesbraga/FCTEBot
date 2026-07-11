# Base de Conhecimento — FCTEBot

Este diretório contém os documentos que alimentam o sistema RAG do FCTEBot.

## Estrutura

```
knowledge_base/
├── matricula/           # Documentos sobre matrícula e ajustes
├── estagio/             # Regulamentos de estágio
├── horas_complementares/ # Atividades complementares
├── trancamento/         # Trancamento parcial e total
├── assistencia/         # Programas de assistência estudantil
├── curriculos/          # PPCs dos 5 cursos da FCTE
├── regulamentos/        # Regimento interno, estatutos
├── calendario/          # Calendários acadêmicos
└── contatos/            # Contatos institucionais
```

## Formatos suportados

| Formato | Extensão | Observação |
|---------|----------|------------|
| PDF | `.pdf` | Documentos oficiais, PPCs, regulamentos |
| Markdown | `.md` | Documentos editáveis, FAQs |
| Texto | `.txt` | Documentos simples |
| Word | `.docx` | Documentos Word |

## Como adicionar documentos

### Opção A — PDF por URL ou arquivo local (recomendado)

```bash
# Ingere um PDF a partir de URL (baixa, converte para .md, re-indexa)
python scripts/ingest_pdf.py \
  --url "https://deg.unb.br/resolucao-xyz.pdf" \
  --name "resolucao-xyz"

# Ingere um PDF local (já baixado)
python scripts/ingest_pdf.py \
  --file /caminho/para/norma.pdf \
  --name "politica-tcc-2026"

# Flags opcionais:
#   --title "Título Customizado"   título do cabeçalho no .md
#   --no-ingest                    só cria o .md, não re-indexa
#   --force                        sobrescreve se já existir
#   --dry-run                      simula sem alterar nada
```

### Opção B — Arquivo .md manual

1. Crie um arquivo `.md` em `Infos Adms UnB/` com o conteúdo estruturado
2. Re-indexe a base:

```bash
python scripts/ingest.py --force
# ou via Docker:
docker exec fctebot-app python scripts/ingest.py --force
```

### Atualização automática do calendário (cron mensal)

```bash
# Verifica e atualiza o calendário acadêmico automaticamente
python scripts/update_calendario.py

# Configurar cron mensal no WSL (roda todo dia 1º às 06:00 BRT)
bash scripts/setup_cron.sh

# Gerenciar o cron
bash scripts/setup_cron.sh --status   # ver agendamento atual
bash scripts/setup_cron.sh --test     # testar sem alterar
bash scripts/setup_cron.sh --remove   # remover agendamento
```

## Boas práticas

- **Mantenha os documentos atualizados**: documentos desatualizados geram respostas incorretas
- **Prefira Markdown para FAQs**: mais fácil de editar do que PDFs
- **Use nomes descritivos**: `manual_aluno_2025.pdf` ao invés de `doc1.pdf`
- **Evite documentos duplicados**: chunks redundantes degradam a qualidade do retrieval
- **Inclua metadados no início**: título, data, versão facilitam citação

## Exemplo de documento Markdown ideal

```markdown
# Manual do Aluno FCTE/UnB — 2025

**Versão:** 2025.1  
**Fonte:** Secretaria Acadêmica FCTE  
**Última atualização:** Março de 2025

## Matrícula

### Prazos de matrícula
O período de matrícula ocorre em...

### Ajuste de matrícula
O ajuste de matrícula permite...
```

## Documentos recomendados para incluir

- [ ] Manual do Aluno UnB (edição atual)
- [ ] PPCs dos cursos: Eng. Software, Eng. Aeroespacial, Eng. Automotiva, Eng. Energia, Eng. Eletrônica
- [ ] Regulamento de Estágio da FCTE
- [ ] Regulamento de Atividades Complementares
- [ ] Calendário Acadêmico (semestre atual)
- [ ] Guia de Assistência Estudantil (DAC/UnB)
- [ ] Regulamento do TCC (por curso)
- [ ] Informações de contato e localização dos setores
- [ ] Regulamento Interno da FCTE
- [ ] Regimento Geral da UnB (partes relevantes)
