import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from './AuthContext'

/** 未登入導向 /login 並保留原目標，登入後回跳。 */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <p role="status" className="text-sm text-slate-300">
        正在確認登入狀態…
      </p>
    )
  }
  if (status === 'anonymous') {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  }
  return <Outlet />
}
