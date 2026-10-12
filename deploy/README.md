# MarketLens deployment and D-drive layout

## Where everything lives

| Item | Location |
| --- | --- |
| Python packages, including SQLAlchemy/Alembic/Psycopg | `D:\marketlens\backend\.venv\Lib\site-packages` |
| Python package download cache | `D:\marketlens\downloads\pip-cache` |
| Frontend packages | `D:\marketlens\frontend\node_modules` |
| npm download cache | `D:\marketlens\frontend\.npm-cache` |
| Temporary files and logs | `D:\marketlens\work` |
| Optional local SQLite development database | `D:\marketlens\data\marketlens-dev.db` |
| Dockerfiles, Compose, Nginx and helper scripts | `D:\marketlens\deploy` |
| Proposed Docker Desktop application location | `D:\marketlens\tools\Docker` |
| Proposed Docker WSL disk location | `D:\marketlens\data\docker-wsl` |
| Proposed Docker installer download location | `D:\marketlens\downloads\Docker Desktop Installer.exe` |

The Docker locations are a **plan**, not an installed runtime. Docker was not found
on PATH or in the checked standard application locations. No Docker image has been
pulled and no PostgreSQL server has been started in this phase. Windows integration
components and some Docker settings can still live on C:; installing its application
and virtual disk on D: does not relocate every Windows-managed file.

## Docker Desktop setup (pending approval/system setup)

