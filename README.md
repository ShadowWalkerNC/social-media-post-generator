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
│ Caption textarea │ [FB] [IG] [TT] [GB] [WEB] │ ✅ FB Published   │
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
cp .env.example .env
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
<script src="https://YOUR-APP-URL/static/embed.js"></script>
```

---

## 📁 Project Structure

```
Post-Pilot/
├── app.py
├── blueprints/
│   ├── auth.py
│   ├── billing.py
│   ├── api.py
│   ├── website.py
│   ├── pages.py
│   └── utils.py
├── modules/
│   ├── publisher.py
│   ├── validator.py
│   ├── post_generator.py
│   ├── billing_manager.py
│   ├── plan_guard.py
│   ├── post_scheduler.py
│   ├── analytics_client.py
│   ├── auth_manager.py
│   ├── user_manager.py
│   └── website_manager.py
├── templates/
├── static/
├── tests/
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

## 🚀 Agent Session Bootstrap

This repo follows the **Universal Project Architect (UPA)** workflow. Start every AI session by loading the system files below and filling in the context block.

**Full reference:** [BOOT.md](https://github.com/ShadowWalkerNC/.github/blob/main/BOOT.md)

```
Load and follow these files before responding:
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/AGENTS.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/SESSION_START.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/AGENT_DISPATCH.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/UPA_V1.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/UPA_LIGHT_MODE.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/UPA_ESCALATION_CHECKLIST.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_COHERENCE.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_SECURITY.md
https://raw.githubusercontent.com/ShadowWalkerNC/.github/main/agents/AGENT_DOCS.md
https://raw.githubusercontent.com/ShadowWalkerNC/Post-Pilot/main/AGENTS.md
https://raw.githubusercontent.com/ShadowWalkerNC/Post-Pilot/main/ARCHITECTURE.md

PROJECT:      Post-Pilot
PHASE:        [current phase]
LAST COMMIT:  [SHA or description]
MODE:         [full | quick | audit | hotfix | onboard]
AGENT:        [Perplexity | Claude | Cursor | Copilot]
OPEN:         [2-3 open items or "see TODO"]
SCOPE:        [what you want this session]
OUT OF SCOPE: [what you are not doing]
```

---

## 📄 License

MIT License — free to use, modify, and distribute.
