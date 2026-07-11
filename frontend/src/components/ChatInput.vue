<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function resize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 140)}px`
}

async function submit() {
  const value = text.value.trim()
  if (!value || chat.isLoading) return
  text.value = ''
  await nextTick()
  resize()
  chat.sendMessage(value)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="input-area">
    <div class="input-wrap" :class="{ 'input-wrap--loading': chat.isLoading }">
      <textarea
        ref="textareaRef"
        v-model="text"
        @input="resize"
        @keydown="onKeydown"
        placeholder="Digite sua pergunta… (Enter para enviar, Shift+Enter para nova linha)"
        :disabled="chat.isLoading"
        rows="1"
        maxlength="2000"
        aria-label="Campo de mensagem"
      />
      <button
        class="send-btn"
        @click="submit"
        :disabled="!text.trim() || chat.isLoading"
        aria-label="Enviar mensagem"
      >
        <svg v-if="!chat.isLoading" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
        <svg v-else class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2a10 10 0 1 0 10 10"/>
        </svg>
      </button>
    </div>
    <p class="input-hint">FCTEBot pode cometer erros. Verifique informações importantes.</p>
  </div>
</template>

<style scoped>
.input-area {
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  padding: 12px 20px 8px;
}

.input-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 8px 8px 8px 14px;
  transition: border-color 0.15s;
}
.input-wrap:focus-within { border-color: var(--color-primary); }
.input-wrap--loading { opacity: 0.7; }

textarea {
  flex: 1;
  border: none;
  background: none;
  outline: none;
  font-family: var(--font);
  font-size: 14px;
  color: var(--color-text);
  resize: none;
  line-height: 1.5;
  max-height: 140px;
  padding: 0;
  scrollbar-width: thin;
}
textarea::placeholder { color: var(--color-placeholder); }
textarea:disabled { cursor: not-allowed; }

.send-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border: none;
  border-radius: 8px;
  background: var(--color-navy);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.send-btn svg { width: 16px; height: 16px; }
.send-btn:hover:not(:disabled) { background: var(--color-primary-hover); }
.send-btn:disabled { background: var(--color-border); cursor: not-allowed; }

@keyframes spin { to { transform: rotate(360deg); } }
.spin { animation: spin 0.8s linear infinite; }

.input-hint {
  font-size: 10.5px;
  color: var(--color-text-secondary);
  text-align: center;
  margin-top: 6px;
  opacity: 0.7;
}
</style>
