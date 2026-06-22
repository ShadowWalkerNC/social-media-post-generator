# Post-Pilot — Alembic Migrations

## Quick start

```bash
# Apply all pending migrations (fresh DB)
alembic upgrade head

# Already have a DB created by the old ad-hoc init_db() calls?
# Mark it as already migrated without re-running DDL:
alembic stamp head

# Roll back the last migration
alembic downgrade -1

# Generate a new migration after changing a table
alembic revision --autogenerate -m "add foo column"

# Preview the SQL without running it
alembic upgrade head --sql
```

## How it works

| File | Purpose |
|---|---|
| `alembic.ini` | Alembic config; SQLite fallback URL for local dev |
| `alembic/env.py` | Wired to `modules/db.py` — reads `DATABASE_URL` env var, handles `postgres://` → `postgresql://` rewrite, uses `render_as_batch=True` for SQLite ALTER TABLE support |
| `alembic/versions/0001_initial_schema.py` | Canonical baseline — all 6 tables with conflicts resolved |

## Adding a migration

1. Make your schema change in the relevant module (`user_manager.py`, `auth_manager.py`, etc.)
2. Run `alembic revision --autogenerate -m "describe change"`
3. Review the generated file in `alembic/versions/`
4. Run `alembic upgrade head`

## Existing databases

The old codebase used ad-hoc `CREATE TABLE IF NOT EXISTS` calls scattered across
`app.py`, `user_manager.py`, `auth_manager.py`, and `api_manager.py`. Those calls
are still present as a safety net but **Alembic is now the source of truth** for
schema changes going forward.

For any existing `postpilot.db`:
```bash
alembic stamp head
```
This writes the current revision (`0001`) into the `alembic_version` table without
touching your data.

## Conflict resolutions in 0001

| Column | Old state | Decision |
|---|---|---|
| `post_history.scheduled_at` | `INTEGER` in app.py, `TEXT` in user_manager | **INTEGER** — scheduler polls `WHERE scheduled_at <= int(time.time())` |
| `api_keys.key_value` | `TEXT` in api_manager, `key_hash` in user_manager | **key_value** — live /v1/keys/* routes use key_value; key_hash was dead code |
| `users` columns | Subset in app.py, full set in user_manager | **user_manager** column set — stripe, trial, is_admin, sub_status |
