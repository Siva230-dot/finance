# Security & Privacy

| Control | Implementation |
|---|---|
| Password hashing | Argon2id (`argon2-cffi` defaults); policy ≥ 8 chars with letters and digits |
| Authentication | HS256 JWT, `exp` (30 min default), `type=access`, `tv` token version checked on every request; logout and password change revoke tokens |
| Authorization / isolation | Every query filters by the authenticated `user_id`; foreign records return 404; custom categories are owner-only. Tested in `test_isolation.py` and agent tests |
| AI boundaries | No SQL from the LLM, no `user_id` tool arguments, per-agent tool allowlists, mandatory confirmation for mutations, iteration limits, audit trail |
| Input validation | Pydantic schemas (amount > 0, 2 decimals, enums, lengths), Zod on the client |
| Uploads | Extension allowlist, declared MIME check, magic-byte sniffing (`filetype`), size limit (`MAX_UPLOAD_SIZE_MB`), encrypted/scanned PDF detection, private temp file deleted in `finally`, original never stored |
| CORS | Explicit origin allowlist (`CORS_ORIGINS` + `FRONTEND_URL`), no credentials mode, limited methods/headers |
| Rate limiting | slowapi: default `RATE_LIMIT_DEFAULT`; login/register 10/min; uploads 10/min; assistant 20/min |
| Errors | Uniform envelope, no stack traces or SQL in responses; DB outages → 503 |
| Logging | Event names and exception types only — no request bodies, amounts or descriptions |
| Headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on API; HSTS in production (API and Vercel) |
| Secrets | Only in env vars (`.env` git-ignored; `.env.example` has placeholders). Groq key and JWT secret are server-side only; `VITE_*` contains only the public API URL |
| Production | `APP_ENV=production` disables OpenAPI docs and refuses to start without a ≥32-char `JWT_SECRET_KEY` |
| Token storage | `sessionStorage` (cleared when the tab closes) |
| Privacy controls | JSON export of all data; password-confirmed hard account deletion (cascade) |

Never collected: banking passwords, OTPs, full card numbers, payment credentials. The app moves no money.
Demo data is synthetic (`seed_demo.py`); never put real bank data in a public demo account.
