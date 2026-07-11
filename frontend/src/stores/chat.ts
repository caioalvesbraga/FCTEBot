import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useStorage } from '@vueuse/core'
import { useApi } from '@/composables/useApi'
import type { Message, ChatSession, ApiHealthResponse } from '@/types'

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

function newSession(): ChatSession {
  return { id: generateId(), title: 'Nova conversa', createdAt: new Date().toISOString(), messages: [] }
}

export const useChatStore = defineStore('chat', () => {
  const { query, health } = useApi()

  // Histórico persistido no localStorage (máximo 10 sessões)
  const sessions = useStorage<ChatSession[]>('fctebot-sessions', [newSession()])
  const activeSessionId = useStorage<string>('fctebot-active-session', sessions.value[0]?.id ?? '')

  const isLoading = ref(false)
  const apiStatus = ref<'unknown' | 'online' | 'offline'>('unknown')
  const apiHealth = ref<ApiHealthResponse | null>(null)

  const activeSession = computed<ChatSession | undefined>(
    () => sessions.value.find(s => s.id === activeSessionId.value),
  )

  const messages = computed<Message[]>(() => activeSession.value?.messages ?? [])

  // ── Sessões ────────────────────────────────────────────────────

  function startNewSession() {
    const session = newSession()
    sessions.value = [session, ...sessions.value.slice(0, 9)]
    activeSessionId.value = session.id
  }

  function switchSession(id: string) {
    activeSessionId.value = id
  }

  function deleteSession(id: string) {
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (activeSessionId.value === id) {
      if (sessions.value.length === 0) startNewSession()
      else activeSessionId.value = sessions.value[0].id
    }
  }

  // ── Mensagens ──────────────────────────────────────────────────

  function addMessage(msg: Omit<Message, 'id' | 'timestamp'>): Message {
    const full: Message = { ...msg, id: generateId(), timestamp: new Date().toISOString() }
    const session = activeSession.value
    if (!session) return full

    session.messages.push(full)

    // Título da sessão = primeiras palavras da 1ª mensagem do usuário
    if (session.messages.length === 1 && msg.role === 'user') {
      session.title = msg.text.slice(0, 48) + (msg.text.length > 48 ? '…' : '')
    }

    return full
  }

  // ── API ────────────────────────────────────────────────────────

  async function sendMessage(text: string): Promise<void> {
    if (isLoading.value || !text.trim()) return

    addMessage({ role: 'user', text: text.trim() })
    isLoading.value = true

    try {
      const response = await query({ query: text.trim() })
      addMessage({
        role: 'bot',
        text: response.response,
        mode: response.mode,
        latencySeconds: response.latency_ms / 1000,
        confidence: response.confidence,
      })
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return

      const errorText = err instanceof Error ? err.message : 'Erro desconhecido'
      addMessage({
        role: 'bot',
        text: `Não foi possível obter uma resposta: ${errorText}`,
        error: true,
      })
    } finally {
      isLoading.value = false
    }
  }

  async function checkHealth(): Promise<void> {
    try {
      apiHealth.value = await health()
      apiStatus.value = 'online'
    } catch {
      apiStatus.value = 'offline'
      apiHealth.value = null
    }
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    isLoading,
    apiStatus,
    apiHealth,
    startNewSession,
    switchSession,
    deleteSession,
    sendMessage,
    checkHealth,
  }
})
