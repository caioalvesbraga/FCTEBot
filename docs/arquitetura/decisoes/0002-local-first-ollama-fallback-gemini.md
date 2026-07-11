# ADR-0002 — Local-first (Ollama + fallback Gemini)

- **Status:** Aceito
- **Data:** 2026-06-01
- **Decisores:** Caio Braga

## Contexto

O projeto é um TCC com restrições de custo e uma tese central: verificar a
**viabilidade de assistentes educacionais baseados em modelos de código aberto
locais**. Ao mesmo tempo, é desejável não degradar a experiência quando o modelo
local estiver indisponível ou pouco confiável.

## Decisão

Adotar uma estratégia **local-first** configurável via `LLM_STRATEGY`:

- `local_first` (padrão): usa **Ollama** (modelo aberto, ex.: `qwen2.5:7b`) e só
  recorre ao **Gemini** como *fallback* quando o Ollama falha ou a confiança fica
  abaixo de `CONFIDENCE_THRESHOLD`.
- `local_only`: nunca usa Gemini (cenário 100% aberto/offline).
- `gemini_only`: ignora o Ollama (útil para comparação/baseline).

A resiliência é garantida por *circuit breaker* e retentativas (`tenacity`).

## Alternativas consideradas

- **Apenas API paga (Gemini/OpenAI):** melhor qualidade imediata, mas custo
  recorrente e dependência externa — contraria a tese do TCC.
- **Apenas local, sem fallback:** 100% aberto, porém frágil em CPU lenta ou
  falhas do Ollama, prejudicando a validação com usuários.

## Consequências

- **Positivas:** custo próximo de zero em operação local; independência de
  fornecedor; a tese do TCC pode ser avaliada empiricamente comparando modos.
- **Trade-offs:** em CPU, a latência do modelo local é alta (segundos); GPU
  (ex.: Vast.ai) resolve, mas adiciona custo/operação.
- **Riscos:** divergência de qualidade entre modos — mitigada por avaliação e
  pelo *fallback*.

## Referências

- `src/rag/generator.py`
- Variáveis: `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `GEMINI_API_KEY`, `LLM_STRATEGY`,
  `CONFIDENCE_THRESHOLD`
