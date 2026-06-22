# 🚀 Post-Pilot

**One-page command center — write one update, push it to Facebook, Instagram, TikTok, Google Business, and your website simultaneously.**

Built for food trucks, restaurants, hotels, cafes, and food companies.

---

## ✨ What It Does

Write a single post in the Command Center. Check the platforms you want. Hit **Push to All**.

Post-Pilot automatically:
- 📘 Posts to **Facebook** (text + photo, with scheduling)
- 📸 Posts to **Instagram** (photo + caption, with scheduling)
- 🎵 Generates a ready-to-record **TikTok script**
- 📍 Creates a **Google Business** post
- 🌐 Updates a **website banner** on your site (via 1-line embed)

All from one screen. No switching between apps.

---

## 🖥️ The Command Center

```
┌─────────────────────────────────────────────────────────────────┐
│ 🚀 Post-Pilot                       📘✅ 📸✅ 🎵✅ 📍❌ 🌐✅  │
├──────────────────┬──────────────────────────┬───────────────────┤
│ ✏️ COMPOSE       │ 👁️ LIVE PREVIEW           │ 📋 ACTIVITY FEED  │
│                  │                          │                   │
│ Caption textarea │ [FB] [IG] [TT] [GB] [WEB]│ ✅ FB Published   │
│ Image URL        │                          │ ✅ IG Published   │
│ Link URL         │  ┌─────────────────────┐ │ 🎵 TT Script ready│
│                  │  │ Mock post preview   │ │                   │
│ ☑ Facebook       │  │ for selected tab    │ │ 📊 QUICK STATS    │
│ ☑ Instagram      │  └─────────────────────┘ │ 7 posts / 2.4k    │
│ ☐ TikTok         │                          │ reach / 143 likes │
│ ☐ Google         │                          │                   │
│ ☑ Website        │                          │ ⚡ QUICK ACTIONS  │
│                  │                          │ [Generate][Cal]   │
│ [🚀 Push All]    │                          │                   │
└──────────────────┴──────────────────────────┴───────────────────┘
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/ShadowWalkerNC/Post-Pilot.git
cd Post-Pilot
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python app.py
# open http://localhost:5000
```

---

## 🔌 Platform Setup

| Platform | How to Connect | Docs |
|----------|---------------|------|
| **Facebook** | Click “Connect Facebook” in Setup | [developers.facebook.com](https://developers.facebook.com/apps/) |
| **Instagram** | Same OAuth as Facebook | [graph.facebook.com](https://developers.facebook.com/docs/instagram-api/) |
| **TikTok** | Script-only now; full API in Phase 4 | [developers.tiktok.com](https://developers.tiktok.com/) |
| **Google Business** | Click “Connect Google” in Setup | [console.cloud.google.com](https://console.cloud.google.com/) |
| **Website** | Add 1 line to your site’s `<head>` | See below |

### Website Banner — 1-Line Setup
```html
<!-- Add this to your website's <head> tag -->
<script src="https://YOUR-APP-URL/static/embed.js"></script>
```
Every time you push a website update in Post-Pilot, your banner updates automatically.

---

## 📁 Project Structure

```
Post-Pilot/
├── app.py                     # App factory: extensions, DB, error handlers
├── blueprints/
│   ├── auth.py                # Login, register, logout, OAuth flows
│   ├── billing.py             # Stripe checkout, portal, cancel, webhook
│   ├── api.py                 # All /api/* endpoints
│   ├── website.py             # Website hub + public site renderer
│   ├── pages.py               # Dashboard, setup, calendar, onboarding
│   └── utils.py               # Shared helpers (_uid, _get_tokens, etc.)
├── modules/
│   ├── publisher.py           # Universal push to all platforms
│   ├── validator.py           # Input validation for publish requests
│   ├── post_generator.py      # AI caption generation
│   ├── billing_manager.py     # Stripe integration
│   ├── plan_guard.py          # Subscription tier enforcement
│   ├── post_scheduler.py      # APScheduler integration
│   ├── analytics_client.py    # Meta Insights API
│   ├── auth_manager.py        # OAuth token storage
│   ├── user_manager.py        # User CRUD + login helpers
│   └── website_manager.py     # Website hub logic
├── templates/
│   ├── dashboard.html         # One-page command center
│   ├── index.html             # Landing page
│   ├── setup.html
│   ├── generate.html
│   ├── calendar.html
│   ├── analytics.html
│   └── billing.html
├── static/
│   ├── dashboard.js
│   ├── embed.js               # Website banner embed (1-line setup)
│   ├── banner.json            # Live banner data
│   └── style.css
├── tests/
│   ├── conftest.py
│   ├── test_smoke.py
│   ├── test_p0_fixes.py       # Billing bypass, XSS, OAuth CSRF
│   └── test_validator.py      # Input validation unit tests
├── .env.example
├── requirements.txt
└── TODO.md
```

---

## 🗺️ Roadmap

- [x] Phase 1 — Facebook + Instagram API + GUI
- [x] Phase 2 — Scheduler + Calendar + Analytics
- [x] Phase 3 — One-page command center + Google Business + Website banner
- [x] Phase 4 — SaaS billing, auth, plan enforcement, blueprint architecture
- [ ] Phase 5 — Alembic migrations, multi-user teams, advanced analytics

---

## 📄 License

MIT License — free to use, modify, and distribute.
