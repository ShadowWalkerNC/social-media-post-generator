# 🚀 PostPilot Pro

**Automated social media post generator for food trucks, restaurants, hotels, cafes, and food companies.**

Generates high-engagement posts and publishes directly to **Facebook & Instagram** via the Meta Graph API.

---

## ✨ Features

- 📝 **Auto-generate posts** — 7 days of posts in 1 click
- 📘 **Publish to Facebook** — Direct posting via Facebook Pages API
- 📸 **Publish to Instagram** — Direct posting via Instagram Graph API
- 📅 **Post Scheduler** — Schedule posts for future dates/times
- 📊 **Analytics Dashboard** — Track likes, comments, and reach
- 🖥️ **Web GUI** — No coding needed; run in your browser
- 🎯 **5 Business Types** — Food truck, restaurant, hotel, cafe, food company
- 🔁 **9 Post Templates** — Location, menu, engagement, team, giveaway, TikTok script, email, and more

---

## 📁 Project Structure

```
postpilot-pro/
│
├── app.py                       # Flask main app (GUI + API routes)
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
│
├── modules/
│   ├── post_generator.py        # Post generation logic
│   ├── meta_client.py           # Facebook/Instagram API integration
│   ├── post_scheduler.py        # Post scheduling logic
│   └── analytics_client.py     # Analytics fetching
│
├── templates/
│   ├── index.html               # Home / landing page
│   ├── setup.html               # Business setup form
│   ├── generate.html            # Generate & publish posts
│   ├── calendar.html            # Visual content calendar
│   └── analytics.html          # Analytics dashboard
│
└── static/
    ├── style.css                # Global styles
    └── app.js                   # Frontend logic
```

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/ShadowWalkerNC/postpilot-pro.git
cd postpilot-pro
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your Meta App ID and Secret
```

### 4. Run the app
```bash
python app.py
```

### 5. Open in browser
```
http://localhost:5000
```

---

## 🔑 Meta API Setup

1. Go to [developers.facebook.com](https://developers.facebook.com/apps/)
2. Create a new App → Select **Business** type
3. Add **Instagram Graph API** product
4. Request permissions:
   - `pages_manage_posts`
   - `pages_read_engagement`
   - `instagram_content_publish`
5. Add your `APP_ID` and `APP_SECRET` to `.env`
6. Click **Connect Facebook** in the app → OAuth flow handles the rest

---

## 📱 Supported Platforms

| Platform | Post Types | Scheduling |
|----------|------------|------------|
| Instagram | Photo, Carousel, Reel | ✅ |
| Facebook | Photo, Text, Link | ✅ |
| TikTok | Script generator | Coming soon |
| Email | Subject + body templates | Coming soon |

---

## 🏢 Business Types

| Type | Templates | Auto-Hashtags |
|------|-----------|---------------|
| Food Truck | Location, Menu, Engagement, Team, Giveaway | #cityeats #foodtruck |
| Restaurant | Location, Menu, Engagement, Team, Giveaway | #cityeats #finedining |
| Hotel | Location, Room, Engagement, Staff, Giveaway | #cityhotel #luxurytravel |
| Cafe | Location, Menu, Engagement, Team, Giveaway | #cityeats #cafe |
| Food Company | Product, Launch, Engagement, Team, Giveaway | #organicfood #foodie |

---

## 📅 Weekly Schedule (Auto-Generated)

| Day | Platform | Template | Time |
|-----|----------|----------|------|
| Monday | Instagram | Location | 8 AM |
| Tuesday | Instagram | Menu | 11 AM |
| Wednesday | Instagram | Engagement | 5 PM |
| Thursday | Instagram | Team | 8 AM |
| Friday | Facebook | Giveaway | 11 AM |
| Saturday | Instagram | Location | 8 AM |
| Sunday | Instagram | Poll | 5 PM |

---

## 🗺️ Roadmap

- [x] Phase 1 — GUI + Facebook/Instagram API
- [x] Phase 2 — Scheduler + Calendar + Analytics
- [ ] Phase 3 — Multi-user SaaS with login & billing
- [ ] Phase 4 — AI caption generation + image suggestions
- [ ] Phase 5 — TikTok + Google Business integration

---

## 🤝 Contributing

Pull requests welcome! Please open an issue first to discuss what you'd like to change.

---

## 📄 License

MIT License — free to use, modify, and distribute.
