# ShadowRealm Network — App Contract v1.0

Every app in the **ShadowWalkerNC ecosystem** follows this contract.
This file is identical across all repos. Do not modify it per-app —
use `V1_API.md` for app-specific tool documentation.

---

## Purpose

The ShadowRealm Network (SRN) allows every app to:
- **Discover** what other apps can do (via `/v1/manifest`)
- **Call** other apps as tools over authenticated HTTP
- **Report** health status to the ShadowRealm orchestrator
- Stay **independent** (each app runs and deploys on its own) while being **interconnected** (any app can call any other)

---

## Required Endpoints

Every SRN-compliant app MUST implement these three routes:

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /v1/health` | None | Liveness check — always public |
| `GET /v1/manifest` | Bearer token | Machine-readable tool list |
| `POST /v1/<tool_name>` | Bearer token | Execute a tool |

---

## Authentication

All `/v1/*` routes **except `/v1/health`** require:

```http
Authorization: Bearer <api_key>
X-SRN-App: <calling_app_name>
```

- `api_key` — an app-specific key issued by the receiving app (e.g. `pp_live_xxx` for Post-Pilot)
- `X-SRN-App` — identifies the caller (e.g. `sigil`, `shadowrealm`). Used for logging and rate-limiting.

---

## Health Response

```json
{
  "status":  "ok",
  "app":     "post-pilot",
  "version": "1.0.0",
  "uptime":  3600
}
```

---

## Manifest Response

```json
{
  "app":     "post-pilot",
  "version": "1.0.0",
  "tools": [
    {
      "name":        "publish_post",
      "description": "Publish a caption to one or more social platforms",
      "method":      "POST",
      "path":        "/v1/publish_post",
      "input": {
        "caption":      { "type": "string",  "required": true },
        "platforms":    { "type": "array",   "required": false },
        "content_type": { "type": "string",  "required": false }
      },
      "output": {
        "success": "boolean",
        "results": "object"
      }
    }
  ]
}
```

---

## Standard Response Envelope

All `/v1/*` POST routes return:

```json
{ "success": true,  "data": { ... } }
{ "success": false, "error": "Human readable message", "code": "MACHINE_CODE" }
```

HTTP status codes:
- `200` — success
- `400` — bad input
- `401` — missing or invalid auth
- `403` — valid auth but insufficient tier/permissions
- `404` — tool not found
- `500` — internal error

---

## Required `.env` Keys

Every SRN app adds these to its `.env`:

```bash
# This app's identity in the network
SRN_APP_NAME=post-pilot

# Shared inter-app secret (used to verify calls from ShadowRealm)
SRN_SECRET=srn_live_xxx

# ShadowRealm registry URL (set once ShadowRealm is deployed)
SRN_REGISTRY_URL=https://shadowrealm.railway.app
```

---

## Per-App Documentation

Each app maintains its own `V1_API.md` listing every tool it exposes —
inputs, outputs, examples, and tier requirements. The manifest endpoint
is the machine-readable version; `V1_API.md` is the human-readable version.

---

## App Registry

The canonical list of all SRN apps lives in:
[`ShadowWalkerNC/ShadowRealm`](https://github.com/ShadowWalkerNC/ShadowRealm) → `SRN_REGISTRY.json`

| App | Stack | Repo | Role |
|-----|-------|------|------|
| **post-pilot** | Python / Flask | [Post-Pilot](https://github.com/ShadowWalkerNC/Post-Pilot) | Social media posting engine |
| **sigil** | Node.js / Discord.js | [Sigil](https://github.com/ShadowWalkerNC/Sigil) | Discord bot — culinary ops + community |
| **shadowrealm** | TBD | [ShadowRealm](https://github.com/ShadowWalkerNC/ShadowRealm) | Orchestrator — manifest registry + tool dispatcher |

---

## Versioning

- Contract version lives in this file's header (`v1.0`)
- Breaking changes bump the major version and require migration notes
- Additive changes (new tools, new optional fields) are non-breaking
