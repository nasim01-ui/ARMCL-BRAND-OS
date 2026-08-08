"""skill_server.py - Self-contained HTTP dashboard for the Brand Custodian skill.

Serves a single-page dashboard tracking all skill data (sales/revenue from the
DWH, plus campaign, competitor, visibility, market-visit and KPI stores kept as
JSON under database/). Pure standard-library server; edit-friendly JSON stores.

Endpoints (GET):
  /                 -> dashboard HTML (web/index.html)
  /web/<file>       -> static assets (css, js)
  /api/overview     -> today/week/month deliveries, volume, net value
  /api/sales-by-zone    -> today's sales grouped by transport zone
  /api/sales-by-dealer  -> today's top 10 dealers
  /api/monthly-revenue  -> last 12 months revenue
  /api/budget          -> FY2026-27 monthly budget/spend/remaining
  /api/budget-total     -> FY2026-27 total approved budget for ARMCL
  /api/skill            -> brand_custodian skill markdown
  /api/<store>          -> items for store: campaigns, competitors, visibility, visits, kpis

POST:
  /api/<store>          -> upsert one record into that store
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import market_fetch

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "database"
SKILL_FILE = BASE_DIR / "skills" / "brand_custodian.md"

ARMCL_UNIT_ID = 175  # Akij Cement - Ready Mix? -> actual ARMCL unit id


def _load_env() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

DB_CONFIG = {
    "server": os.getenv("MSSQL_SERVER", "203.202.241.211"),
    "port": int(os.getenv("MSSQL_PORT", "1433")),
    "user": os.getenv("MSSQL_USER", "mcp_user"),
    "password": os.getenv("MSSQL_PASSWORD", "iAOS@35o997"),
    "database": os.getenv("MSSQL_DATABASE", "DWH"),
}

STORES = ("campaigns", "competitors", "visibility", "visits", "kpis", "market_share")


def pymssql():
    import pymssql
    return pymssql


def connect():
    return pymssql().connect(**DB_CONFIG)


# --------------------------------------------------------------------------
# DWH queries
# --------------------------------------------------------------------------
def _q(sql, params=()):
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def totals_between(start, end):
    rows = _q(
        """SELECT COUNT(*), ISNULL(SUM(numTotalDeliveryQuantity),0), ISNULL(SUM(numTotalNetValue),0)
           FROM sms.tblDeliveryHeaderArc
           WHERE intBusinessUnitId = %s AND dteDeliveryDate >= %s AND dteDeliveryDate < %s""",
        (ARMCL_UNIT_ID, start, end),
    )
    if isinstance(rows, dict):
        return rows
    r = rows[0]
    return {"deliveries": int(r[0] or 0), "volume": float(r[1] or 0), "value": float(r[2] or 0)}


def sales_by_zone(start, end):
    rows = _q(
        """SELECT ISNULL(NULLIF(strTransportZoneName,''),'(unassigned)') zone,
                  COUNT(*), SUM(numTotalDeliveryQuantity), SUM(numTotalNetValue)
           FROM sms.tblDeliveryHeaderArc
           WHERE intBusinessUnitId = %s AND dteDeliveryDate >= %s AND dteDeliveryDate < %s
           GROUP BY strTransportZoneName ORDER BY SUM(numTotalNetValue) DESC""",
        (ARMCL_UNIT_ID, start, end),
    )
    if isinstance(rows, dict):
        return rows
    return [{"zone": a, "deliveries": int(b or 0), "volume": float(c or 0), "value": float(d or 0)} for a, b, c, d in rows]


def sales_by_dealer(start, end, top=10):
    rows = _q(
        f"""SELECT TOP {int(top)} strSoldToPartnerName, COUNT(*), SUM(numTotalNetValue)
            FROM sms.tblDeliveryHeaderArc
            WHERE intBusinessUnitId = %s AND dteDeliveryDate >= %s AND dteDeliveryDate < %s
            GROUP BY strSoldToPartnerName ORDER BY SUM(numTotalNetValue) DESC""",
        (ARMCL_UNIT_ID, start, end),
    )
    if isinstance(rows, dict):
        return rows
    return [{"dealer": a, "deliver": int(b or 0), "value": float(c or 0)} for a, b, c in rows]


def monthly_revenue(months=12):
    out = []
    now = datetime.now()
    first = now.replace(day=1)
    for i in range(months - 1, -1, -1):
        base_months = (first.year * 12 + first.month - 1) - i
        y, m = divmod(base_months, 12)
        m += 1
        start = datetime(y, m, 1)
        end = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        r = totals_between(start, end)
        out.append({"month": f"{y:04d}-{m:02d}", "revenue": r.get("value", 0) if isinstance(r, dict) else 0})
    return out


def budget_rows() -> list[dict]:
    """Approved FY 2026-27 budget for the ARMCL brand (unit 175), by month."""
    rows = _q(
        """SELECT b.intMonthId, b.numAmount
           FROM bgt.tblBudgetIncomeExpenseRowArc b
           JOIN bgt.tblBudgetIncomeExpenseHeaderArc h
             ON h.intBudgetHeaderId = b.intBudgetHeaderId
           WHERE h.strFiscalYear = %s AND b.intBusinessUnitId = %s
             AND h.isActive = 1 AND h.isForecast = 0 AND b.isActive = 1""",
        ("2026-2027", ARMCL_UNIT_ID),
    )
    if isinstance(rows, dict):
        return [{"error": str(rows["error"])}]
    bucket = {}
    for m, amt in rows:
        bucket.setdefault(m, 0.0)
        bucket[m] += float(amt or 0)
    return [{"month": _month_name(m), "amount": round(v, 2)} for m, v in sorted(bucket.items())]


def _month_name(m: int) -> str:
    names = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    return names[m - 1]


# --------------------------------------------------------------------------
# JSON stores in database/
# --------------------------------------------------------------------------
def store_path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def load_store(name: str) -> list[dict]:
    p = store_path(name)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_store(name: str, items: list[dict]) -> None:
    store_path(name).write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def upsert_store(name: str, record: dict) -> list[dict]:
    items = load_store(name)
    key = record.get("id", "")
    if key:
        items = [r for r in items if str(r.get("id", "")) != str(key)]
    record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if not record.get("created_at"):
        record["created_at"] = record["updated_at"]
    items.append(record)
    save_store(name, items)
    return items


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SkillDashboard/1.0"

    # -- helpers ----------------------------------------------------------
    def _write(self, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    # -- requests ---------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        if p.startswith("/api/"):
            self._api(p)
        elif p in ("/", "/index.html"):
            self._static("index.html")
        else:
            self._static(p.lstrip("/"))

    def do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path
        if not p.startswith("/api/"):
            self._json({"ok": False, "error": "unknown route"}, status=404)
            return
        store = p[len("/api/"):].split("/")[0]
        if store not in STORES:
            self._json({"ok": False, "error": f"unknown store {store}"}, status=404)
            return
        record = self._read_json()
        items = upsert_store(store, record)
        self._json({"ok": True, "items": items})

    def _static(self, rel: str):
        rel = rel.replace("\\", "/").lstrip("/")
        if rel.startswith("web/"):
            rel = rel[len("web/"):]
        fp = (WEB_DIR / rel).resolve()
        if not fp.is_file() or WEB_DIR.resolve() not in fp.parents:
            self.send_response(404)
            self.end_headers()
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(fp.suffix, "application/octet-stream")
        self._write(fp.read_bytes(), ctype)

    def _api(self, p):
        if p == "/api/overview":
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = today.replace(day=1)
            nxt_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            self._json({
                "today": totals_between(today, today + timedelta(days=1)),
                "week": totals_between(week_start, week_start + timedelta(days=7)),
                "month": totals_between(month_start, nxt_month),
                "report_date": now.strftime("%Y-%m-%d %H:%M"),
            })
            return
        if p == "/api/sales-by-zone":
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self._json(sales_by_zone(today, today + timedelta(days=1)))
        elif p == "/api/sales-by-dealer":
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self._json(sales_by_dealer(today, today + timedelta(days=1), top=10))
        elif p == "/api/monthly-revenue":
            self._json(monthly_revenue())
        elif p == "/api/budget":
            self._json(budget_rows())
        elif p == "/api/skill":
            self._json({"skill": SKILL_FILE.read_text(encoding="utf-8") if SKILL_FILE.exists() else ""})
        elif p == "/api/campaigns":
            self._json(load_store("campaigns"))
        elif p == "/api/competitors":
            # combine competitor store
            self._json(load_store("competitors"))
        elif p == "/api/visibility":
            self._json(load_store("visibility"))
        elif p == "/api/visits":
            self._json(load_store("visits"))
        elif p == "/api/kpis":
            self._json(load_store("kpis"))
        elif p == "/api/market-share":
            items = load_store("market_share")
            total = sum(float(x.get("actual_sales_avg") or 0) for x in items)
            for x in items:
                a = float(x.get("actual_sales_avg") or 0)
                x["share_pct"] = round(a / total * 100, 1) if total else 0
            self._json({"items": items, "total_sales_lakh": round(total, 2)})
        elif p == "/api/market-trend":
            qs = dict(x.split("=", 1) for x in urlparse(self.path).query.split("&") if "=" in x)
            force = qs.get("refresh") == "1"
            self._json(market_fetch.get_market_trend(force=force))
        elif p == "/api/market_share":
            self._json(load_store("market_share"))
        else:
            self._json({"error": "unknown api"}, status=404)


STORES = {"campaigns", "competitors", "visibility", "visits", "kpis", "market_share"}


def run(port: int = 8000):
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"SKILL Dashboard  ->  http://localhost:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", "8000")))