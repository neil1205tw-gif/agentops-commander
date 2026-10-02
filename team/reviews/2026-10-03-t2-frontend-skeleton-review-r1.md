The readiness-success UI contradicts an explicit acceptance requirement: the banner remains visible instead of being hidden.

Review comment:

- [P2] Hide the banner once readiness succeeds — C:\side_workspace\AgentOps-Commander\frontend\src\features\backend-status\BackendStatusBanner.tsx:40-48
  When `/health/ready` returns ready, this branch still renders a persistent green status bar. The task spec explicitly requires the entire status banner to be hidden in the `ready` state, so every successfully connected deployment retains UI that should disappear; return `null` for this case and update the test accordingly.