# Zerro-R-vision-360

A full-stack executive project-completion dashboard for industrial projects. CMD users can view every project and discipline. Discipline heads are restricted to Mechanical, Electrical, or Civil information assigned to them.

## Included

- Project portfolio and project selection
- CMD, Project Director, Project Manager, Discipline Head and Viewer roles
- Mechanical, Electrical and Civil drill-downs
- Sub-project/work-package tracking
- Contractor name and contact details
- Planned and actual completion
- Approved budget, committed cost and actual cost
- Start dates and target dates
- Milestones, risks and mitigation actions
- Responsive executive UI
- FastAPI Swagger documentation
- SQLite for zero-setup local development
- PostgreSQL and Supabase-ready configuration
- Docker Compose setup

## Project structure

```text
zerro-project-command-center/
├── backend/
│   ├── app/
│   │   ├── routers/projects.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── seed.py
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── types.ts
│   ├── .env.example
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
└── docker-compose.yml
```

## Quick start with Docker

Install Docker Desktop, open a terminal in this folder, and run:

```bash
docker compose up --build
```

Open:

- Dashboard: http://localhost:8080
- FastAPI documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Run without Docker

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

The first startup creates the SQLite database and demo data automatically.

### Frontend

Open a second terminal:

```bash
cd frontend
npm install
```

Windows PowerShell:

```powershell
copy .env.example .env
npm run dev
```

macOS/Linux:

```bash
cp .env.example .env
npm run dev
```

Open http://localhost:5173.

## Access control

The demo uses two headers so access rules can be tested without an identity provider:

- `X-User-Role`: `CMD`, `PROJECT_DIRECTOR`, `PROJECT_MANAGER`, `DISCIPLINE_HEAD`, or `VIEWER`
- `X-Discipline`: required for a discipline head; `MECHANICAL`, `ELECTRICAL`, or `CIVIL`

The role selector in the UI sends these headers automatically. Before production, replace the demo header identity with verified Supabase JWT claims. Keep the backend authorization checks; hiding tabs in the frontend is not sufficient security.

## Progress calculation

Project progress is weighted, not a simple average:

```text
Project completion = Σ(discipline weight × discipline completion) / Σ(discipline weight)
```

Use the same formula for work packages inside each discipline. Discipline weights in each project and work-package weights in each discipline should total 100.

## PostgreSQL or Supabase

Copy `backend/.env.example` to `backend/.env` and change `DATABASE_URL`:

```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres
```

For Supabase, use the database connection string supplied in the Supabase dashboard. Do not expose the database password or service-role key in the Vite frontend.

## Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/projects` | List projects visible to the current role |
| GET | `/api/projects/{id}/dashboard` | Executive summary with permitted disciplines |
| GET | `/api/projects/{id}/disciplines/{code}` | Discipline details and work packages |
| PATCH | `/api/work-packages/{id}/progress` | Update completion, cost and status |
| GET | `/health` | Service health check |

## Recommended production additions

1. Replace demo headers with Supabase Auth/JWT verification.
2. Add user-to-project and user-to-discipline assignment tables.
3. Add an audit log for every progress and budget change.
4. Store daily or weekly progress snapshots for the S-curve.
5. Add approval workflow before progress updates affect CMD reporting.
6. Add contractor login restrictions if contractors enter their own progress.

