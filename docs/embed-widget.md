# PostPilot Embed Widget

Allow any external website to display your live specials, hours, and services
with a single `<div>` and one `<script>` tag — no login required for visitors.

## Quick Start

```html
<!-- 1. Place this div where you want the widget to appear -->
<div
  data-postpilot-slug="your-business-slug"
  data-postpilot-theme="light"
  data-postpilot-sections="posts,hours,services"
></div>

<!-- 2. Load the embed script (put before </body>) -->
<script src="https://yourapp.com/static/embed.js" async></script>
```

## Options

| Attribute | Values | Default | Description |
|---|---|---|---|
| `data-postpilot-slug` | your slug/username | *(required)* | Identifies your PostPilot account |
| `data-postpilot-theme` | `light` \| `dark` | `light` | Widget color scheme |
| `data-postpilot-sections` | comma-separated list | `posts,hours,services` | Which sections to show |

## Sections

- **posts** — up to 6 most recent published posts (with images)
- **hours** — business hours from your profile
- **services** — service cards with name, description, and price

## Finding Your Slug

Your slug is your **username** by default. A custom `embed_slug` column
can be set by an admin or via the Settings page (future feature).

## API Endpoint

The widget fetches data from:

```
GET /api/embed/<slug>
```

This endpoint is **public** (no authentication required). It returns:

```json
{
  "success": true,
  "name": "My Restaurant",
  "tagline": "Best pizza in town",
  "logo_url": "https://...",
  "about": "...",
  "hours": { "Monday": "9am – 9pm", ... },
  "services": [ { "name": "...", "description": "...", "price": "$12" } ],
  "recent_posts": [ { "caption": "...", "image_url": "...", "created_at": "..." } ]
}
```

## Registering the Blueprint

In `app.py`, import and register `embed_bp`:

```python
from blueprints.embed_api import embed_bp
app.register_blueprint(embed_bp)
```

## Database Note

The endpoint looks for `embed_slug` first, then falls back to `username`.
To add a custom slug column (optional):

```sql
ALTER TABLE users ADD COLUMN embed_slug TEXT UNIQUE;
```
