import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

import { clearToken } from '../lib/tokenStore'

// 測試之間不共用全域狀態：每個測試前後都重設 sessionStorage 與記憶體備援 token。
beforeEach(() => {
  sessionStorage.clear()
  clearToken()
})

afterEach(() => {
  cleanup()
  sessionStorage.clear()
  clearToken()
})
