import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="space-y-4">
      <p className="font-mono text-sm text-cyan-400">404</p>
      <h1 className="text-2xl font-bold text-white sm:text-3xl">找不到這個頁面</h1>
      <p className="text-slate-300">你要找的網址不存在，或已被移動。</p>
      <Link
        to="/"
        className="inline-block rounded border border-cyan-500/50 px-4 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/10"
      >
        回首頁
      </Link>
    </div>
  )
}
