# Glossário

Termos e siglas usados no projeto e no domínio acadêmico da UnB. Manter este
glossário atualizado (e refletido na base de conhecimento) evita que o LLM
**invente** expansões de siglas.

!!! danger "Termo que NÃO existe"
    **"Central de Atendimento ao Estudante"** — não existe na UnB. Já foi
    alucinada pelo modelo ao expandir a sigla *CAO*. O nome correto é
    **Comissão de Acompanhamento e Orientação** (ver abaixo).

## Siglas da UnB (domínio)

| Sigla | Significado |
|---|---|
| **CAO** | Comissão de Acompanhamento e Orientação (vinculada ao DEG; contato `caodeg@unb.br`) |
| **CEG** | Câmara de Ensino de Graduação |
| **CEPE** | Conselho de Ensino, Pesquisa e Extensão |
| **DAIA** | Diretoria de Acompanhamento e Integração Acadêmica |
| **DEG** | Decanato de Ensino de Graduação |
| **DEX** | Decanato de Extensão |
| **FCTE** | Faculdade de Ciências e Tecnologias em Engenharia (ex-FGA) |
| **IRA** | Índice de Rendimento Acadêmico |
| **PPC** | Projeto Pedagógico do Curso |
| **SAA** | Secretaria de Administração Acadêmica |
| **SEI** | Sistema Eletrônico de Informações |
| **SIGAA** | Sistema Integrado de Gestão de Atividades Acadêmicas |
| **TCE** | Termo de Compromisso de Estágio |
| **TGM / TGMJ** | Trancamento Geral de Matrícula / … Justificado |
| **TR / TJ** | Trancamento parcial (automático) / … Justificado |

## Termos técnicos (arquitetura)

| Termo | Significado |
|---|---|
| **RAG** | Retrieval-Augmented Generation — geração de respostas ancorada em documentos recuperados |
| **Chunk** | Trecho de documento indexado (tamanho por `CHUNK_SIZE`) |
| **Embedding** | Representação vetorial de texto para busca semântica |
| **FAISS** | Biblioteca de busca vetorial (recuperação densa) |
| **TF-IDF** | Recuperação esparsa por frequência de termos |
| **RRF** | Reciprocal Rank Fusion — funde rankings de recuperadores diferentes |
| **Cross-encoder** | Modelo de re-ranking que pontua par (pergunta, trecho) |
| **Fallback** | Uso do Gemini quando o modelo local falha ou tem baixa confiança |
| **L1 / L2 (cache)** | Cache exato (hash) / cache semântico (similaridade) |
| **Circuit breaker** | Proteção que interrompe chamadas a um serviço instável |

> **Continuidade:** ao adicionar uma sigla nova ao produto, registre-a aqui **e**
> em `Infos Adms UnB/infos-gerais.md` (seção "SIGLAS IMPORTANTES").
