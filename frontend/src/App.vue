<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import AppHeader from '@/components/AppHeader.vue'
import ChatSidebar from '@/components/ChatSidebar.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import AppFooter from '@/components/AppFooter.vue'

const chat = useChatStore()

onMounted(() => {
  chat.checkHealth()
  setInterval(() => chat.checkHealth(), 30_000)
})
</script>

<template>
  <div class="app-shell">
    <AppHeader />

    <div class="app-body">
      <ChatSidebar />
      <ChatWindow />
    </div>

    <AppFooter />
  </div>
</template>

<style>
@import '@/assets/design-system.css';

.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}
</style>
