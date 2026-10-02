import { useCallback, useSyncExternalStore } from 'react'

/** 每秒更新，回傳距離 `target`（epoch ms）還剩幾秒；`target` 為 null 時回傳 null。 */
export function useSecondsUntil(target: number | null): number | null {
  const subscribe = useCallback((onChange: () => void) => {
    const timer = setInterval(onChange, 1_000)
    return () => {
      clearInterval(timer)
    }
  }, [])

  const getSnapshot = () => (target === null ? null : Math.max(0, Math.ceil((target - Date.now()) / 1_000)))

  return useSyncExternalStore(subscribe, getSnapshot)
}
