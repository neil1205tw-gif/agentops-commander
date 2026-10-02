import { describe, expect, it } from 'vitest'

import { normalizeBaseUrl } from './config'

describe('normalizeBaseUrl', () => {
  it('未設定時使用預設值', () => {
    expect(normalizeBaseUrl(undefined)).toBe('http://localhost:8000')
    expect(normalizeBaseUrl('  ')).toBe('http://localhost:8000')
  })

  it('去除結尾斜線', () => {
    expect(normalizeBaseUrl('https://api.example.com/')).toBe('https://api.example.com')
    expect(normalizeBaseUrl('https://api.example.com///')).toBe('https://api.example.com')
  })

  it('保留沒有結尾斜線的網址', () => {
    expect(normalizeBaseUrl('https://api.example.com')).toBe('https://api.example.com')
  })
})
