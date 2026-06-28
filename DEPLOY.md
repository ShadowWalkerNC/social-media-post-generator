# Deploying Post-Pilot

Post-Pilot is a Python/Flask web app deployed on **Railway** — the same platform as Sigil.
Both projects live under the same Railway account and auto-deploy on `git push` to `main`.

---

## 1. Create the Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `ShadowWalkerNC/Post-Pilot`
3. Railway detects `railway.toml` and configures the service automatically
4. Click **Deploy** — Railway runs `pip install -r requirements.txt` then starts gunicorn
5. Once live, go to **Settings → Networking → Generate Domain**:
   `https://post-pilot-production.up.railway.app`

---

## 2. Add Plugins (before setting Variables)

In the Railway project, add these two plugins first — they auto-inject their connection URLs:

| Plugin | Auto-injected Variable | Used for |
|--------|------------------------|----------|
| **PostgreSQL** | `DATABASE_URL` | Production database |
| **Redis** | `REDIS_URL` | Rate limiting across workers |

Railway dashboard → **New** → **Database** → select Postgres / Redis.

> **Local dev:** SQLite is still used by default when `DATABASE_URL` is not set.
> Set `DATABASE_PATH=postpilot.db` in your local `.env`. No volume needed locally.

---

## 3. Set Environment Variables

Railway dashboard → Post-Pilot service → **Variables** tab.
Use `.env.example` as the reference — all keys are documented there with notes.

| Variable | Where to get it |
|---|---|
| `FLASK_SECRET_KEY` | Any random 32+ char string |
| `TOKEN_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Auto-injected by Railway Postgres plugin |
| `SUPABASE_URL` | Supabase dashboard → Project Settings → API |
| `SUPABASE_ANON_KEY` | Same — "anon / public" key |
| `SUPABASE_SERVICE_ROLE_KEY` | Same — "service_role" key (keep secret, server-side only) |
| `REDIS_URL` | Auto-injected by Railway Redis plugin |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `STRIPE_SECRET_KEY` | [dashboard.stripe.com](https://dashboard.stripe.com) → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe → Webhooks → your endpoint → Signing secret |
| `STRIPE_PRICE_STARTER` | Stripe → Products → Starter → price ID |
| `STRIPE_PRICE_GROWTH` | Stripe → Products → Growth → price ID |
| `STRIPE_PRICE_AGENCY` | Stripe → Products → Agency → price ID |
| `FACEBOOK_APP_ID` | [developers.facebook.com](https://developers.facebook.com) |
| `FACEBOOK_APP_SECRET` | Same |
| `REDIRECT_URI` | `https://<your-railway-domain>/auth/facebook/callback` |
| `GOOGLE_CLIENT_ID` | [console.cloud.google.com](https://console.cloud.google.com) |
| `GOOGLE_CLIENT_SECRET` | Same |
| `GOOGLE_REDIRECT_URI` | `https://<your-railway-domain>/auth/google/callback` |
| `TIKTOK_CLIENT_KEY` | [developers.tiktok.com](https://developers.tiktok.com) |
| `TIKTOK_CLIENT_SECRET` | Same |
| `TIKTOK_REDIRECT_URI` | `https://<your-railway-domain>/auth/tiktok/callback` |
| `TWITTER_CLIENT_ID` | [developer.twitter.com](https://developer.twitter.com) → App → OAuth 2.0 settings |
| `TWITTER_CLIENT_SECRET` | Same |
| `TWITTER_REDIRECT_URI` | `https://<your-railway-domain>/auth/twitter/callback` |
| `SENTRY_DSN` | [sentry.io](https://sentry.io) → Project → Settings → DSN (optional) |

---

## 4. Run Alembic Migrations

After first deploy, run migrations to initialise the Postgres schema:

```bash
# Option A — via Railway CLI
railway run alembic upgrade head

# Option B — add a one-off start command in the Railway dashboard,
# run it once, then switch back to the gunicorn start command.
```

For subsequent deploys, migrations run automatically if you add this to `railway.toml`:
```toml
[build]
buildCommand = "pip install -r requirements.txt && alembic upgrade head"
```

---

## 5. Set Up Stripe Webhook

1. Stripe → **Developers** → **Webhooks** → **Add endpoint**
2. URL: `https://<your-railway-domain>/webhooks/stripe`
3. Events to subscribe:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy **Signing secret** → set as `STRIPE_WEBHOOK_SECRET` in Railway Variables

---

## 6. Create Stripe Products

Stripe dashboard → **Products** → **Add product** × 3:

| Product | Monthly | Annual |
|---------|---------|--------|
| Starter | $29/mo  | $290/yr |
| Growth  | $59/mo  | $590/yr |
| Agency  | $149/mo | $1,490/yr |

Copy the **price IDs** (`price_xxx`) into Railway Variables.

---

## 7. Wire Sigil → Post-Pilot

Once Post-Pilot is live:

1. Log in at `https://<your-railway-domain>` — create your account
2. Go to **Settings → API Keys** → **Create Key** → name it `sigil`
3. Copy the `pp_live_...` key
4. In Railway → Sigil project → **Variables**, set:
   ```
   POSTPILOT_URL=https://<your-post-pilot-railway-domain>
   POSTPILOT_API_KEY=pp_live_...
   POSTPILOT_USER_ID=<your user ID from Post-Pilot settings>
   ```
5. Sigil auto-redeploys
6. In Discord: `/poststatus` → 🟢 Online

---

## 8. Update SRN_REGISTRY.json

In `ShadowRealm/SRN_REGISTRY.json`, update:

```json
"postpilot": {
  "live_url": "https://<your-post-pilot-railway-domain>",
  "deploy_target": "railway",
  "status": "live"
}
```

---

## 9. Smoke Test Checklist

```
☐ GET  https://<domain>/           → marketing page loads
☐ GET  https://<domain>/v1/health  → { "status": "ok" }
☐ POST /register                   → account created, redirects to onboarding
☐ Complete onboarding              → business profile saved
☐ GET  /billing                    → plans shown, Stripe checkout works
☐ GET  /website                    → website hub loads
☐ GET  /site/preview               → preview iframe renders
☐ POST /v1/generate_post           → returns AI caption
☐ Discord /poststatus              → 🟢 Online
☐ Discord /postgenerate topic:test → caption embed appears
☐ Discord /post topic:test         → publishes
☐ POST /webhooks/stripe            → 200 OK (test with Stripe CLI)
```

---

## Local Development

```bash
git clone https://github.com/ShadowWalkerNC/Post-Pilot.git
cd Post-Pilot
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
python app.py
# Open http://localhost:5000
```
