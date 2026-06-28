# Post-Pilot — Task List
*Last updated: 2026-06-28 — UPA session (specials table + schedule UI + agent rewrite)*

Priority levels: 🔴 Critical (stop-ship) · 🟠 High · 🟡 Medium · 🟢 Low

---

## 🔴 CRITICAL — Manual Steps Required (You Must Do These)

### SEC-1 · Rotate TOKEN_ENCRYPTION_KEY
- [x] `.gitignore` created — `.env`, `*.db`, `.venv/`, `__pycache__/` covered
- [x] `.env` replaced with safe placeholders
- [ ] **Generate new Fernet key locally:**
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- [ ] **Update `TOKEN_ENCRYPTION_KEY` in Vercel environment variables**
- [ ] **Update `FLASK_SECRET_KEY` in Vercel environment variables**
- [ ] **Re-encrypt existing `platform_tokens` rows** (write one-time migration if real tokens exist)

### SEC-2 · Remove binary files from git tracking (run locally)
- [ ] **Run locally and push:**
  ```bash
  git rm --cached postpilot.db .venv __pycache__ -r --ignore-unmatch
  git commit -m "chore: untrack .db, .venv, __pycache__"
  git push
  ```

### SEC-3 · Confirm /dev-login is disabled in production
- [ ] **Confirm `DEV_LOGIN_KEY` is absent or empty in Vercel production env vars**

---

## 🟠 HIGH PRIORITY

### INFRA-1 · Confirm production redeploy is live
- [ ] Trigger fresh Vercel redeploy after rotating keys
- [ ] Smoke test: visit `/login`, request magic link
- [ ] Check Vercel Cron tab — confirm both `/api/cron/generate` and `/api/cron/publish` are listed

### INFRA-2 · Add Redis for real rate limiting
- [ ] Provision Upstash Redis (free tier — https://upstash.com)
- [ ] Add `REDIS_URL` to Vercel environment variables

### INFRA-6 · Scheduler — Vercel Cron
- [x] `/api/cron/publish` — every minute
- [x] `/api/cron/generate` — every hour → calls AutomationAgent
- [x] `vercel.json` updated — both cron jobs registered
- [ ] **Add `CRON_SECRET` to Vercel environment variables:**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

### INFRA-7 · Automation Agent
- [x] `modules/automation_agent.py` — reads specials table, generates per-platform captions, queues post_history rows
- [x] `alembic/versions/0004_automation_log.py` — audit trail table
- [x] `alembic/versions/0005_specials.py` — specials table
- [x] `blueprints/specials.py` — full CRUD API + /schedule page route
- [x] `templates/schedule.html` — schedule management UI
- [ ] **Register `specials_bp` in `blueprints/__init__.py`** (see below)
- [ ] **Apply migrations:** `alembic upgrade head` (runs 0003, 0004, 0005)
- [ ] **Add `OPENAI_API_KEY` to Vercel environment variables**
- [ ] **Add `CRON_SECRET` to Vercel environment variables**
- [ ] **Add `/schedule` link to dashboard sidebar nav**
- [ ] Test: add a special via UI, POST `/api/cron/generate`, confirm post_history row created

### REGISTER specials_bp
Add to `blueprints/__init__.py`:
```python
from blueprints.specials import specials_bp
app.register_blueprint(specials_bp)
# also add to CSRF exempt list if using flask-wtf
```

---

## 🟡 MEDIUM PRIORITY

### AUTOMATION-2 · Agent activity dashboard
- [ ] `/dashboard/automation` page — show `automation_log` rows for current user
- [ ] Display: content_type, tone, scheduled_at, master_caption preview, status

### DEV-1 · CI pipeline
- [ ] Add `CI_TOKEN_ENCRYPTION_KEY` to GitHub Actions secrets

### DEV-2 · Error monitoring
- [ ] Sign up at https://sentry.io, add `SENTRY_DSN` to Vercel

### DB-1 · Drop password_hash
- [x] Migration `0003_drop_password_hash.py` written
- [ ] `alembic upgrade head`

---

## 🟢 LOW PRIORITY

### PERF-1 · Caching layer
- [ ] Add Redis-backed caching for 3 most-called DB queries

### OPS-1 · Structured logging
- [ ] Replace `print()` statements with `app.logger` calls

### UX-1 · Favicon
- [ ] Add `favicon.ico` to `static/` and `<link rel="icon">` to `base.html`

---

## ✅ COMPLETED

- [x] AUTOMATION-1: `specials` table migration + CRUD blueprint + schedule UI
- [x] AUTOMATION-1: `automation_agent.py` rewritten — reads specials, no more invented content
- [x] INFRA-7: `automation_agent.py` v1 — original agent loop + automation_log table
- [x] INFRA-6: Vercel Cron — `/api/cron/generate` (hourly) + `/api/cron/publish` (every minute)
- [x] Publisher: LinkedIn and Pinterest stubs removed
- [x] Publisher: `_update_website` fixed — writes to DB instead of ephemeral filesystem
- [x] Publisher: `timeout=15` added to all `requests` calls
- [x] DB-1: `0003_drop_password_hash.py` written
- [x] Sentry, CI, CORS, `/dev-login` guard, OAuth state namespacing, XSS fix
- [x] `AGENTS.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `README.md` all written
