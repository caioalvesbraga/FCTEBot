<script setup lang="ts">
import { nextTick, watch } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatMessage from './ChatMessage.vue'
import ChatInput from './ChatInput.vue'

const chat = useChatStore()

// Scrolla para o final sempre que uma nova mensagem chega
watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    const el = document.getElementById('messages-end')
    el?.scrollIntoView({ behavior: 'smooth' })
  },
)
</script>

<template>
  <div class="chat-window">
    <div class="messages" role="log" aria-live="polite" aria-label="Histórico de conversa">

      <!-- Welcome state -->
      <div v-if="!chat.messages.length" class="welcome">
        <div class="welcome__icon" aria-hidden="true">F</div>
        <h2 class="welcome__title">Olá! Sou o FCTEBot</h2>
        <p class="welcome__desc">
          Assistente virtual da Engenharia de Software da UnB.<br />
          Posso responder dúvidas sobre calendário, matrícula, trancamento,
          estágio, TCC, normativos e muito mais.
        </p>
      </div>

      <!-- Mensagens -->
      <ChatMessage
        v-for="msg in chat.messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- Typing indicator -->
      <div v-if="chat.isLoading" class="typing-indicator">
        <div class="typing-indicator__avatar" aria-hidden="true">F</div>
        <div class="typing-indicator__bubble">
          <span /><span /><span />
        </div>
        <span class="typing-indicator__label">Consultando base de conhecimento…</span>
      </div>

      <div id="messages-end" aria-hidden="true" />
    </div>

    <ChatInput />
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--color-bg);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}

/* Welcome */
.welcome {
  text-align: center;
  max-width: 440px;
  margin: auto;
  padding: 24px;
}
.welcome__icon {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: var(--color-navy);
  color: #fff;
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}
.welcome__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-navy);
  margin-bottom: 8px;
}
.welcome__desc {
  font-size: 13.5px;
  color: var(--color-text-secondary);
  line-height: 1.65;
}

/* Typing */
.typing-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  align-self: flex-start;
}
.typing-indicator__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-navy);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.typing-indicator__bubble {
  display: flex;
  align-items: center;
  gap: 5px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-left: 3px solid var(--color-primary);
  border-radius: 10px;
  border-bottom-left-radius: 3px;
  padding: 10px 14px;
}
.typing-indicator__bubble span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: bounce 1.2s infinite;
}
.typing-indicator__bubble span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator__bubble span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-5px); opacity: 1; }
}
.typing-indicator__label {
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
