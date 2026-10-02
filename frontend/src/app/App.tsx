import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RouterProvider } from 'react-router'

import { BackendReadinessProvider } from '../features/backend-status'

type AppRouter = Parameters<typeof RouterProvider>[0]['router']

export function App({ router }: { router: AppRouter }) {
  const [queryClient] = useState(() => new QueryClient())

  return (
    <QueryClientProvider client={queryClient}>
      <BackendReadinessProvider>
        <RouterProvider router={router} />
      </BackendReadinessProvider>
    </QueryClientProvider>
  )
}
