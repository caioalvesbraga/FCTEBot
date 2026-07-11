import { defineStore } from 'pinia'
import { useStorage, useDark, useToggle } from '@vueuse/core'

export const useSettingsStore = defineStore('settings', () => {
  const isDark = useDark({ storageKey: 'fctebot-theme' })
  const toggleDark = useToggle(isDark)

  const sidebarOpen = useStorage('fctebot-sidebar', true)

  return { isDark, toggleDark, sidebarOpen }
})
