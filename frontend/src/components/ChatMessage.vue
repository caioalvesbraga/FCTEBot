<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Message } from '@/types'

const props = defineProps<{ message: Message }>()

const renderedText = computed(() => {
  if (props.message.role === 'user') return null
  if (!props.message.text) return ''
  const html = marked.parse(props.message.text, { breaks: true, gfm: true }) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
})

const timeLabel = computed(() => {
  return new Date(props.message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

const latencyLabel = computed(() => {
  const lat = props.message.latencySeconds
  if (lat == null) return null
  return lat < 1 ? `${(lat * 1000).toFixed(0)}ms` : `${lat.toFixed(1)}s`
})

const confidenceLabel = computed(() => {
  const c = props.message.confidence
  if (c == null) return null
  return `${(c * 100).toFixed(0)}% conf.`
})

const modeBadgeClass = computed(() => {
  const m = props.message.mode
  if (m === 'cached') return 'badge--cached'
  if (m === 'gemini') return 'badge--gemini'
  if (m === 'local') return 'badge--local'
  return ''
})
</script>

<template>
  <div class="message" :class="[`message--${message.role}`, { 'message--error': message.error }]">
    <div class="message__avatar" aria-hidden="true">
      {{ message.role === 'user' ? 'V' : 'F' }}
    </div>

    <div class="message__body">
      <div class="message__author">
        <span>{{ message.role === 'user' ? 'Você' : 'FCTEBot' }}</span>
        <span class="message__time">{{ timeLabel }}</span>
      </div>

      <!-- Bot: renderiza Markdown -->
      <div
        v-if="message.role === 'bot'"
        class="message__bubble message__bubble--bot prose"
        v-html="renderedText"
      />

      <!-- Usuário: texto puro -->
      <div v-else class="message__bubble message__bubble--user">
        {{ message.text }}
      </div>

      <!-- Metadados da resposta -->
      <div v-if="message.role === 'bot' && !message.error" class="message__meta">
        <span v-if="message.mode" class="badge" :class="modeBadgeClass">
          {{ message.mode }}
        </span>
        <span v-if="latencyLabel" class="meta-chip">{{ latencyLabel }}</span>
        <span v-if="confidenceLabel" class="meta-chip">{{ confidenceLabel }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 10px;
  max-width: 80%;
  animation: fadeIn 0.15s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

.message--user { align-self: flex-end; flex-direction: row-reverse; }
.message--bot  { align-self: flex-start; }

.message__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 2px;
}
.message--user .message__avatar { background: var(--color-text-secondary); color: #fff; }
.message--bot  .message__avatar { background: var(--color-navy); color: #fff; }

.message__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }

.message__author {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  font-weight: 500;
}
.message--user .message__author { flex-direction: row-reverse; }

.message__time { font-weight: 400; opacity: 0.75; }

.message__bubble {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message__bubble--user {
  background: var(--color-navy);
  color: #fff;
  border-bottom-right-radius: 3px;
  white-space: pre-wrap;
}

.message__bubble--bot {
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-primary);
  border-bottom-left-radius: 3px;
}

.message--error .message__bubble--bot {
  border-left-color: #ef4444;
  background: var(--color-error-bg);
  color: var(--color-error-text);
}

/* Markdown (prose) styles dentro do bubble bot */
.prose :deep(p)          { margin: 0 0 0.6em; }
.prose :deep(p:last-child) { margin-bottom: 0; }
.prose :deep(ul),
.prose :deep(ol)         { padding-left: 1.4em; margin: 0.4em 0; }
.prose :deep(li)         { margin-bottom: 0.2em; }
.prose :deep(strong)     { font-weight: 600; color: var(--color-navy); }
.prose :deep(code)       { background: var(--color-surface-alt); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
.prose :deep(pre)        { background: var(--color-surface-alt); padding: 10px; border-radius: 6px; overflow-x: auto; margin: 0.5em 0; }
.prose :deep(pre code)   { background: none; padding: 0; }
.prose :deep(a)          { color: var(--color-link); text-decoration: underline; }
.prose :deep(blockquote) { border-left: 3px solid var(--color-border); padding-left: 10px; margin: 0.5em 0; color: var(--color-text-secondary); }

/* Meta */
.message__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.message--user .message__meta { justify-content: flex-end; }

.badge {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 10px;
  border: 1px solid currentColor;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.badge--cached { color: #22c55e; }
.badge--local  { color: var(--color-primary); }
.badge--gemini { color: #8b5cf6; }

.meta-chip {
  font-size: 10.5px;
  color: var(--color-text-secondary);
}
</style>
