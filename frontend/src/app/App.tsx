import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RouterProvider } from 'react-router'

import { AuthProvider } from '../features/auth'
import { BackendReadinessProvider } from '../features/backend-status'

type AppRouter = Parameters<typeof RouterProvider>[0]['router']

export function App({ router }: { router: AppRouter }) {
  // 後端冷啟動由 BackendReadinessProvider 處理，查詢本身不自動重試，失敗時由頁面提供「重試」。
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <BackendReadinessProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </BackendReadinessProvider>
    </QueryClientProvider>
  )
}
