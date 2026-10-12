# Hosting MarketLens on a free tier

## Recommended portfolio-demo setup

Use a **Render Static Site** for React and a **Render Free Web Service** for FastAPI.
The root `render.yaml` provides a two-service Blueprint. PostgreSQL is optional:
analytics, options, simulation and backtesting work without it. The repository can
be public while database credentials remain private in server environment settings.

The public demo configuration deliberately leaves saved-portfolio storage
unconfigured. The current persistence API is single-user and has no authentication
or per-user ownership: connecting a database to a public endpoint would allow
visitors to list, change and delete its saved portfolios. A hidden database password
does **not** protect those application endpoints. Add authentication/authorization
or put the entire app behind a trusted access gateway before enabling cloud storage.

## Deploy from GitHub

1. Connect your public MarketLens repository to Render.
2. Create a Blueprint using `render.yaml`, or create the two services below manually.
3. Set the backend environment variable `MARKETLENS_CORS_ORIGINS` to your actual
   frontend URL, e.g. `https://your-marketlens-web.onrender.com` (no trailing slash).
4. Set the frontend `VITE_API_BASE_URL` to your actual backend URL, e.g.
   `https://your-marketlens-api.onrender.com` (no trailing slash). It is a public URL,
   **not** a secret or token.
5. Deploy the API, then build/redeploy the frontend with the correct URL. If the
   URLs were not known initially, update both settings after Render assigns them.
6. Check the backend `/health`, open the frontend, and run a small option-price or
   simulation request. The API connection badge should report connected. Do not
   use `/ready` as this stateless demo's health check: it requires a database.

Manual service settings:

| Setting | Frontend | Backend |
| --- | --- | --- |
| Service type | Static Site | Web Service, Docker runtime |
| Root/context | `frontend` | Repository root |
| Dockerfile | None | `deploy/backend.Dockerfile` |
| Build | `npm ci && npm run build` | Dockerfile build |
| Publish directory | `dist` | Not applicable |
| Start override | None | `sh -c 'exec python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1'` |
| Health check | Not applicable | `/health` |
| Plan | Free static hosting | Free |

Add a frontend rewrite from `/*` to `/index.html` (included in the Blueprint).
The production frontend does not use Vite's development proxy. Changing a `VITE_`
variable requires rebuilding the frontend. Restrict CORS to the actual frontend
origin; it controls browser requests and is not an authorization mechanism.

Keep simulation sizes small on a free service, especially when several people
visit together. The API's five-million-value limit is a per-request limit; it does
not bound aggregate memory across simultaneous requests. This setup is for a
portfolio demo, not a production multi-user finance service. Provider requests may
also be rate-limited or blocked from shared cloud IPs.

## Free-tier limitations

Verified against provider documentation on 2026-10-11:

- Render offers free static sites and free web services. Free web services sleep
  after 15 minutes without traffic and can take about a minute to wake. Usage and
  build limits apply. Local files disappear on restart, redeploy or spin-down.
- Do **not** use SQLite for persistent cloud data on a free Render service.
- Render's free PostgreSQL database expires after 30 days, so it is unsuitable as
  the long-lived database for this project.
- Neon offers a free PostgreSQL plan with storage/compute/network allowances and
  idle scale-to-zero. Check the current plan dashboard before enabling it; limits
  can change. Do not choose a paid plan merely to bypass a demo limit.

Sources: [Render free services](https://render.com/docs/free),
[Render Blueprint specification](https://render.com/docs/blueprint-spec),
[Neon plans](https://neon.com/docs/introduction/plans).

Free hosting is not a guarantee of unlimited or permanent free availability. Check
usage alerts and billing settings. No hosted accounts or billable resources have
been created by adding these configuration files.

## PostgreSQL later, behind access control

1. Create a Neon free project and obtain its connection string privately.
2. Change its URI scheme from `postgresql://` to `postgresql+psycopg://` for this
   SQLAlchemy driver. Keep the host, credentials, database and TLS query parameters,
   including `sslmode=require`. Never paste the actual URL into Git or frontend code.
3. Set `MARKETLENS_DATABASE_URL` in the backend's private environment settings.
4. Run `python -m alembic upgrade head` with that environment before serving storage
   requests. For a single free instance without a release job, a start override can
   run `python -m alembic upgrade head && exec python -m uvicorn ...`; do not run
   competing migrations from multiple instances.
5. Check `/ready` and test create/load/update/delete with authentication enforced.
6. Configure backups separately; free-tier limits and retention differ by provider.

Database credentials stay on the backend. **Anything prefixed `VITE_` is included
in the browser bundle and must be safe for public disclosure.** The current yfinance
adapter does not require a MarketLens API key. If a future market-data provider
requires a key, store it only in server-side environment variables.

## GitHub Pages and alternative frontend hosting

GitHub Pages can serve static frontend files, but cannot run FastAPI or PostgreSQL.
Vercel Hobby is another option for a personal, noncommercial frontend; it does not
remove the need for a backend service and database. This project provides Render
configuration to keep the initial setup in one hosting dashboard.

## Deployment status

This guide and Blueprint prepare the project for hosting. They are not evidence of
a completed cloud deployment. Docker/Linux builds, cloud Yahoo connectivity and
PostgreSQL runtime tests must be verified on the selected host. Existing local test
results are documented in the root README.
