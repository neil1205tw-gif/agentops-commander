/** 以本地時區顯示日期時間；無法解析時回傳破折號。 */
export function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '—'
  }
  return date.toLocaleString('zh-TW', { hour12: false })
}
