import type { ReactNode } from 'react'

import { BackendReadinessContext } from './BackendReadinessContext'
import { useBackendReadiness } from './useBackendReadiness'

export function BackendReadinessProvider({ children }: { children: ReactNode }) {
  const readiness = useBackendReadiness()
  return (
    <BackendReadinessContext.Provider value={readiness}>{children}</BackendReadinessContext.Provider>
  )
}
