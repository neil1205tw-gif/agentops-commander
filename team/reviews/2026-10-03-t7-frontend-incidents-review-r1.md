The authentication implementation can unexpectedly invalidate a newly established session and its session-storage fallback fails under partial storage failures.

Full review comments:

- [P2] Preserve the current token when handling stale 401 responses — C:\side_workspace\AgentOps-Commander\frontend\src\lib\api.ts:74-76
  When a request made with an old token completes with 401 after the user has logged out and logged back in, this unconditionally clears the newly issued token and redirects the user back to login. Compare the token used for the request with the currently stored token before clearing/notifying, so late responses from pre-logout requests cannot invalidate a new session.

- [P2] Read the in-memory token after storage write failures — C:\side_workspace\AgentOps-Commander\frontend\src\lib\tokenStore.ts:6-10
  If `sessionStorage.getItem` succeeds but `setItem` fails (for example, quota exhaustion), `writeToken` stores the login token in `memoryToken`, but this function still returns the old storage value or `null`. The subsequent `/me` request therefore has no new Bearer token and login fails despite the intended fallback; return `memoryToken` when it is set before consulting storage.