# ZerroBuild — Foundation Release 0.1

Industrial construction platform foundation built with React/TypeScript, Tailwind, a shadcn-style Button component, FastAPI, SQLAlchemy, Alembic and PostgreSQL.

**This package implements login, access administration and project setup. It is not the completed 21-module product.** The nine remaining domain packages are intentionally empty boundaries. See `docs/implementation_status.md`.

## What works

- Cookie-session login/logout, expiry, account deactivation and CSRF protection.
- Organization isolation and administrator-only user/company management.
- Project roles, participating companies, ALL/SELECTED discipline scopes.
- Project creation, search, filters, pagination and version-protected editing.
- Draft/activation validation, schedule/location fields and automatic lead-PM membership.
- Unit → Area → Block creation, assignment deactivation and audit history.
- Responsive React screens with no fabricated project statistics.

## Start on a laptop with Docker Desktop

Docker Desktop must be running with Linux containers and Docker Compose v2. Git is optional. You do not need local Python, Node or PostgreSQL for this route.

1. Extract this ZIP and open the `siteforge` folder in Cursor.
2. Copy `.env.example` to `.env`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

3. Set `POSTGRES_PASSWORD` to a long random local password. Use URL-safe letters/digits for this Compose example, because the password is interpolated into the database URL. Never commit `.env`.
4. Start the application:

```bash
docker compose up --build -d
```

The one-shot `migrate` service applies Alembic migrations before the backend starts. Wait for health checks:

```bash
docker compose ps -a
docker compose logs backend migrate
```

5. Create your first organization and administrator:

```bash
docker compose exec backend python -m app.bootstrap --organization "Your Company" --email "admin@yourcompany.com" --name "Project Administrator"
```

Enter a password of 12–128 characters at the hidden prompts. There are no default application credentials.

6. Open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health
- PostgreSQL host connection: localhost:55432, database/user `siteforge`, password from `.env`.

Internal PostgreSQL connections use `db:5432`, independent of the host port.

Ports bind to localhost. This is a local development configuration, not an internet deployment.

## First-use sequence

1. Sign in as your administrator.
2. Add owner/client, contractor and subcontractor companies.
3. Add users with their employing company.
4. Create a Draft project.
5. Enter client, site, dates, enabled disciplines and lead PM.
6. Add project participants, then role/discipline assignments.
7. Add Units, Areas and Blocks.
8. Change to Planned when setup is complete; Active also requires actual start.

The lead PM is granted a Project Manager assignment. Replacing the lead retains the former PM membership until the administrator explicitly reviews/deactivates it.

## Ports and troubleshooting

If a port is busy, change `WEB_HOST_PORT`, `API_HOST_PORT` or `DB_HOST_PORT` in `.env`.

If the frontend port changes, also change `ALLOWED_ORIGINS`, for example `http://localhost:5180`. Open the configured localhost address; `127.0.0.1` is a different browser origin unless added explicitly.

After settings change:

```bash
docker compose up --build -d
```

Stop without deleting data:

```bash
docker compose down
```

Database data is retained in the named volume. Do not use `down -v` unless intentionally deleting that data.

If initialization settings change after a database volume already exists, PostgreSQL does not automatically change existing user passwords. Update the database credentials through an authorized database process and keep `.env` consistent.

Internet is needed for the first Docker image/dependency download. The UI uses system-font fallbacks and does not require externally hosted fonts.

## Tests in Docker

```bash
docker compose exec backend pytest -q
docker compose run --rm migrate alembic check
```

Tests use an isolated in-memory SQLite database and never use project data. PostgreSQL-specific concurrency behavior still requires PostgreSQL integration testing.

## Development without Docker

Install Python 3.12+, Node 22+ and PostgreSQL.

Backend, from `backend/`:

```bash
python -m venv .venv
```

Activate with `.venv\Scripts\Activate.ps1` on PowerShell or `source .venv/bin/activate` on Linux/macOS.

```bash
pip install -r requirements.txt
```

Create `backend/.env` with a URL-encoded PostgreSQL connection string:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/siteforge
ALLOWED_ORIGINS=http://localhost:5173
COOKIE_SECURE=false
SESSION_HOURS=12
```

```bash
alembic upgrade head
python -m app.bootstrap --organization "Your Company" --email "admin@yourcompany.com" --name "Administrator"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in another terminal from `frontend/`:

```bash
npm ci
npm run dev
```

The Vite proxy passes browser `/api` requests to localhost:8000. If the backend port changes, update `vite.config.ts`.

Checks:

```bash
# backend/
pytest -q
# frontend/
npm run typecheck
npm run build
```

## Important scope and deployment limits

- Password reset, invitations, MFA, SSO, attachments and advanced workflow engine are not implemented.
- Login rate limiting is single-process/in-memory for local use; production requires a shared limiter.
- Use HTTPS and `COOKIE_SECURE=true` in production with correctly configured trusted origins and proxy headers.
- No automatic technical, commercial or safety approval privileges are granted by organization-admin status.
- Discipline checks are ready for domain endpoints; current project overview access is project-level.
- Business services have not been built. Never use this release to authorize live construction or safety-critical work.
- Full Docker/PostgreSQL runtime validation and browser checks are recorded honestly in `docs/validation.md`.

## Next Cursor task

Read `docs/next_cursor_prompt.md`. Complete remaining Project Details and shared services before implementing domain workflows.
