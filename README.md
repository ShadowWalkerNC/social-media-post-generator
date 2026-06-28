# 🚀 Post-Pilot

**AI-powered social media automation for food trucks, restaurants, hotels, cafes, and food companies.**

Generates high-engagement posts via Anthropic Claude and publishes directly to Facebook & Instagram via the Meta Graph API. Runs as a Flask SaaS on Vercel with Supabase (PostgreSQL), Stripe billing, magic-link auth, and Vercel Cron for scheduled publishing.

> **Status:** In production · Phase 5 in progress (Teams, Alembic migrations, Redis, analytics)

---

## 📄 Documentation

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, module map, data flow, DB schema, integrations |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | Local setup, env vars, testing, branching, deployment |
| [AGENTS.md](./AGENTS.md) | AI agent instructions and project-specific rules |
| [TODO.md](./TODO.md) | Current open work and priorities |
| [PLANNING.md](./PLANNING.md) | Full UPA phase planning document |
| [DEPLOY.md](./DEPLOY.md) | Vercel deployment runbook |
| [CHANGELOG.md](./CHANGELOG.md) | What changed and when |
| [V1_API.md](./V1_API.md) | External API reference |

---

## ✨ What It Does

- Generates platform-optimised posts using Anthropic Claude
- Publishes directly to **Facebook** and **Instagram** via Meta Graph API
- Schedules posts with **Vercel Cron** (fires every minute, HMAC-authenticated)
- Manages subscriptions with **Stripe** (Starter / Pro / Agency plans)
- Authenticates users via **magic link email** (no passwords)
- Monitors errors in production via **Sentry**
- Enforces plan limits per user with `@require_plan` decorator

---

## 🏗️ Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Flask 3.x |
| Database | Supabase (PostgreSQL) via SQLAlchemy + psycopg2 |
| Hosting | Vercel (serverless + Vercel Cron) |
| AI | Anthropic Claude (claude-3-5-sonnet) |
| Auth | Magic link email (Flask-Mail + JWT) |
| Payments | Stripe (subscription billing) |
| Observability | Sentry (`sentry-sdk[flask]`) |
| Rate limiting | Flask-Limiter + Upstash Redis |
| Migrations | Alembic |
| CI/CD | GitHub Actions (ruff + pytest) |
| Styling | Tailwind CSS (Jinja2 templates) |

---

## 📁 Project Structure

```
Post-Pilot/
  app.py                  ← Flask app factory, blueprint registration, Sentry init
  blueprints/             ← Flask blueprints (one file per domain)
    auth.py               ← Magic link auth, session management
    dashboard.py          ← Post queue, platform overview
    generate.py           ← AI post generation (Claude)
    publish.py            ← Meta Graph API publish logic
    scheduler.py          ← Post scheduling interface
    cron.py               ← Vercel Cron endpoint (/api/cron/publish)
    billing.py            ← Stripe subscription management
    onboarding.py         ← New user setup flow
    settings.py           ← Account and platform settings
    admin.py              ← Internal admin tools
  modules/                ← Shared utilities and services
    db.py                 ← SQLAlchemy engine, session factory, base models
    database.py           ← Safe proxy to db.py (backward compat)
    models.py             ← ORM models: User, Post, Platform, Schedule, Plan
    ai.py                 ← Claude API wrapper, prompt management
    meta_api.py           ← Meta Graph API client
    scheduler_utils.py    ← _publish_scheduled_posts() — called by cron
    auth_utils.py         ← JWT, magic link generation, session helpers
    billing_utils.py      ← Stripe helpers, @require_plan decorator
    rate_limit.py         ← Flask-Limiter + Redis config
  templates/              ← Jinja2 HTML templates
  static/                 ← Tailwind CSS, JS, images
  alembic/                ← Database migrations (forward-only)
    versions/             ← Migration files
  tests/                  ← pytest test suite
  mcp/                    ← Post-Pilot MCP server (planned)
  .github/
    workflows/ci.yml      ← GitHub Actions: ruff + pytest + coverage
  vercel.json             ← Vercel deployment + Cron config
  requirements.txt        ← Pinned Python dependencies
  .env.example            ← All required env vars (no values)
```

---

## ⚡ Quick Start

```bash
git clone https://github.com/ShadowWalkerNC/Post-Pilot.git
cd Post-Pilot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env — see DEVELOPMENT.md for the full guide
alembic upgrade head
flask run
# open http://localhost:5000
```

See [DEVELOPMENT.md](./DEVELOPMENT.md) for the complete setup guide, env var reference, and troubleshooting.

---

## 🗺️ Roadmap

- [x] Phase 1 — Facebook + Instagram API integration
- [x] Phase 2 — Post scheduler + calendar
- [x] Phase 3 — SaaS billing (Stripe), magic link auth, plan enforcement
- [x] Phase 4 — Blueprint architecture, Vercel Cron, Sentry, CI hardening
- [ ] **Phase 5** — Alembic migration cleanup, multi-user teams, Redis rate limiting, analytics dashboard
- [ ] Phase 6 — Public launch, onboarding flow, marketing site

---

## 🤖 AI Agent Session Bootstrap

This repo follows the **Universal Project Architect (UPA)** framework. Every AI session (Perplexity, Claude, or any coding agent) must load the bootstrap files before planning or making changes.

**Full bootstrap reference:** [BOOT.md](https://github.com/ShadowWalkerNC/.github/blob/main/BOOT.md)

### Quick bootstrap (paste as first message)

```
Load and follow these files before responding:
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/AGENTS.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/SESSION_START.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/AGENT_DISPATCH.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/UPA_V1.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_COHERENCE.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_SECURITY.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_DOCS.md
https://raw.githubusercontent.com/ShadowWalkerNC/Post-Pilot/main/AGENTS.md
https://raw.githubusercontent.com/ShadowWalkerNC/Post-Pilot/main/ARCHITECTURE.md

PROJECT:      Post-Pilot
PHASE:        5 — Teams, Alembic migrations, Redis, analytics
LAST COMMIT:  [paste last commit SHA or message]
MODE:         [full | quick | audit | hotfix | onboard]
AGENT:        [Perplexity | Claude]
OPEN:         SEC-1 (key rotation), INFRA-6 (register cron blueprint), [your third item]
SCOPE:        [what you want this session]
OUT OF SCOPE: [what you are not doing]
```

**iPhone shortcut:** Use `;upa` text replacement to expand the full block on mobile. See [BOOT.md](https://github.com/ShadowWalkerNC/.github/blob/main/BOOT.md) for setup instructions.

---

## 📄 License

MIT License — free to use, modify, and distribute.
