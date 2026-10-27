# Deploying and restoring OpportunityRadar

## Restore the existing service first

1. Locate the existing FastAPI service and database in the hosting account. The
   known public URL, `https://opportunityradar-gamma.vercel.app`, is the frontend.
   Do not assume the example `opportunityradar-api.onrender.com` belongs to this account.
2. Inspect the database status and the API's startup logs. Free Render Postgres
   expires after 30 days and is deleted after its subsequent recovery grace period.
   Recover an expired database if still available; otherwise restore a backup into
   persistent hosting. Creating a new empty database cannot recover deleted data.
3. Retain the current `SUPABASE_JWT_SECRET`, existing database and user data when
   updating a deployment. Back up any accessible database before changing plans or providers.
4. Deploy the repaired API, then verify `GET <actual-backend>/api/ready` returns JSON
   with HTTP 200, and unauthenticated `/api/auth/me` returns JSON with HTTP 401.

## Render Blueprint

`render.yaml` defines the API, one worker, one beat scheduler, persistent Redis and
PostgreSQL 16. It deliberately uses **paid** compute and database plans to avoid
database expiration and idle scheduling interruptions. Applying it can create or
upgrade billable resources. Review Render's current pricing and the proposed changes
before applying; no services or charges are created by editing this file.

The browser-capable worker uses a larger instance than the API. All services share
the database and Redis. The worker reads the same JWT secret and Gemini key as the
API. A shared configuration group supplies the frontend origin and digest timezone.
Redis uses `noeviction` and persistence because it carries queued jobs as well as caches.

Use the repository root as Docker build context; do not set Render's root directory
to `backend` when using the root Dockerfile. Initial deployment inputs:

| Setting | Value |
| --- | --- |
| `GEMINI_API_KEY` on API | Your key, or empty to use keyword matching |
| `ADMIN_USER_IDS` on API | JSON array of trusted account UUIDs; `[]` denies admin actions |
| `SENDGRID_API_KEY` on worker | Your SendGrid API key, or empty to disable email |
| `FROM_EMAIL` on worker | A verified SendGrid sender |
| `SUPABASE_JWT_SECRET` | Preserve the existing value when updating; generated for a new deployment |
| `DATABASE_URL`, `REDIS_URL` | Supplied from the declared data stores |

Render prompts for `sync: false` values on initial Blueprint creation only. When
updating an existing deployment, add new settings manually. After changing an API
secret referenced by another service, sync the Blueprint and redeploy dependent
services so they receive the updated value.

One beat instance owns the schedule. Distributed locks and per-user row locks
prevent overlapping executions. Email delivery and a database commit cannot form
one atomic transaction: a worker crash after the provider accepts an email but
before commit can still cause a retry. The normal overlap/retry path is covered by tests.

Private-only database/Redis networking is intentional. The manual GitHub Actions
scraper is a diagnostic alternative and needs an explicitly configured, reachable
external test/database URL; it is not the production scheduler. Do not re-enable
both periodic schedulers against the same production database.

## Vercel frontend

1. Use the same repository, set **Root Directory** to `frontend` and choose Vite.
2. Set **`VITE_API_URL` to the actual healthy FastAPI origin**, for example the URL
   displayed on your own Render service. Do not use a guessed hostname. A trailing
   `/api` is accepted but not required.
3. Deploy with `npm ci && npm run build` and output directory `dist`.
4. The shared backend configuration uses `FRONTEND_URL=https://opportunityradar-gamma.vercel.app`
   and `CORS_ORIGINS=["https://opportunityradar-gamma.vercel.app"]`. Update both if the
   frontend domain changes. The configured frontend origin is included in CORS automatically.
5. Rebuild after any `VITE_API_URL` change: Vite embeds it in the bundle. Vercel
   builds deliberately fail if this setting is missing, rather than shipping a broken `/api` target.

The API client rejects HTML and malformed JSON as service errors. Existing login
tokens survive temporary network/server failures; only an HTTP 401 clears the session.
Unsubscribe works without login at `/unsubscribe?token=...`.

## Validation after deployment

- Verify backend readiness and the frontend-origin CORS preflight.
- Register/login, save a profile, list and page matches, save/update an application.
- An ordinary account must receive 403 from admin endpoints; an explicitly approved
  admin receives 202, and the worker logs show completion.
- Confirm that worker and beat are running, Chromium launches, and scheduled jobs
  reach their queues. No Redis URL should point to localhost in Render.
- Send a test digest to an account you control, verify its success history and confirm
  that its unsubscribe link disables that account's digest preference.

## Rollback

Keep the previous deployment and a database backup available. This repair does not
change database columns or erase application data. Rolling back code alone will
restore the old routing, worker and authorization defects; prefer correcting an
environment value if that is the source of a deployment problem. Do not delete a
database to roll back a service.

Official references: [Render Blueprint specification](https://render.com/docs/blueprint-spec),
[Render free database policy](https://render.com/docs/free#30-day-limit).
