import { Link } from 'react-router'

interface Scenario {
  title: string
  service: string
  description: string
}

const SCENARIOS: Scenario[] = [
  {
    title: 'CPU Spike After Deployment',
    service: 'checkout-api',
    description: '新版本部署後 CPU 飆升、5xx 增加，Agent 追查 retry regression 並規劃 rollback。',
  },
  {
    title: 'Database Pool Exhaustion',
    service: 'student-portal-api',
    description: 'HTTP 500 增加且 log 顯示連線池耗盡，Agent 規劃 restart 緩解與調整 pool 的改善項目。',
  },
  {
    title: 'Duplicate Alert Storm',
    service: 'notification-worker',
    description: '重複建立 incident，Agent 找出 cooldown race condition 並建立修正 distributed lock 的 ticket。',
  },
]

export function LandingPage() {
  return (
    <div className="space-y-12">
      <section className="space-y-4">
        <p className="font-mono text-xs uppercase tracking-widest text-cyan-400">
          Incident response, orchestrated
        </p>
        <h1 className="text-3xl font-bold leading-tight text-white sm:text-5xl">
          AgentOps Commander — AI Multi-Agent Incident Response Platform
        </h1>
        <p className="max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
          系統事故處理通常需要人工在告警、監控、日誌、部署紀錄、Runbook
          與歷史事件間切換。AgentOps Commander
          將這些步驟編排成可追蹤、可中斷、可人工審批的多 Agent 工作流。
        </p>
        <Link
          to="/incidents"
          className="inline-block rounded border border-cyan-500/60 bg-cyan-500/10 px-5 py-2 text-sm font-medium text-cyan-100 hover:bg-cyan-500/20"
        >
          進入事故列表
        </Link>
      </section>

      <section aria-labelledby="scenarios-heading" className="space-y-4">
        <h2 id="scenarios-heading" className="text-xl font-semibold text-white">
          三個情境
        </h2>
        <ul className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {SCENARIOS.map((scenario) => (
            <li
              key={scenario.title}
              className="rounded-lg border border-slate-800 bg-slate-900/60 p-5 transition-colors hover:border-cyan-500/50"
            >
              <h3 className="text-base font-semibold text-white">{scenario.title}</h3>
              <p className="mt-1 break-all font-mono text-xs text-cyan-300">{scenario.service}</p>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">{scenario.description}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
