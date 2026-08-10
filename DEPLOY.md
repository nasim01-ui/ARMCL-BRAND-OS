# BrandOS — Deployment Guide

This doc covers production setup (Render) for the AKIJ Ready Mix BrandOS app.

## Local dev

```
cd AI_Automation/web
python server.py          # serves http://localhost:8000
```

Login password defaults to `123456` (env `BRANDOS_PASSWORD`).

## Render deployment

The repo contains `render.yaml` (Render Blueprint). Steps:

1. **Push to GitHub** (repo: `nasim01-ui/ARMCL-BRAND-OS`).
2. In Render → **New → Blueprint**, select the repo. Render reads `render.yaml`
   and creates the `armcl-brand-dashboard` web service.
3. **Set secrets** (marked `sync: false` — must be set in the Render dashboard,
   under the service → Environment):

| Env var | Value |
|---------|-------|
| `BRANDOS_PASSWORD` | The login password (any string). |
| `BRANDOS_SECRET` | A long random string (HMAC session secret). Generate: `python -c "import secrets;print(secrets.token_hex(32))"` |
| `GOOGLE_TOKEN_JSON` | The full JSON contents of `AI_Automation/database/token.json` (paste as a multiline secret). Needed for `/api/market-trend`, `/api/sales-status`, and spreadsheet sync. |

4. Confirm auto-set env vars from `render.yaml`:
   `MSSQL_SERVER`, `MSSQL_PORT`, `MSSQL_USER`, `MSSQL_PASSWORD`, `MSSQL_DATABASE`,
   `BRANDOS_COOKIE_SECURE=true` (HTTPS), `MARKET_SHEET_FILE`, `MARKET_SHEET_GID`.

5. Health check path: `/` (redirects to `/login` or `/dashboard`).

## Vercel (serverless fallback)

The `vercel/api/` folder mirrors the Flask API. Deploy with the same env vars;
note MSSQL/pymssql is **not** supported on Vercel — those endpoints return
stubs, but Google-Sheet + strategy/NBA/action engines work.

## Security notes

- `database/token.json`, `database/credentials.json`, `.env`, `AGENTS.md`
  are git-ignored and must never be committed.
- Use `BRANDOS_COOKIE_SECURE=true` in production (HTTPS).
- Rotate `BRANDOS_SECRET` and the Google OAuth token periodically.

## Role-based access

Login lets you pick a role (MD/CEO, Marketing, Finance, Sales, Operations,
Executive). Role gates which dashboard modules are shown, and only `md`/
`executive` can write (decisions, actions, sync, store edits) — others get
HTTP 403 on writes.
