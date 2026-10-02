import { createContext, useContext } from 'react'

import type { BackendReadiness } from './useBackendReadiness'

export const BackendReadinessContext = createContext<BackendReadiness | null>(null)

/** 讀取共用的後端 readiness 狀態；其他元件以 `isReady` 決定是否啟用需要後端的操作。 */
export function useBackendStatus(): BackendReadiness {
  const value = useContext(BackendReadinessContext)
  if (value === null) {
    throw new Error('useBackendStatus must be used within BackendReadinessProvider')
  }
  return value
}
