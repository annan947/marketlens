# Deployment verification milestone

## Automated Linux checks

`.github/workflows/verify.yml` runs on pushes to `main`, pull requests and manual
workflow dispatch. It uses read-only repository permissions and pins GitHub actions
to verified v6 commit IDs. No production API keys or database credentials are needed.

The `tests` job provisions an isolated PostgreSQL 18 service, installs the project's
Python dependencies, builds the optional C++ engine on Linux, runs all pytest tests
including the PostgreSQL test, then tests and builds the frontend. The service's
hardcoded `marketlens_test` password is disposable CI test data, not a real secret.

After tests pass, `compose` generates a fresh random password into an ignored `.env`,
builds both Linux images, starts the real Compose stack, waits for health checks and
runs `scripts/deployment_smoke.py`. The smoke test checks:

- Nginx serves the frontend HTML.
- `/ready` confirms database connectivity and the expected migration.
- Options and simulation requests return known valid results.
- A unique test portfolio can be created, read, updated and deleted.
- A stale update is rejected.

It repeats after a backend restart. The smoke test deletes only its own uniquely
identified test row; it does not clear other portfolios. The runner stops its stack
at the end. It does not upload environment files or expanded Compose configuration.

Run the same smoke check locally after the stack is healthy:

```powershell
.\backend\.venv\Scripts\python.exe scripts/deployment_smoke.py --url http://127.0.0.1:8080
```

The script exercises the deployed HTTP service, not just functions in the Python
process. It does not verify browser layout or Yahoo's live availability. Those checks
remain separate before announcing a hosted release.

## Local Windows prerequisite

The inspection on 2026-10-12 found neither Docker Desktop nor an installed WSL
runtime. Docker setup was approved, with application and main disk locations under
`D:\marketlens`. The official installer is downloaded to
`D:\marketlens\downloads\Docker Desktop Installer.exe` and the helper verifies its
Authenticode signature before execution.

This agent session is not elevated. Complete installation from **Administrator
PowerShell**:

```powershell
cd D:\marketlens
.\deploy\install-docker.ps1
```

If Docker reports that WSL is missing, follow its Windows setup prompt. WSL setup
may require Windows component changes and a restart. Windows-managed integration
files can still be placed on C:; the intended Docker application and large disk are
on D:. The helper does not accept the license automatically. Open Docker Desktop
after installation to finish setup, review the license, and verify the disk path
before pulling images. Existing Docker data must not be moved or removed casually.

Once `docker version` reports a running server:

```powershell
.\deploy\setup-env.ps1
docker compose --env-file deploy/.env -f deploy/compose.yaml config --quiet
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d --wait
.\backend\.venv\Scripts\python.exe scripts/deployment_smoke.py
```

Use the assigned website URL only after successful checks. Do not infer deployment
success from the presence of configuration files or a downloaded installer.

## Completion criteria

- A green `Verify deployment` workflow on the current GitHub commit, or equivalent
  successful local PostgreSQL/Linux container checks.
- Desktop and mobile browser checks on the built frontend, including errors and
  loading states.
- No credentials in tracked files or history; private environment values configured
  outside the repository.

At preparation time, workflow syntax and action references were checked locally.
The actual PostgreSQL/Linux container run is still pending Windows setup or a
successful GitHub Actions run. This document does not claim those checks passed.
