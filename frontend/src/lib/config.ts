const DEFAULT_API_BASE_URL = 'http://localhost:8000'

export function normalizeBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim()
  if (!trimmed) {
    return DEFAULT_API_BASE_URL
  }
  return trimmed.replace(/\/+$/, '')
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL)
