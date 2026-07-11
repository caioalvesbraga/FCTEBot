# Segurança e LGPD

Considerações de segurança e privacidade. Esta página consolida o que já existe
e aponta o que falta endereçar.

## Dados pessoais tratados

- **ID de usuário do Telegram / `user_id`** — usado para rate limiting e
  métricas. Evite persistir dados pessoais além do necessário.
- **Perguntas dos usuários** — podem ser armazenadas em **cache (Redis)** e em
  **logs**. Perguntas podem conter dados pessoais (matrícula, nome).

### Princípios (LGPD)

- **Minimização:** colete/armazene o mínimo necessário.
- **Retenção:** defina TTL/expurgo. O cache já expira (`CACHE_L1_TTL`,
  `CACHE_L2_TTL`); logs precisam de política de retenção.
- **Transparência:** informe ao usuário que é um bot e como os dados são usados.

## Superfície de segurança

| Item | Estado | Ação recomendada |
|---|---|---|
| HTTPS (produção) | OK via Caddy (Let's Encrypt) | Manter |
| Rate limiting | OK (`RATE_LIMIT_PER_USER`) | Ajustar conforme carga |
| Sanitização de saída no frontend | OK (DOMPurify) | Manter |
| `POST /ingest` sem autenticação | **Risco** | Adicionar token/segredo antes de expor |
| Segredos em `.env` | OK (não versionado) | Garantir no `.gitignore`; rotacionar tokens |
| CORS | Configurado em `main.py` | Restringir origens em produção |
| Guardrails de conteúdo | OK (temas sensíveis → secretaria) | Revisar periodicamente |

## Boas práticas de segredos

- Nunca commitar `.env`, tokens do Telegram ou chaves Gemini.
- Rotacione o token do bot se houver exposição.
- Em CI, use *secrets* do repositório (não hardcode).

> **TODO (continuidade):**
> - Implementar autenticação na rota `/ingest` (ver [Dívida técnica](../continuidade/divida-tecnica.md)).
> - Definir política formal de retenção de logs e expurgo.
> - Elaborar aviso de privacidade para os usuários do bot.
