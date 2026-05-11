# GitHub Actions Secrets

Every secret the CI/CD pipelines need, documented in one place.

---

## Required Secrets

| Secret Name | What It Is | Where to Get It |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for AI features | [console.anthropic.com](https://console.anthropic.com) → API Keys → Create key |
| `RAILWAY_TOKEN` | Railway deploy token | [railway.app](https://railway.app) → Account Settings → Tokens → New Token |
| `PRODUCTION_URL` | Live app base URL (no trailing slash) | Railway dashboard → your project → copy the public domain |
| `SECRET_KEY` | JWT signing key (min 32 bytes, hex) | Generate locally: `openssl rand -hex 32` |

`GITHUB_TOKEN` is **automatic** — GitHub injects it into every workflow run. Do not create it manually.

---

## How to Add Secrets to GitHub

1. Go to your repository: `https://github.com/anika0273/axiom`
2. Click **Settings** (top navigation bar)
3. In the left sidebar: **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the **Name** (exactly as shown in the table above) and **Value**
6. Click **Add secret**

Repeat for each secret in the table.

---

## Secret Details

### `ANTHROPIC_API_KEY`
- Format: `sk-ant-...`
- Used by: unit-tests job (CI) and production backend
- In CI, only the intelligence tests use it — the rest pass a placeholder

### `RAILWAY_TOKEN`
- Format: long alphanumeric string
- Used by: CD `deploy` job only
- **Scope:** give it access to your specific project, not account-wide, if Railway offers project-scoped tokens
- Rotate every 90 days

### `PRODUCTION_URL`
- Format: `https://your-app.up.railway.app` (no trailing slash)
- Used by: CD smoke tests after deploy
- Update this secret whenever Railway reassigns your domain

### `SECRET_KEY`
- Format: 64-character hex string
- Used by: backend JWT signing
- Generate: `openssl rand -hex 32`
- **Never reuse** the development value in production
- Changing this value invalidates all active JWT sessions

---

## Production Environment Gate

The CD workflow uses `environment: production`, which unlocks an optional manual-approval gate in GitHub:

1. Go to **Settings** → **Environments** → **production**
2. Enable **Required reviewers** and add yourself (or your team)
3. Every push to `main` will pause before the deploy step and wait for approval

This is optional but recommended for a production system.

---

## Secret Rotation Checklist

| Secret | Rotate Every | What Breaks If Leaked |
|---|---|---|
| `ANTHROPIC_API_KEY` | 90 days | API costs charged to your account |
| `RAILWAY_TOKEN` | 90 days | Attacker can deploy arbitrary code |
| `SECRET_KEY` | 1 year (or on breach) | All user sessions invalidated on rotation |
| `PRODUCTION_URL` | Only if domain changes | Smoke tests fail silently |