Use the official [Docker Desktop Windows installer documentation](https://docs.docker.com/desktop/setup/install/windows-install/).
Download the all-users installer to the path above. Review the installer and license
yourself; do not use a third-party download or silently accept the license. The
documented location flags for a D-drive installation are:

```powershell
# Run only after approving the system-level Docker installation.
# The installer may require elevation and WSL setup or a restart.
Start-Process 'D:\marketlens\downloads\Docker Desktop Installer.exe' -Wait -ArgumentList @(
  'install',
  '--installation-dir=D:\marketlens\tools\Docker',
  '--backend=wsl-2',
  '--wsl-default-data-root=D:\marketlens\data\docker-wsl'
)
```

Check `wsl --version` and the current Docker system requirements. Do not change an
existing Docker installation or move an existing disk without a separate backup
and migration plan. After installation, open Docker Desktop, confirm the WSL disk
location is on D:, and run `docker version` and `docker compose version`. Do this
**before** pulling images: named volumes, image layers and build caches live inside
Docker's managed disk, not beside `compose.yaml`.

## Start PostgreSQL and the application

Run in PowerShell after Docker Desktop is available and its disk location verified:

```powershell
Set-Location D:\marketlens
.\deploy\setup-env.ps1
docker compose --env-file deploy/.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
```

Open `http://127.0.0.1:8080`. `setup-env.ps1` generates a 256-bit random hex database
password without printing it and preserves an existing `.env`. Hex avoids URL
encoding ambiguities in the connection URI. Do not paste `docker compose config`
output into logs: its expanded configuration can contain secrets; use `--quiet`.

Compose starts PostgreSQL 18, waits for its health check, runs `alembic upgrade head`
once in a migration service, starts FastAPI, and then starts the frontend after
database readiness succeeds. PostgreSQL and FastAPI are only reachable inside the
Compose network; the web port is bound to **127.0.0.1**. The backend and Nginx runtime
use non-root users. Nginx serves the SPA and proxies `/api`, `/health` and `/ready`.
The PostgreSQL volume mounts `/var/lib/postgresql`, as required by the official
[PostgreSQL 18 image layout](https://hub.docker.com/_/postgres).

This is a local, single-user research deployment. There is no login, ownership
isolation or authorization. Do not expose it publicly without adding these controls,
TLS, request/concurrency limits and operational monitoring. CORS is not authentication.

`/health` checks the API process; `/ready` checks the configured database, expected
migration revision and portfolio table. A missing database still permits analytics
but returns 503 for storage and readiness. Schema creation is never performed
automatically on ordinary API startup; only explicit Alembic commands migrate it.

## Local development without Docker

SQLite is an **explicit development alternative**, not a PostgreSQL compatibility
claim. It uses the same migrations and CRUD models. For an immediate saved-portfolio
demo while Docker is pending:

```powershell
Set-Location D:\marketlens
.\deploy\start-local.ps1 -ApiPort 8001 -WebPort 5174
```

Stop your old manually started MarketLens servers first if those ports are occupied,
or choose different ports. The script refuses to stop other processes, runs
migrations, and starts hidden background servers. It prints the process IDs and
log locations. It does not claim readiness just because a process starts: check
`http://127.0.0.1:8001/ready` and the frontend connection badge. Database and logs
remain on D:. Stop these processes by their printed IDs when finished.

For manual startup, set the URL in **both** the migration and backend environment:

```powershell
$env:MARKETLENS_DATABASE_URL = 'sqlite:///D:/marketlens/data/marketlens-dev.db'
New-Item -ItemType Directory -Force D:\marketlens\data | Out-Null
.\backend\.venv\Scripts\python.exe -m alembic upgrade head
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8001
```

SQLite data is not automatically transferred into PostgreSQL. Saved portfolio JSON
can be retrieved through the API and recreated against the new database. Keep the
original data file until any transfer is verified.

## Saved-portfolio API and UI

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/v1/saved-portfolios?limit=50&offset=0` | Paginated summaries; no price/return matrices |
| POST | `/api/v1/saved-portfolios` | Save `name`, `notes`, `definition`; returns 201 and Location |
| GET | `/api/v1/saved-portfolios/{uuid}` | Load the definition and version |
| PUT | `/api/v1/saved-portfolios/{uuid}` | Replace content using the current `version` |
| DELETE | `/api/v1/saved-portfolios/{uuid}?version=1` | Delete only the specified current version |

`definition` follows the existing portfolio analysis contract: assets, chronological
dates, aligned decimal returns, weights, periods per year and risk-free rate.
Names are trimmed; weights must match assets and sum to one. Definitions are bounded
to 100000 return cells, 50 assets and 10000 rows. PostgreSQL stores definitions in
JSONB; SQLite uses JSON. Generated IDs are UUIDs; timestamps are UTC. Saved entries
are research inputs, not frozen model results, so loading does not auto-run analysis.

In **Portfolios**, use **Save as new**, click an entry to load it, or choose
**Update selected**. Update keeps the same ID; Save as new creates a copy. Deletion
requires a second explicit confirmation in the UI. Optimizer results can be applied
with **Use optimized weights in analysis** before saving. Saved data persists across
server restarts. Updates and deletes reject stale versions with 409; reload before
retrying. SQLAlchemy's version counter also protects against a race after the initial
version check; changes are committed atomically, and failed sessions roll back.

The service is single-user; duplicate portfolio names are allowed. New saves create
new IDs, so retrying an ambiguous interrupted create may create a duplicate. Recheck
the saved list before retrying. No hardcoded credentials or browser-local token are
introduced. Database URLs are secret settings and are not included in error responses.

## Tests and dependency reproducibility

```powershell
Set-Location D:\marketlens
$env:TEMP = 'D:\marketlens\work\temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'D:\marketlens\downloads\pip-cache'
$env:npm_config_cache = 'D:\marketlens\frontend\.npm-cache'
.\backend\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

`backend/requirements-lock.txt` is a snapshot of installed version constraints,
including existing tools; only packages required by `requirements.txt` are installed
into the backend image. Install using `pip install -r backend/requirements.txt -c
backend/requirements-lock.txt`. This snapshot was verified on Windows/Python 3.14;
Linux image resolution remains unverified until a Docker build runs. Base image tags
are not immutable digests. Frontend dependencies use `npm ci` and the tracked lockfile.

For PostgreSQL verification, provision a **dedicated test database**, set
`MARKETLENS_TEST_POSTGRES_URL=postgresql+psycopg://...`, then run
`pytest backend/tests/test_persistence.py`. The PostgreSQL smoke test applies
migrations and creates/updates/removes its own portfolio; it does not drop tables.
SQLite migration downgrade tests use only isolated temporary fixtures.

Current verification: 119 backend tests passed, one PostgreSQL test skipped because
no server is available; 21 frontend tests and the production build passed. SQLite
CRUD, persistence across app instances, actual ORM write conflicts, migrations and
schema drift were checked. Docker Compose and PostgreSQL runtime execution are
**pending**, not verified by the SQLite suite.

## Stop, backup and upgrades

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yaml down
```

This preserves the named database volume. **Do not add `-v`** unless intentionally
deleting all saved portfolios after approval. Before a schema or PostgreSQL major
upgrade, make a backup and verify a restore in a separate database. Do not replace
PostgreSQL's major image tag and expect an existing volume to upgrade itself.

A local SQL backup without binary/text-redirection pitfalls in PowerShell:

```powershell
New-Item -ItemType Directory -Force D:\marketlens\data\backups | Out-Null
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T db pg_dump -U marketlens -d marketlens --file=/tmp/marketlens.sql
$stamp = Get-Date -Format yyyyMMdd-HHmmss
docker compose --env-file deploy/.env -f deploy/compose.yaml cp db:/tmp/marketlens.sql "D:\marketlens\data\backups\marketlens-$stamp.sql"
```

Backups contain your portfolio inputs; keep them private and outside Git. Restore
only to a separate empty test database first. Alembic downgrade of the initial
migration drops the portfolio table and is destructive; do not run it on real data
without a backup and explicit approval.
