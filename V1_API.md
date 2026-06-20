# Post-Pilot — V1 API Reference

Base URL: `https://your-postpilot.onrender.com`

This is the **human-readable** reference for Post-Pilot's `/v1/` API layer.
For the machine-readable version, call `GET /v1/manifest`.

Post-Pilot is **ShadowRealm Network (SRN) compliant** — see [`SHADOWREALM_NETWORK.md`](./SHADOWREALM_NETWORK.md).

---

## Authentication

All `/v1/*` endpoints except `/v1/health` require:

```http
Authorization: Bearer <token>
X-SRN-App: <your-app-name>
```

Two token types are accepted:

| Type | Format | Issued by | Use case |
|------|--------|-----------|----------|
| User API key | `pp_live_xxx` | Post-Pilot dashboard | Your own integrations |
| SRN secret | `srn_live_xxx` | You (shared) | ShadowRealm / Sigil |

---

## Endpoints

### `GET /v1/health`
Public — no auth required.

```json
{ "status": "ok", "app": "post-pilot", "version": "1.0.0", "uptime": 1234567 }
```

---

### `GET /v1/manifest`
Returns Post-Pilot's full tool list in SRN manifest format.
Used by ShadowRealm on boot.

```bash
curl https://your-postpilot.onrender.com/v1/manifest \
  -H 'Authorization: Bearer pp_live_xxx'
```

---

### `POST /v1/generate_post`
Generate an AI caption for a topic.

**Body:**
```json
{
  "topic":    "Brisket Tacos are back on the menu",
  "platform": "instagram",
  "tone":     "exciting",
  "user_id":  "usr_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "caption":  "They’re back and better than ever 🔥 Brisket Tacos just landed...",
    "hashtags": ["#BBQ", "#FoodTruck", "#BrisketTacos"]
  }
}
```

---

### `POST /v1/publish_post`
Publish a caption to one or more platforms.

**Body:**
```json
{
  "caption":      "Brisket Tacos are back 🔥",
  "platforms":    ["facebook", "instagram", "tiktok"],
  "user_id":      "usr_abc123",
  "image_url":    "https://example.com/photo.jpg",
  "scheduled_at": 1750000000
}
```

`scheduled_at` is a Unix timestamp. Omit to publish immediately.

**Response:**
```json
{
  "success": true,
  "data": {
    "post_id": "ph_xyz789",
    "results": {
      "facebook":  { "success": true,  "url": "https://facebook.com/..." },
      "instagram": { "success": true,  "url": "https://instagram.com/..." },
      "tiktok":    { "success": false, "error": "No TikTok account connected" }
    }
  }
}
```

---

### `POST /v1/generate_and_publish`
One-shot: generate a caption then publish it. **Used by Sigil's `/post` command.**

**Body:**
```json
{
  "topic":     "Today's special: Brisket Tacos $12",
  "platforms": ["facebook", "instagram"],
  "tone":      "exciting",
  "user_id":   "usr_abc123",
  "image_url": "https://example.com/tacos.jpg"
}
```

---

### `GET /v1/get_history`
Get recent post history.

```bash
curl 'https://your-postpilot.onrender.com/v1/get_history?user_id=usr_abc123&limit=10' \
  -H 'Authorization: Bearer pp_live_xxx'
```

---

### `GET /v1/get_site_config`
Get website hub config for a user.

```bash
curl 'https://your-postpilot.onrender.com/v1/get_site_config?user_id=usr_abc123' \
  -H 'Authorization: Bearer pp_live_xxx'
```

---

### `POST /v1/set_published`
Publish or unpublish a user's website.

```json
{ "user_id": "usr_abc123", "published": true }
```

---

## API Key Management

These routes use **session auth** (Flask-Login), not Bearer tokens.
Call them from the Post-Pilot dashboard.

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/v1/keys/create` | Create a new `pp_live_xxx` key |
| `GET`  | `/v1/keys`        | List keys (values redacted) |
| `POST` | `/v1/keys/revoke` | Revoke a key by `key_id` |

### Create a key
```json
POST /v1/keys/create
{ "label": "Sigil Bot", "ttl_days": 365 }
```

Response:
```json
{ "success": true, "data": { "key": "pp_live_abc...", "label": "Sigil Bot", "expires_at": 1781234567 } }
```

> ⚠️ The full key value is **only shown once**. Store it immediately in your `.env`.

---

## Registering with `app.py`

Add to your Flask app:

```python
from modules.api_manager import v1 as v1_blueprint
app.register_blueprint(v1_blueprint)
```

And add to your DB init:

```python
from modules.api_manager import CREATE_API_KEYS_TABLE
db.execute(CREATE_API_KEYS_TABLE)
```

---

## Sigil Integration

Sigil calls Post-Pilot via `generate_and_publish` — the simplest flow:

```
Discord /post command
  → src/services/postpilot.js
  → POST /v1/generate_and_publish
  → Post-Pilot generates + publishes
  → Sigil replies: "✅ Posted to Facebook + Instagram"
```

`.env` keys needed in Sigil:
```bash
POSTPILOT_URL=https://your-postpilot.onrender.com
POSTPILOT_API_KEY=pp_live_xxx   # created via /v1/keys/create
POSTPILOT_USER_ID=usr_abc123    # the Post-Pilot user_id this guild maps to
```
