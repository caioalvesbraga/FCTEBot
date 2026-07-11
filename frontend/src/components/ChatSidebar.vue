<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const chat = useChatStore()
const settings = useSettingsStore()

const suggestions = [
  'Qual o prazo para trancamento parcial no 2026.1?',
  'Como solicitar aproveitamento de estudos?',
  'Quantas horas complementares preciso para me formar?',
  'Como funciona a dupla diplomação?',
  'Quais são os requisitos para o estágio obrigatório?',
  'Quando abre a matrícula do semestre 2026.2?',
  'Como funciona a revisão de menção final?',
]

function sendSuggestion(text: string) {
  chat.sendMessage(text)
}
</script>

<template>
  <aside class="sidebar" :class="{ open: settings.sidebarOpen }">
    <!-- Nova conversa -->
    <div class="sidebar-top">
      <button class="new-chat-btn" @click="chat.startNewSession()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Nova conversa
      </button>
    </div>

    <!-- Histórico de sessões -->
    <div v-if="chat.sessions.length" class="sidebar-section">
      <div class="section-label">Histórico</div>
      <ul class="session-list">
        <li
          v-for="session in chat.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === chat.activeSessionId }"
        >
          <button class="session-btn" @click="chat.switchSession(session.id)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <span class="session-title">{{ session.title }}</span>
          </button>
          <button class="session-delete" @click.stop="chat.deleteSession(session.id)" aria-label="Excluir conversa">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </li>
      </ul>
    </div>

    <!-- Sugestões -->
    <div class="sidebar-section">
      <div class="section-label">Perguntas frequentes</div>
      <button
        v-for="s in suggestions"
        :key="s"
        class="suggestion-btn"
        @click="sendSuggestion(s)"
        :disabled="chat.isLoading"
      >
        {{ s }}
      </button>
    </div>

    <!-- Status da API -->
    <div v-if="chat.apiHealth" class="sidebar-section sidebar-status">
      <div class="section-label">Status da API</div>
      <div class="status-row">
        <span>Modelo</span>
        <span class="status-val">{{ chat.apiHealth.ollama_model }}</span>
      </div>
      <div class="status-row">
        <span>Estratégia</span>
        <span class="status-val">{{ chat.apiHealth.llm_strategy }}</span>
      </div>
      <div class="status-row">
        <span>Pipeline RAG</span>
        <span class="status-val" :class="chat.apiHealth.pipeline_ready ? 'ok' : 'err'">
          {{ chat.apiHealth.pipeline_ready ? 'Pronto' : 'Não inicializado' }}
        </span>
      </div>
    </div>

    <div class="sidebar-footer">
      <p>FCTEBot v2.0 · RAG local-first</p>
      <a href="https://fcte.unb.br/contato/" target="_blank" rel="noopener">Fale com a coordenação</a>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 248px;
  min-width: 248px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  transition: transform 0.2s ease, width 0.2s ease;
}

@media (max-width: 768px) {
  .sidebar {
    position: absolute;
    top: 0; left: 0;
    height: 100%;
    z-index: 100;
    transform: translateX(-100%);
  }
  .sidebar.open { transform: translateX(0); }
}

.sidebar-top {
  padding: 12px;
  border-bottom: 1px solid var(--color-border);
}
.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.new-chat-btn svg { width: 16px; height: 16px; flex-shrink: 0; }
.new-chat-btn:hover { background: var(--color-primary-hover); }

.sidebar-section {
  padding: 12px;
  border-bottom: 1px solid var(--color-border);
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

/* Sessões */
.session-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.session-item {
  display: flex;
  align-items: center;
  border-radius: 6px;
  overflow: hidden;
  transition: background 0.15s;
}
.session-item:hover, .session-item.active { background: var(--color-surface-alt); }
.session-item.active .session-btn { color: var(--color-primary); font-weight: 600; }
.session-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  font-family: var(--font);
  font-size: 12.5px;
  color: var(--color-text);
  min-width: 0;
}
.session-btn svg { width: 14px; height: 14px; flex-shrink: 0; color: var(--color-text-secondary); }
.session-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-delete {
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px;
  color: var(--color-text-secondary);
  opacity: 0;
  transition: opacity 0.15s;
  flex-shrink: 0;
}
.session-delete svg { width: 13px; height: 13px; }
.session-item:hover .session-delete { opacity: 1; }
.session-delete:hover { color: #ef4444; }

/* Sugestões */
.suggestion-btn {
  display: block;
  width: 100%;
  text-align: left;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 7px 10px;
  font-family: var(--font);
  font-size: 12px;
  color: var(--color-text);
  cursor: pointer;
  margin-bottom: 5px;
  line-height: 1.35;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.suggestion-btn:last-child { margin-bottom: 0; }
.suggestion-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-subtle);
}
.suggestion-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Status */
.sidebar-status { font-size: 12px; }
.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  color: var(--color-text-secondary);
}
.status-val { font-weight: 600; color: var(--color-text); }
.status-val.ok { color: #22c55e; }
.status-val.err { color: #ef4444; }

/* Footer */
.sidebar-footer {
  margin-top: auto;
  padding: 12px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.sidebar-footer p { margin-bottom: 4px; }
.sidebar-footer a { color: var(--color-link); text-decoration: none; }
.sidebar-footer a:hover { text-decoration: underline; }
</style>
