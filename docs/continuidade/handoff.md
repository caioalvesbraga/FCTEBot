# Handoff — onboarding do próximo mantenedor

Bem-vindo(a) ao FCTEBot. Esta página é o seu ponto de partida para assumir o
projeto. Leitura estimada: 10 minutos.

## O que é

Assistente virtual (Telegram + web) que responde dúvidas administrativas da
FCTE/UnB usando RAG local-first. Produto de TCC2 de Engenharia de Software.

## Suas 3 primeiras horas

1. Leia [Arquitetura → Visão geral](../arquitetura/visao-geral.md) e
   [Pipeline RAG](../arquitetura/pipeline-rag.md).
2. Rode localmente seguindo [Setup local](../desenvolvimento/setup-local.md).
3. Faça uma pergunta em `POST /query` e acompanhe os logs.
4. Edite um `.md` da base e execute o
   [fluxo de atualização](../base-conhecimento/manual.md) ponta a ponta.

## Onde estão as coisas

| Preciso de… | Vá para |
|---|---|
| Entender o *porquê* das decisões | [ADRs](../arquitetura/decisoes/index.md) |
| Rodar / desenvolver | [Setup local](../desenvolvimento/setup-local.md), [Estrutura do código](../desenvolvimento/estrutura-codigo.md) |
| Colocar em produção | [Deploy](../operacao/deploy.md) |
| Operar no dia a dia | [Runbook](../operacao/runbook.md) |
| Resolver falhas | [Incidentes](../operacao/incidentes.md) |
| Atualizar conteúdo | [Manual da KB](../base-conhecimento/manual.md) |
| Configurar variáveis | [Configuração](../referencia/configuracao.md) |
| Saber o que fazer a seguir | [Roadmap](roadmap.md), [Dívida técnica](divida-tecnica.md) |

## Conhecimento tácito importante

- **A regra de ouro ao atualizar a base:** *ingest --force* → *recreate app* →
  *FLUSHALL*. Pular qualquer passo faz o bot continuar respondendo o antigo.
- **Base real** é `Infos Adms UnB/` (não `knowledge_base/`).
- **CPU é lento** (segundos por resposta). Produção usa **GPU** (Vast.ai/RunPod).
- **Local-first:** com `LLM_STRATEGY=local_only` o sistema roda 100% aberto,
  sem Gemini.
- **Não invente siglas:** defina-as na base (ver [Glossário](../base-conhecimento/glossario.md)).

## Acessos que você vai precisar (preencher)

> **TODO:** registrar (em local seguro, fora do Git) — repositório, credenciais
> do provedor GPU, token do bot (@BotFather), chave Gemini (se usada), acesso ao
> Grafana e ao domínio/DNS.

## Contatos

- Autor: Caio Felipe Alves Braga.
- Coordenação de Engenharia de Software: `engsoftware@unb.br`.
- Secretaria FCTE: `secretaria.fcte@unb.br` · (61) 3107-8901.
