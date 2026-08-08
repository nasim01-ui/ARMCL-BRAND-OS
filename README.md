# ARMCL Brand Custodian Dashboard

Live dashboard for the AKIJ Ready Mix brand-custodian workflow:

- **Sales & Revenue** — live from the MSSQL DWH (`sms.tblDeliveryHeaderArc`, unit 175)
- **Budget** — FY 2026-27 approved budget from the DWH (`bgt.tblBudgetIncomeExpense*`)
- **Market Share** — competitor capacity + **monthwise market-share trend** pulled live from a Google Sheet
- **Campaigns / Competitors / Visibility / Visits / KPIs** — editable JSON stores

## Run locally

```bash
pip install -r requirements.txt
python web/server.py 8000
# open http://localhost:8000
```

## Deploy to Render

1. Push this folder to a GitHub repo.
2. In Render: **New → Blueprint** and paste the repo URL (uses `render.yaml`), or
   **New → Web Service** → set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `python web/server.py`
   - Health check path: `/`
3. Add these env vars (from Render dashboard, under your service → Environment):

   | Key | Value |
   |---|---|
   | `MSSQL_SERVER` | `203.202.241.211` |
   | `MSSQL_PORT` | `1433` |
   | `MSSQL_USER` | `mcp_user` |
   | `MSSQL_PASSWORD` | your DB password |
   | `MSSQL_DATABASE` | `DWH` |
   | `GOOGLE_TOKEN_JSON` | full JSON contents of `database/token.json` (line-broken string) |
   | `MARKET_SHEET_FILE` | `1NDWiW6q1PuykQ2uuNLcMuyU_90tVSBqLARlQxiaPgss` |
   | `MARKET_SHEET_GID` | `1519626691` |

   > **Important:** allow the Render service IP in the DWH firewall, and make sure
   > `GOOGLE_TOKEN_JSON` is set, otherwise the market-trend tab shows an error.

4. Deploy. Render gives you `https://<name>.onrender.com`.

## Notes

- `database/token.json`, `database/credentials.json` and `.env` are git-ignored —
  do not commit them. Set `GOOGLE_TOKEN_JSON` as an env var instead.
- If `pymssql` fails to build on Render, add a `build.sh` that `apt-get install -y
  freetds-dev build-essential` before `pip install`.
- Store writes (POST /api/<store>) are in-memory on Render's ephemeral filesystem
  and won't survive restarts.
