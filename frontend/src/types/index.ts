export type MessageRole = 'user' | 'bot'
export type LlmMode = 'cached' | 'local' | 'gemini' | 'error'

export interface Message {
  id: string
  role: MessageRole
  text: string
  timestamp: string
  mode?: LlmMode
  latencySeconds?: number
  confidence?: number
  error?: boolean
}

export interface ApiQueryRequest {
  query: string
}

export interface ApiQueryResponse {
  response: string
  sources: string[]
  mode: LlmMode
  confidence: number
  latency_ms: number
  cache_hit: string
  model_used: string
}

export interface ApiHealthResponse {
  status: string
  llm_strategy: string
  ollama_model: string
  gemini_key_valid: boolean
  pipeline_ready: boolean
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  messages: Message[]
}
