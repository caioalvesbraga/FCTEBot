<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const chat = useChatStore()
const settings = useSettingsStore()
</script>

<template>
  <div class="govbar">
    <span>gov.br</span>
    <span class="sep">·</span>
    <a href="https://www.unb.br" target="_blank" rel="noopener">Universidade de Brasília</a>
    <span class="sep">·</span>
    <a href="https://software.unb.br" target="_blank" rel="noopener">Engenharia de Software</a>
  </div>

  <header class="site-header">
    <button class="sidebar-toggle" @click="settings.sidebarOpen = !settings.sidebarOpen" :aria-label="settings.sidebarOpen ? 'Fechar menu' : 'Abrir menu'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>

    <div class="logo-block">
      <span class="logo-institution">UnB · FCTE</span>
      <span class="logo-course">Engenharia de Software</span>
    </div>

    <div class="header-divider" aria-hidden="true" />

    <div class="bot-brand">
      <span class="bot-name">FCTEBot</span>
      <span class="bot-desc">Assistente Virtual Acadêmico</span>
    </div>

    <div class="header-actions">
      <div class="api-status" :class="chat.apiStatus" :title="`API: ${chat.apiStatus}`">
        <span class="status-dot" />
        <span class="status-label">{{ chat.apiStatus === 'online' ? 'Online' : chat.apiStatus === 'offline' ? 'Offline' : '…' }}</span>
      </div>

      <button class="icon-btn" @click="settings.toggleDark()" :aria-label="settings.isDark ? 'Modo claro' : 'Modo escuro'">
        <svg v-if="settings.isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.govbar {
  background: var(--color-govbar);
  color: var(--color-govbar-text);
  font-size: 11px;
  padding: 5px 20px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.govbar a { color: var(--color-govbar-link); text-decoration: none; }
.govbar a:hover { color: #fff; }
.sep { opacity: 0.4; }

.site-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.sidebar-toggle {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-secondary);
  padding: 4px;
  border-radius: 6px;
}
.sidebar-toggle svg { width: 20px; height: 20px; }
.sidebar-toggle:hover { background: var(--color-surface-alt); color: var(--color-primary); }

@media (max-width: 768px) {
  .sidebar-toggle { display: flex; }
}

.logo-block { display: flex; flex-direction: column; gap: 1px; }
.logo-institution { font-size: 10px; font-weight: 600; color: var(--color-text-secondary); text-transform: uppercase; letter-spacing: 0.8px; }
.logo-course { font-size: 17px; font-weight: 700; color: var(--color-primary); }

.header-divider { width: 1px; height: 36px; background: var(--color-border); flex-shrink: 0; }

.bot-brand { display: flex; flex-direction: column; gap: 1px; }
.bot-name { font-size: 14px; font-weight: 600; color: var(--color-navy); }
.bot-desc { font-size: 11px; color: var(--color-text-secondary); }

.header-actions { margin-left: auto; display: flex; align-items: center; gap: 12px; }

.api-status { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--color-text-secondary); }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-border); transition: background 0.3s; }
.api-status.online .status-dot { background: #22c55e; }
.api-status.offline .status-dot { background: #ef4444; }

.icon-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 6px;
  cursor: pointer;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  transition: background 0.15s, color 0.15s;
}
.icon-btn svg { width: 16px; height: 16px; }
.icon-btn:hover { background: var(--color-surface-alt); color: var(--color-primary); }
</style>
