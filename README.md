# 🚀 PostPilot Pro

**One-page command center — write one update, push it to Facebook, Instagram, TikTok, Google Business, and your website simultaneously.**

Built for food trucks, restaurants, hotels, cafes, and food companies.

---

## ✨ What It Does

Write a single post in the Command Center. Check the platforms you want. Hit **Push to All**.

PostPilot Pro automatically:
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
│ 🚀 PostPilot Pro                    📘✅ 📸✅ 🎵✅ 📍❌ 🌐✅  │
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
git clone https://github.com/ShadowWalkerNC/social-media-post-generator.git
cd social-media-post-generator
pip install -r requirements.txt
cp .env.example .env   # add your API keys
python app.py
# open http://localhost:5000
```

---

## 🔌 Platform Setup

| Platform | How to Connect | Docs |
|----------|---------------|------|
| **Facebook** | Click "Connect Facebook" in Setup | [developers.facebook.com](https://developers.facebook.com/apps/) |
| **Instagram** | Same OAuth as Facebook | [graph.facebook.com](https://developers.facebook.com/docs/instagram-api/) |
| **TikTok** | Script-only now; full API in Phase 4 | [developers.tiktok.com](https://developers.tiktok.com/) |
| **Google Business** | Click "Connect Google" in Setup | [console.cloud.google.com](https://console.cloud.google.com/) |
| **Website** | Add 1 line to your site's `<head>` | See below |

### Website Banner — 1-Line Setup
```html
<!-- Add this to your website's <head> tag -->
<script src="https://YOUR-APP-URL/static/embed.js"></script>
```
Every time you push a website update in PostPilot Pro, your banner updates automatically.

---

## 📁 Project Structure

```
postpilot-pro/
├── app.py                     # Flask app — all routes
├── modules/
│   ├── publisher.py           # 🆕 Universal push to all platforms
│   ├── post_generator.py      # Post generation logic
│   ├── meta_client.py         # Facebook + Instagram API
│   ├── post_scheduler.py      # APScheduler integration
│   └── analytics_client.py   # Meta Insights API
├── templates/
│   ├── dashboard.html         # 🆕 One-page command center
│   ├── index.html             # Landing page
│   ├── setup.html             # Business + token setup
│   ├── generate.html          # Bulk post generator
│   ├── calendar.html          # Content calendar
│   └── analytics.html        # Analytics dashboard
└── static/
    ├── dashboard.css          # 🆕 Command center styles
    ├── dashboard.js           # 🆕 Command center logic
    ├── embed.js               # 🆕 Website banner embed
    ├── banner.json            # 🆕 Live banner data
    ├── style.css
    └── app.js
```

---

## 🗺️ Roadmap

- [x] Phase 1 — Facebook + Instagram API + GUI
- [x] Phase 2 — Scheduler + Calendar + Analytics
- [x] Phase 3 — One-page command center + Google Business + Website banner
- [ ] Phase 4 — TikTok full auto-post + AI captions + image suggestions
- [ ] Phase 5 — Multi-user SaaS with login, billing, and team accounts

---

## 📄 License

MIT License — free to use, modify, and distribute.
