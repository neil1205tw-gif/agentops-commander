The redaction processor leaks API keys supplied through the standard hyphenated HTTP header name when such headers are logged.

Review comment:

- [P1] Redact hyphenated API-key headers — C:\side_workspace\AgentOps-Commander\backend\app\logging.py:32-34
  When a logged request-header mapping contains the standard `X-API-Key` header, its normalized key is `x-api-key`, which matches neither the exact sensitive-key set nor the underscore suffixes. The API key is therefore emitted verbatim despite the logging redaction requirement; normalize hyphens or explicitly treat this header form as sensitive.