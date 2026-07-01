# Post-Pilot — Task List
*Last updated: 2026-06-30 — Audit complete, go-live steps documented*

Priority levels: 🔴 Critical (stop-ship) · 🟠 High · 🟡 Medium · 🟢 Low

---

## 🔴 CRITICAL — You Must Do These Manually (Go-Live Blockers)

### STEP 1 · Generate secure keys (run locally)
```bash
# Flask secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Fernet encryption key for platform_tokens
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Cron secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### STEP 2 · Add to Vercel Environment Variables
- [ ] `FLASK_SECRET_KEY` → output from Step 1
- [ ] `TOKEN_ENCRYPTION_KEY` → Fernet key from Step 1
- [ ] `CRON_SECRET` → urlsafe token from Step 1
- [ ] `OPENAI_API_KEY` → from https://platform.openai.com
- [ ] `STRIPE_PRICE_STARTER_MONTHLY` / `STRIPE_PRICE_STARTER_ANNUAL`
- [ ] `STRIPE_PRICE_GROWTH_MONTHLY` / `STRIPE_PRICE_GROWTH_ANNUAL`
- [ ] `STRIPE_PRICE_PRO_MONTHLY` / `STRIPE_PRICE_PRO_ANNUAL`
- [ ] `STRIPE_PRICE_AGENCY_MONTHLY` / `STRIPE_PRICE_AGENCY_ANNUAL`
- [ ] `REDIS_URL` — provision free tier at https://upstash.com, copy Redis URL
- [ ] `SENTRY_DSN` — optional, from https://sentry.io (add for production error tracking)

### STEP 3 · Add to GitHub Actions Secrets
- [ ] Go to: repo → Settings → Secrets and variables → Actions
- [ ] Add `CI_TOKEN_ENCRYPTION_KEY` → same Fernet key used in Vercel

### STEP 4 · Run DB migrations
```bash
# From your local machine or Railway shell
DATABASE_URL=your_postgres_connection_string alembic upgrade head
```
> Applies migrations 0003 through 0006 (specials, events, hours_overrides tables)

### STEP 5 · Security check
- [ ] Confirm `DEV_LOGIN_KEY` is **absent or empty** in Vercel production env vars
- [ ] Re-encrypt any existing `platform_tokens` rows if TOKEN_ENCRYPTION_KEY changed

### STEP 6 · Git cleanup — remove tracked binaries
```bash
git rm --cached postpilot.db .venv __pycache__ -r --ignore-unmatch
git commit -m "chore: untrack .db, .venv, __pycache__"
git push
```

### STEP 7 · Deploy + Smoke Test
- [ ] Trigger fresh Vercel redeploy after all env vars are set
- [ ] Visit `/login` → receive magic link → click link → land on dashboard
- [ ] Go to `/schedule` → add a Special
- [ ] `POST /api/cron/generate` with `Authorization: Bearer <CRON_SECRET>` header
- [ ] Confirm a row appears in `post_history` table
- [ ] Visit `/billing` → verify plan tiers display correctly
- [ ] Connect one platform (Facebook or Google) via `/settings`

---

## 🟠 HIGH — Phase 2: Website Embed

- [ ] `alembic/0007_business_slug.py` — add `slug` to `business_profiles`
- [ ] Onboarding step: choose/confirm slug (auto-generated from business name, user can edit once)
- [ ] `blueprints/embed.py` — `GET /api/public/<slug>/feed` → public JSON (no auth required)
- [ ] `static/embed.js` — 10-line drop-in script for any website
- [ ] `templates/embed_preview.html` — live preview + copy embed code in dashboard

---

## 🟠 HIGH — Phase 3: Inbox

- [ ] `alembic/0008_inbox.py` — `inbox_items` table
- [ ] `modules/comment_poller.py` — polls FB + IG Graph API for new comments on recent posts
- [ ] `modules/reply_agent.py` — generates AI draft reply per comment, tone-matched to business
- [ ] `blueprints/inbox.py` — list inbox, approve / edit / reject
- [ ] `templates/inbox.html` — comment feed + Approve / Edit / Skip buttons
- [ ] `vercel.json` — add `/api/cron/poll_comments` every 15 min

---

## 🟡 MEDIUM

- [ ] `check_post_limit()` wired into `api_publish` and `api_push_all`
- [ ] Agent activity log page (`/dashboard/automation`) — show `automation_log` rows
- [ ] Add `/schedule` link to dashboard sidebar nav
- [ ] Replace `print()` with `app.logger` calls

---

## 🟢 LOW

- [ ] Redis-backed caching for hot DB queries
- [ ] Favicon (`static/favicon.ico`)
- [ ] Mobile-responsive dashboard nav
- [ ] Bulk reschedule / drag-and-drop calendar view

---

## ✅ COMPLETED

- [x] CI pipeline — `.github/workflows/ci.yml` (lint + pytest + coverage on push/PR)
- [x] Stripe webhook handler — `billing_manager.py` handles all 5 Stripe events (verified 2026-06-30)
- [x] Tests — `test_smoke.py`, `test_p0_fixes.py`, `test_validator.py`, `conftest.py` (verified 2026-06-30)
- [x] MCP server — `mcp/server.py` with 7 real tools, stdio + SSE transport (verified 2026-06-30)
- [x] All 11 blueprints registered and CSRF-exempted correctly (verified 2026-06-30)
- [x] PHASE 1: Events table + CRUD blueprint (`blueprints/events.py`)
- [x] PHASE 1: Hours overrides table + CRUD blueprint (`blueprints/hours.py`)
- [x] PHASE 1: Migration `0006_events_hours.py` — `events` + `hours_overrides` tables
- [x] PHASE 1: `automation_agent.py` v3 — reads specials + events + hours
- [x] PHASE 1: `schedule.html` — tabbed UI (Specials / Events / Hours) with per-tab modals
- [x] PHASE 1: `blueprints/__init__.py` — registers specials_bp, events_bp, hours_bp + CSRF exemptions
- [x] BILLING-1: `plan_guard.py` — Free/Starter/Pro/Agency tiers, post/platform/location limits
- [x] BILLING-1: `billing.html` — correct prices, monthly/annual toggle, annual totals
- [x] AUTOMATION-1: `specials` table + CRUD + agent v2
- [x] INFRA-6: Vercel Cron — `/api/cron/generate` (hourly) + `/api/cron/publish` (every minute)
- [x] Publisher: `_update_website` fixed, timeout=15, LinkedIn/Pinterest stubs removed
- [x] Security: `.gitignore`, `.env` placeholders, `/dev-login` guard, XSS fix, CORS, OAuth state
- [x] Docs: `AGENTS.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `README.md`
