"""skill_server.py - Self-contained HTTP dashboard for the Brand Custodian skill.

Serves a single-page dashboard tracking all skill data (sales/revenue from the
DWH, plus campaign, competitor, visibility, market-visit and KPI stores kept as
JSON under database/). Pure standard-library server; edit-friendly JSON stores.

Endpoints:
  GET  /login        -> login page (redirect to /dashboard if already authed)
  GET  /dashboard    -> app shell (redirect to /login if not authed; session cookie required)
  GET  /             -> redirect to /login or /dashboard
  POST /api/login    -> {password} -> {ok,token} + Set-Cookie (HttpOnly session)
  POST /api/logout   -> clears session cookie
  GET  /api/session  -> {authenticated,user,exp} (verifies token/cookie)
  GET  /api/overview -> today/week/month deliveries, volume, net value + MTD sales vs sheet
  /api/* (other)     -> protected JSON (bearer token or session cookie)
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

import hmac
import json
import os
import secrets
import sys
import time
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

LOGIN_PASSWORD = os.getenv("BRANDOS_PASSWORD", "123456")
TOKEN_SECRET = os.getenv("BRANDOS_SECRET", "brandos-secret-change-me")
TOKEN_TTL = int(os.getenv("BRANDOS_TOKEN_TTL", "3600"))


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

STORES = ("campaigns", "competitors", "visibility", "visits", "kpis", "market_share",
          "projects", "dealers", "customers", "assets", "approvals", "tasks", "creative")


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
# Auth (stateless HMAC session token + HttpOnly session cookie)
# --------------------------------------------------------------------------
COOKIE_NAME = "brandos_session"


def _b64url(b: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    import base64

    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_token(payload: dict | None = None) -> str:
    """Issue a signed session token. Payload {exp} defaults to now+TTL."""
    p = payload or {}
    p["exp"] = int(time.time()) + TOKEN_TTL
    body = json.dumps(p, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(TOKEN_SECRET.encode(), body, "sha256").hexdigest()
    return _b64url(body) + "." + sig


def parse_token(token: str) -> dict | None:
    try:
        payload_b64, sig = token.split(".", 1)
        body = _b64url_decode(payload_b64)
        expected = hmac.new(TOKEN_SECRET.encode(), body, "sha256").hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(body)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def token_valid(token: str) -> bool:
    return parse_token(token) is not None


def _cookie_header_value(token: str, max_age: int = TOKEN_TTL) -> str:
    flag = "Secure;" if os.getenv("BRANDOS_COOKIE_SECURE", "").lower() in ("1", "true") else ""
    parts = f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Lax; Max-Age={max_age}; Path=/; {flag}".strip()
    return parts


def _clear_cookie_value() -> str:
    return f"{COOKIE_NAME}=; HttpOnly; SameSite=Lax; Max-Age=0; Path=/"


def _cookie_token_from_headers(headers) -> str | None:
    raw = headers.get("Cookie", "")
    for pair in raw.split(";"):
        k, _, v = pair.strip().partition("=")
        if k == COOKIE_NAME and v:
            return v
    return None


def authorized(self) -> bool:
    """True if request carries a valid bearer token or a valid session cookie."""
    auth = self.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return token_valid(auth[len("Bearer "):])
    tok = _cookie_token_from_headers(self.headers)
    return bool(tok) and token_valid(tok)


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------
def login_ok(body: dict) -> bool:
    return isinstance(body, dict) and str(body.get("password", "")) == LOGIN_PASSWORD


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SkillDashboard/1.0"

    # -- helpers ----------------------------------------------------------
    def _write(self, body: bytes, ctype="application/json; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._write(body, status=status)

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
            return
        # public auth pages
        if p in ("/login", "/login/"):
            if authorized(self):
                self._redirect("/dashboard")
            else:
                self._static("login.html")
            return
        if p in ("/dashboard", "/dashboard/"):
            if authorized(self):
                self._static("dashboard.html")
            else:
                self._redirect("/login")
            return
        if p in ("/", "/index.html"):
            # redirect to the right shell; never serve the combined page directly
            if authorized(self):
                self._redirect("/dashboard")
            else:
                self._redirect("/login")
            return
        self._static(p.lstrip("/"))

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

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
            ".png": "image/png",
            ".svg": "image/svg+xml",
        }.get(fp.suffix, "application/octet-stream")
        self._write(fp.read_bytes(), ctype)

    def do_POST(self):
        parsed = urlparse(self.path)
        p = parsed.path
        if not p.startswith("/api/"):
            self._json({"ok": False, "error": "unknown route"}, status=404)
            return
        if p == "/api/login":
            body = self._read_json()
            ok = isinstance(body, dict) and str(body.get("password", "")) == LOGIN_PASSWORD
            if ok:
                token = make_token()
                payload = json.dumps({"ok": True, "token": token}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Set-Cookie", _cookie_header_value(token))
                self.end_headers()
                self.wfile.write(payload)
                return
            self._json({"ok": False, "error": "invalid password"}, status=401)
            return
        if p == "/api/logout":
            payload = json.dumps({"ok": True, "message": "logged out"}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Set-Cookie", _clear_cookie_value())
            self.end_headers()
            self.wfile.write(payload)
            return
        if not authorized(self):
            self._json({"error": "unauthorized"}, status=401)
            return
        store = p[len("/api/"):].split("/")[0]
        if store not in STORES:
            self._json({"ok": False, "error": f"unknown store {store}"}, status=404)
            return
        record = self._read_json()
        items = upsert_store(store, record)
        self._json({"ok": True, "items": items})

    def _api(self, p):
        if not authorized(self):
            self._json({"error": "unauthorized"}, status=401)
            return
        if p == "/api/session":
            tok = _cookie_token_from_headers(self.headers) or self.headers.get("Authorization", "")[len("Bearer "):]
            data = parse_token(tok) or {}
            self._json({"authenticated": True, "user": "custodian", "exp": data.get("exp")})
            return
        if p == "/api/overview":
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = today.replace(day=1)
            nxt_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            sales_status = market_fetch.get_sales_status(force=False)
            self._json({
                "today": totals_between(today, today + timedelta(days=1)),
                "week": totals_between(week_start, week_start + timedelta(days=7)),
                "month": totals_between(month_start, nxt_month),
                "report_date": now.strftime("%Y-%m-%d %H:%M"),
                "mtd_sales": sales_status.get("mtd_sales"),
                "monthly_target": sales_status.get("monthly_target"),
                "achievement_pct": sales_status.get("achievement_pct"),
                "sales_status_source": sales_status.get("source"),
                "sales_status_month": sales_status.get("month"),
                "sales_status_updated_at": sales_status.get("updated_at"),
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
        elif p == "/api/sales-status":
            qs = dict(x.split("=", 1) for x in urlparse(self.path).query.split("&") if "=" in x)
            force = qs.get("refresh") == "1"
            self._json(market_fetch.get_sales_status(force=force))
        elif p == "/api/market_share":
            self._json(load_store("market_share"))
        elif p == "/api/insights":
            self._json(build_insights())
        elif p == "/api/ai":
            qs = dict(x.split("=", 1) for x in urlparse(self.path).query.split("&") if "=" in x)
            query = qs.get("q", "").lower()
            self._json(ai_reply(query))
        elif p.startswith("/api/store/"):
            name = p[len("/api/store/"):].split("/")[0]
            if name in STORES:
                self._json(load_store(name))
            else:
                self._json({"error": "unknown store"}, status=404)
        elif p == "/api/reports":
            self._json(report_payload())
        elif p[len("/api/"):] in STORES:
            self._json(load_store(p[len("/api/"):]))
        else:
            self._json({"error": "unknown api"}, status=404)


def build_insights() -> dict:
    """Rule-based AI insight summary computed from the JSON stores."""
    kpis = load_store("kpis")
    comps = load_store("competitors")
    mk = load_store("market_share")
    akij = next((x for x in mk if "akij" in (x.get("company") or "").lower()), {})
    share_pct = float(akij.get("share_pct") or akij.get("actual_sales_avg") or 0)
    threats = [c for c in comps if str(c.get("threat", "")).lower() == "high"]
    atrisk = [k for k in kpis if str(k.get("status", "")).lower() in ("at risk", "behind")]

    obs_txt = f"AKIJ ready-mix market share is at {share_pct:.1f}% of rated capacity."
    reason_txt = "Peer capacity expansion continues; see competitor watch."
    action_txt = "Prioritize dealer activation in Dhaka & Chattogram and review campaign ROI weekly."
    if threats:
        obs_txt = f"High-threat competitor activity detected ({', '.join(t.get('name') for t in threats)})."
        reason_txt = "These peers are running aggressive dealer/channel programs."
        action_txt = "Step up developer engagement and dealer signboard coverage in contested zones."
    if atrisk:
        obs_txt += f" {len(atrisk)} KPI(s) flagged as at-risk/behind."
        reason_txt += f" Focus on: {', '.join(k.get('name') for k in atrisk)}."
        action_txt = "Assign owners and review these KPIs in the weekly EC review."

    return {
        "observation": obs_txt,
        "reason": reason_txt,
        "recommended_action": action_txt,
        "share_pct": share_pct,
        "threat_count": len(threats),
        "kpis_at_risk": [k.get("name") for k in atrisk],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def ai_reply(q: str) -> dict:
    """Tiny keyword NLU assistant for the BrandOS AI box."""
    reply = {
        "reply": "I can help with revenue, sales, market share, competitors, campaigns, projects, dealers, budget and approvals. Ask me like: 'What is our market share?'",
    }
    if any(w in q for w in ("revenue", "sales", "income")):
        reply["reply"] = "Revenue & sales dashboard: Today's net value, MTD revenue, zone/dealer splits and 12-month trend. Drill into /revenue or /sales."
    elif any(w in q for w in ("market share", "market-share", "share")):
        trend = market_fetch.get_market_trend(force=False)
        ak = None
        if not trend.get("error") and trend.get("items"):
            vals = [i.get("market_share_akij") for i in trend["items"] if i.get("market_share_akij") is not None]
            ak = round(sum(vals) / len(vals), 2) if vals else None
        reply["reply"] = f"AKIJ monthwise market share averages ~{ak}% (last sync {trend.get('updated_at')}) with Shah/NDE/Crown/Bashundhara as #1-#4 peers."
    elif any(w in q for w in ("competitor", "threat", "rival")):
        comps = load_store("competitors")
        names = ", ".join(c.get("name") for c in comps) or "no competitor watch entries yet"
        reply["reply"] = f"Competitor watch: {names}. High threat items are flagged in Competitor Intelligence."
    elif any(w in q for w in ("campaign", "roi", "promotion")):
        reply["reply"] = "Campaigns: see ATL/BTL/Digital programs and ROI vs budget in Campaign Management / Marketing Budget."
    elif any(w in q for w in ("budget", "spend", "expense")):
        reply["reply"] = "Marketing Budget: annual plan, used vs remaining, and the FY 2026-27 request→approval→PO flow."
    elif any(w in q for w in ("kpi", "score", "health")):
        kpis = load_store("kpis")
        reply["reply"] = "KPI health: " + ", ".join(f"{k.get('name')}={k.get('actual') or k.get('status')}" for k in kpis)
    return reply


def report_payload() -> dict:
    """Prebuilt report descriptors for the Reports Center."""
    return {
        "reports": [
            {"name": "Daily Business Report", "format": "PDF/Excel", "desc": "Today's deliveries, volume, net value by zone & dealer."},
            {"name": "Weekly Marketing Report", "format": "PPT", "desc": "Campaign spend, reach, engagement and ROI for the week."},
            {"name": "Monthly EC Report", "format": "PPT", "desc": "Executive summary of revenue, sales, market share, brand health."},
            {"name": "Market Share Report", "format": "Excel", "desc": "Monthwise share trend vs 4 rated peers (live Google Sheet)."},
            {"name": "Competitor Report", "format": "PDF", "desc": "Capacity, price and threat monitor of the Ready-Mix field."},
            {"name": "Campaign ROI Report", "format": "Excel", "desc": "ROI by channel, campaign type and status."},
        ],
        "formats": ["PPT", "PDF", "Excel"],
    }


STORES = set(STORES)


def run(port: int = 8000):
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"SKILL Dashboard  ->  http://localhost:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else int(os.getenv("PORT", "8000")))