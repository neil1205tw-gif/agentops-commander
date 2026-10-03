import { afterEach, describe, expect, it, vi } from 'vitest'

import { clearToken, readToken, writeToken } from './tokenStore'

const KEY = 'agentops.access_token'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('tokenStore', () => {
  it('寫入後可讀回，清除後讀不到', () => {
    writeToken('abc')
    expect(readToken()).toBe('abc')
    expect(sessionStorage.getItem(KEY)).toBe('abc')

    clearToken()
    expect(readToken()).toBeNull()
    expect(sessionStorage.getItem(KEY)).toBeNull()
  })

  it('setItem 失敗但 getItem 正常：寫入後讀到新 token，而不是 storage 內的舊值', () => {
    sessionStorage.setItem(KEY, 'old-token')
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError')
    })

    writeToken('new-token')

    expect(readToken()).toBe('new-token')
  })

  it('setItem 失敗、storage 原本沒有值：寫入後仍讀到新 token', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError')
    })

    writeToken('new-token')

    expect(readToken()).toBe('new-token')
  })

  it('setItem 失敗後清除：記憶體與 storage 都讀不到任何舊值', () => {
    sessionStorage.setItem(KEY, 'old-token')
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError')
    })
    writeToken('new-token')

    clearToken()

    expect(readToken()).toBeNull()
    expect(sessionStorage.getItem(KEY)).toBeNull()

    // storage 恢復可寫後，新的寫入回到 storage，且清除後不殘留記憶體舊值。
    setItem.mockRestore()
    writeToken('later-token')
    expect(readToken()).toBe('later-token')
    expect(sessionStorage.getItem(KEY)).toBe('later-token')
    clearToken()
    expect(readToken()).toBeNull()
  })

  it('removeItem 也失敗：清除後不會讀回 storage 內殘留的舊值，成功寫入後恢復正常', () => {
    sessionStorage.setItem(KEY, 'old-token')
    const denied = () => {
      throw new DOMException('denied', 'SecurityError')
    }
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(denied)
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(denied)
    writeToken('new-token')

    clearToken()
    expect(readToken()).toBeNull()

    setItem.mockRestore()
    removeItem.mockRestore()
    writeToken('later-token')
    expect(readToken()).toBe('later-token')
  })

  it('成功寫入 storage 後不殘留先前的記憶體值', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError')
    })
    writeToken('memory-token')
    setItem.mockRestore()

    writeToken('stored-token')
    expect(readToken()).toBe('stored-token')

    sessionStorage.removeItem(KEY)
    expect(readToken()).toBeNull()
  })
})
