import { ref } from 'vue'
import type { ApiHealthResponse, ApiQueryRequest, ApiQueryResponse } from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    signal,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    const body = await response.text().catch(() => '')
    throw new Error(`HTTP ${response.status}: ${body || response.statusText}`)
  }

  return response.json() as Promise<T>
}

export function useApi() {
  const abortController = ref<AbortController | null>(null)

  function cancelPending() {
    abortController.value?.abort()
    abortController.value = null
  }

  async function query(payload: ApiQueryRequest): Promise<ApiQueryResponse> {
    cancelPending()
    abortController.value = new AbortController()

    return request<ApiQueryResponse>(
      '/query',
      { method: 'POST', body: JSON.stringify(payload) },
      abortController.value.signal,
    )
  }

  async function health(): Promise<ApiHealthResponse> {
    return request<ApiHealthResponse>('/health', { method: 'GET' })
  }

  return { query, health, cancelPending }
}
