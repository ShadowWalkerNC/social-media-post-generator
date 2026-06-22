# Post-Audit Manual TODO

These steps were identified during the production-readiness audit (2026-06-21).
Code-level fixes have been applied automatically. The items below require
manual action in Railway and GitHub.

---

## 1. Activate PostgreSQL on Railway

- In Railway project dashboard → **+ New** → **Database → PostgreSQL**
- Railway auto-sets `DATABASE_URL` in your environment
- The app detects it automatically via `modules/db.py` and switches from SQLite
- **Why:** SQLite on Railway's ephemeral filesystem means all data is wiped on every redeploy/restart

---

## 2. Add GitHub Actions Secret

- Go to **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**
- Name: `CI_TOKEN_ENCRYPTION_KEY`
- Value: a valid Fernet key — generate one with:
  ```
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **Why:** The CI pipeline (`.github/workflows/ci.yml`) needs this to run tests without crashing on import

---

## 3. Provision Redis on Railway (required for production rate limiting)

- In Railway project dashboard → **+ New** → **Database → Redis**
- Railway auto-sets `REDIS_URL` in your environment
- Flask-Limiter will automatically use it (already configured in `app.py`)
- **Why:** Without Redis, each gunicorn worker has its own rate-limit counter.
  A user effectively gets `5 × N` login attempts where N = worker count.

---

## Status

- [ ] Railway PostgreSQL provisioned
- [ ] GitHub secret `CI_TOKEN_ENCRYPTION_KEY` added
- [ ] Redis provisioned on Railway
- [x] `init_scheduler()` guarded to main process only (code fix applied)
- [x] `@require_plan` applied to all premium routes (code fix applied)
- [x] `check_platform_limit` enforced on both `/api/push_all` and `/api/publish` (code fix applied)
- [x] XSS in fallback site renderer fixed (code fix applied)
- [x] OAuth state keys namespaced per-platform (code fix applied)
- [x] `?limit=abc` ValueError fixed in `api_post_history` (code fix applied)
- [x] Silent exception swallowing now logs via `app.logger.exception()` (code fix applied)
- [x] `import requests` moved to top-level (code fix applied)
- [x] `WTF_CSRF_TIME_LIMIT` raised to 7200 (code fix applied)
- [x] `REDIS_URL` and `APP_ENV` added to `.env.example` (code fix applied)
