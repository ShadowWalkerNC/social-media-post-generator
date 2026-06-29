# Post-Pilot — Task List
*Last updated: 2026-06-28 — Phase 1 complete*

Priority levels: 🔴 Critical (stop-ship) · 🟠 High · 🟡 Medium · 🟢 Low

---

## 🔴 CRITICAL — You Must Do These Manually

### SEC-1 · Rotate encryption keys
- [ ] `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Update `TOKEN_ENCRYPTION_KEY` in Vercel env vars
- [ ] Update `FLASK_SECRET_KEY` in Vercel env vars
- [ ] Re-encrypt any existing `platform_tokens` rows

### SEC-2 · Remove binary files from git
```bash
git rm --cached postpilot.db .venv __pycache__ -r --ignore-unmatch
git commit -m "chore: untrack .db, .venv, __pycache__"
git push
```

### SEC-3 · Disable dev login in production
- [ ] Confirm `DEV_LOGIN_KEY` is absent or empty in Vercel production env vars

---

## 🟠 HIGH — Pending Manual Steps

### INFRA · Env vars to add to Vercel
- [ ] `OPENAI_API_KEY`
- [ ] `CRON_SECRET` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] `STRIPE_PRICE_STARTER_MONTHLY` / `STRIPE_PRICE_STARTER_ANNUAL`
- [ ] `STRIPE_PRICE_PRO_MONTHLY` / `STRIPE_PRICE_PRO_ANNUAL`
- [ ] `STRIPE_PRICE_AGENCY_MONTHLY` / `STRIPE_PRICE_AGENCY_ANNUAL`
- [ ] `REDIS_URL` — provision free Upstash Redis at https://upstash.com

### INFRA · After pushing
- [ ] Run `alembic upgrade head` — applies migrations 0003 through 0006
- [ ] Trigger fresh Vercel redeploy
- [ ] Smoke test: `/login` → magic link → `/schedule` → add a special → POST `/api/cron/generate` → confirm `post_history` row created
- [ ] Add `/schedule` link to dashboard sidebar nav

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

- [ ] Stripe webhook handler (`/billing/webhook`) — sync subscription tier on payment events
- [ ] Agent activity log page (`/dashboard/automation`) — show `automation_log` rows
- [ ] `check_post_limit()` wired into `api_publish` and `api_push_all`
- [ ] CI pipeline — add `CI_TOKEN_ENCRYPTION_KEY` to GitHub Actions secrets
- [ ] Sentry — sign up at https://sentry.io, add `SENTRY_DSN` to Vercel

---

## 🟢 LOW

- [ ] Redis-backed caching for hot DB queries
- [ ] Replace `print()` with `app.logger` calls
- [ ] Favicon (`static/favicon.ico`)
- [ ] Mobile-responsive dashboard nav
- [ ] Bulk reschedule / drag-and-drop calendar view

---

## ✅ COMPLETED

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
