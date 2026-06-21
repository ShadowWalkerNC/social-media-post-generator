# Post-Audit Manual TODO

These 3 steps were identified during the production-readiness audit (2026-06-21)
and **cannot be automated via code** — they require action in Railway and GitHub.

---

## 1. Activate PostgreSQL on Railway

- In Railway project dashboard → **+ New** → **Database → PostgreSQL**
- Railway auto-sets `DATABASE_URL` in your environment
- The app detects it automatically via `modules/db.py` and switches from SQLite
- **Why:** SQLite on Railway's ephemeral filesystem means all data is wiped on every redeploy/restart

---

## 2. Add GitHub Actions Secret

- Go to **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**
- Name: `CI_TOKEN_ENCRYPTION_KEY`
- Value: a valid Fernet key — generate one with:
  ```
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- **Why:** The CI pipeline (`.github/workflows/ci.yml`) needs this to run tests without crashing on import

---

## 3. Wire scheduler + plan guard into app.py

### Scheduler (makes scheduled posts actually publish)
Add near the bottom of `app.py`, just before `if __name__ == '__main__':`:
```python
from modules.scheduler_worker import init_scheduler
init_scheduler()
```

### Plan guard (enforce subscription tier server-side)
Add the import at the top of `app.py`:
```python
from modules.plan_guard import require_plan, check_platform_limit
```

Then decorate premium routes:
```python
@app.route('/api/push_all', methods=['POST'])
@login_required
@require_plan('starter')   # blocks free users
def api_push_all():
    ...

@app.route('/api/analytics', methods=['POST'])
@login_required
@require_plan('pro')       # blocks free + starter users
def api_analytics():
    ...

@app.route('/api/generate_weekly', methods=['POST'])
@login_required
@require_plan('starter')
def api_generate_weekly():
    ...
```

Also add platform limit check inside `api_push_all`:
```python
from modules.plan_guard import check_platform_limit

platforms = request.json.get('platforms', [])
allowed, limit = check_platform_limit(current_user.subscription_tier, platforms)
if not allowed:
    return jsonify({'success': False, 'error': f'Your plan allows up to {limit} platform(s) at once. Upgrade at /billing.'}), 403
```

---

## Status

- [ ] Railway PostgreSQL provisioned
- [ ] GitHub secret `CI_TOKEN_ENCRYPTION_KEY` added
- [ ] `init_scheduler()` wired into `app.py`
- [ ] `@require_plan` applied to all premium routes in `app.py`
