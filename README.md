# OpportunityRadar

Internship discovery and application tracking with a React frontend, a FastAPI API,
PostgreSQL, and optional Gemini/OpenAI/Anthropic ranking.

## Architecture

- Vercel serves the static React frontend from `frontend/`.
- A separate Docker service runs FastAPI. The frontend calls its public URL through `VITE_API_URL`.
- PostgreSQL stores accounts, profiles, listings, applications and digest preferences.
- Redis queues jobs; a Celery worker runs scrapers, enrichment, email and maintenance.
- One Celery beat process schedules jobs. GitHub Actions scraping is manual-only.

The default Render Blueprint follows the owner's temporary free recovery choice:
free API plus a fresh free database that expires after 30 days. A lightweight public
employer feed imports internships on startup and checks for updates when the catalog
is used, with a six-hour database-backed cooldown. It needs no additional credentials
or worker. Automatic background
jobs are not provisioned in that mode. The full paid topology is separately available
as `render.production.yaml` and requires explicit approval before use.

Vercel's SPA rewrite does not run the Python backend. See [deployment and recovery](docs/deployment.md)
for the complete production topology and restoring the existing deployment.

## Local development

```sh
cp backend/.env.example backend/.env
docker compose up --build
```

Open http://localhost:5173. Compose supplies container database/Redis URLs and the
Vite proxy target. Change the development JWT secret before exposing this stack.

To run Python and Vite on the host instead:

```sh
docker compose up -d db redis
cd backend
python -m venv venv
# Activate venv, then:
pip install -r requirements.txt
# Copy .env.example to .env; set DATABASE_URL to localhost:5432 and REDIS_URL to localhost:6379/0.
uvicorn app.main:app --reload
# In another terminal:
cd frontend
npm ci
npm run dev
```

## Tests

Use a separate disposable PostgreSQL 16 database named `opportunityradar_test`.
The suite truncates its tables and deliberately rejects database names that do not end in `_test`.
It never uses the application's `DATABASE_URL` or production AI/email credentials.

```sh
cd backend
pip install -r requirements-dev.txt
export TEST_DATABASE_URL='postgresql+asyncpg://postgres:test-password@localhost:5432/opportunityradar_test'
python -m pytest -q

cd ../frontend
npm ci
npm test
npm run build
```

On PowerShell, set the environment variable using `$env:TEST_DATABASE_URL = '...'`.
CI runs the tests on Python 3.12/PostgreSQL 16 and builds the frontend on Node 22.

## Administration and email

Administrative routes require an authenticated account whose UUID is explicitly
listed in `ADMIN_USER_IDS`. Default `[]` denies all administrative access. Do not
grant privileges based on unverified email addresses. Obtain the trusted account's
UUID from `/api/auth/me`, then set the JSON allowlist in the API environment.

`POST /api/admin/scrape` and `POST /api/admin/enrich` return HTTP 202 and a task ID.
Jobs are deduplicated and run in the worker, rather than inside the HTTP request.

Digests use `DIGEST_TIMEZONE` (UTC by default, displayed in the UI). Monthly means
the first selected weekday of the month; biweekly is anchored to the previous
successful delivery. Missed runs catch up within 24 hours. Set SendGrid credentials
and a verified sender in the worker environment. Failed sends remain eligible for
retry and appear as failed attempts in digest history.

Unsubscribe links are signed, expire after one year and open a public confirmation
page. Following a link alone does not change preferences; confirmation persists the opt-out.

## Health checks

- `GET /api/health`: process liveness, independent of database availability.
- `GET /api/ready`: bounded database/schema readiness; returns 503 during an outage
  and retries initialization when the database recovers. Render uses this endpoint.

Existing tables are created if absent; `create_all` is not a migration tool. Future
schema changes need explicit migrations. This repair does not change the existing schema.

## License

MIT
