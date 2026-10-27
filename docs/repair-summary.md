# Repair coverage

This maps the 14 findings from the 28 October 2026 review to the repair branch.
Code and configuration are repaired; an existing expired/deleted cloud database
cannot be recovered without access to its hosting account and any available backup.

| # | Finding | Repair |
| --- | --- | --- |
| 1 | Vercel serves HTML for API calls | Frontend honors `VITE_API_URL`; validates JSON; Vercel builds reject missing/invalid/insecure backend URLs. |
| 2 | CORS excludes the actual domain | Blueprint uses the `-gamma` domain; configured `FRONTEND_URL` is always included in allowed origins. |
| 3 | Free database expires | Blueprint uses persistent paid PostgreSQL. Liveness survives DB outages; readiness retries schema initialization. Recovery of the existing cloud database remains an operator action. |
| 4 | Celery syntax error | Replaced broken task module with importable task entrypoints and bounded job execution. CI compiles all app modules. |
| 5 | All accounts can invoke admin workloads | Explicit trusted UUID allowlist; non-admins receive 403. Work is queued with 202, not run in HTTP requests. Unverified email addresses cannot grant privileges. |
| 6 | Missing task infrastructure and browser | Blueprint provisions Redis, worker and single beat scheduler; image installs Chromium and runtime libraries; duplicate scheduling removed from Actions. |
| 7 | Scraper DB errors poison later records | Per-record savepoints, conflict-safe company insertion and source rollback; enrichment gets the same transaction protection. |
| 8 | Broken digest schedules and false success logs | Minute polling with a catch-up window, cadence/timezone/filter handling, row locks and success-only `last_sent_at`. Failed attempts show as failed. |
| 9 | Unsubscribe does nothing | Purpose-bound signed tokens, public confirmation page and idempotent persisted opt-out. Link-preview GETs do not mutate settings. |
| 10 | Stale cache and fake pagination | Cache includes profile/content/model/limit; every matching record is scored; real pagination removes the 200-row truncation; limits apply to fallback results too. |
| 11 | Outages look like empty results and log users out | Visible retry/error states; only 401 clears credentials; temporary errors preserve sessions. |
| 12 | Compose backend build points to a missing file | Correct root contexts; frontend lockfile copied before `npm ci`; container URLs and development proxy configured. |
| 13 | OpenAI/httpx constructor crash | Tested direct dependency pins, explicit compatible HTTP clients and lazy optional SDK initialization with keyword fallback. |
| 14 | Long passwords cause server errors | UTF-8 byte-length validation returns 422; existing bcrypt hashes remain supported. |

## Local validation

- 51 backend tests passed against an isolated PostgreSQL 16 database.
- 11 frontend tests passed, covering request parsing, routing, session recovery,
  outage states and unsubscribe confirmation.
- Production frontend build passed with a configured HTTPS backend URL, which was
  verified in the generated bundle. Missing, insecure and invalid values were rejected.
- Python compilation, `pip check`, Render's official JSON Schema validation and
  Compose context/URL validation passed.
- No real AI request, email, production scrape or production data mutation was used
  in these checks. Redis lock tests use a protocol-compatible in-memory test server.
- The local Python runtime is Windows/Python 3.11. CI additionally targets Linux/
  Python 3.12 and builds both containers, including a Chromium launch check.
  Local Docker image execution was unavailable; check CI before merging.

## Deployment changes to review

`render.yaml` now describes paid API/worker/beat/Redis/Postgres resources. Review
the proposed resources and costs before merging or syncing a connected Blueprint.
The worker is sized for browser scraping. No paid resources were created during repair.

The actual backend URL, existing database health, hosting credentials, SendGrid
sender and trusted admin account UUID still need to be supplied by the deployment
owner. See [deployment and recovery](deployment.md) for exact steps.
