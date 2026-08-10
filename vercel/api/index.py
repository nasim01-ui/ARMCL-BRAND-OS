"""Vercel serverless Flask app for the Brand Custodian Dashboard.

Serves the static dashboard (public/) and a JSON API equivalent to the local
server.py, minus the MSSQL live endpoints (pymssql is not deployable to
Vercel). Editable stores are read from the bundled database/ JSON files.

Routes:
  GET  /               -> public/index.html
  GET  /web/<static>   -> public assets (style.css, app.js)
  GET/POST /api/...    -> JSON API (see API_ROUTES)
"""

from __future__ import annotations

import hmac
import json
import os
import base64
import time
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, redirect

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
PUBLIC = BASE_DIR / "public"
DB = BASE_DIR / "database"
SKILL_FILE = BASE_DIR / "skills" / "brand_custodian.md"

STORES = ("campaigns", "competitors", "visibility", "visits", "kpis", "market_share")

LOGIN_PASSWORD = os.getenv("BRANDOS_PASSWORD", "123456")
TOKEN_SECRET = os.getenv("BRANDOS_SECRET", "brandos-secret-change-me")
TOKEN_TTL = int(os.getenv("BRANDOS_TOKEN_TTL", "3600"))
COOKIE_NAME = "brandos_session"

app = Flask(__name__, static_folder=None)


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_token() -> str:
    p = {"exp": int(time.time()) + TOKEN_TTL}
    body = json.dumps(p, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(TOKEN_SECRET.encode(), body, "sha256").hexdigest()
    return base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii") + "." + sig


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


def authorized() -> bool:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return parse_token(auth[len("Bearer "):]) is not None
    tok = request.cookies.get(COOKIE_NAME)
    return bool(tok) and parse_token(tok) is not None


def _cookie_val(token: str, max_age: int = TOKEN_TTL) -> str:
    return f"{COOKIE_NAME}={token}; HttpOnly; SameSite=Lax; Max-Age={max_age}; Path=/"


def _clear_cookie_val() -> str:
    return f"{COOKIE_NAME}=; HttpOnly; SameSite=Lax; Max-Age=0; Path=/"


# ---------------------------------------------------------------- stores
def store_path(name: str) -> Path:
    return BASE_DIR / "database" / f"{name}.json"


def load_store(name: str) -> list[dict]:
    p = store_path(name)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------- api
def api_overview():
    now = datetime.now()
    return {
        "today": {"deliveries": 0, "volume": 0, "value": 0},
        "week": {"deliveries": 0, "volume": 0, "value": 0},
        "month": {"deliveries": 0, "volume": 0, "value": 0},
        "report_date": now.strftime("%Y-%m-%d %H:%M"),
        "note": "live MSSQL totals not available in serverless mode",
    }


def api_monthly_revenue():
    out = []
    now = datetime.now()
    first = now.replace(day=1)
    for i in range(12):
        base = (first.year * 12 + first.month - 1) - i
        y, m = divmod(base, 12)
        m += 1
        out.append({"month": f"{y:04d}-{m:02d}", "revenue": 0})
    return out


def api_budget():
    return [{"error": "budget (MSSQL) not available in serverless mode"}]


def api_market_share():
    items = load_store("market_share")
    total = sum(float(x.get("actual_sales_avg") or 0) for x in items)
    for x in items:
        a = float(x.get("actual_sales_avg") or 0)
        x["share_pct"] = round(a / total * 100, 1) if total else 0
    return {"items": items, "total_sales_lakh": round(total, 2)}


def api_market_trend():
    import market_fetch  # sibling module in api/

    force = request.args.get("refresh") == "1"
    return market_fetch.get_market_trend(force=force)


def api_sales_status():
    import market_fetch  # sibling module in api/

    force = request.args.get("refresh") == "1"
    return market_fetch.get_sales_status(force=force)


def api_skill():
    txt = SKILL_FILE.read_text(encoding="utf-8") if SKILL_FILE.exists() else ""
    return {"skill": txt}


def api_login():
    body = request.get_json(silent=True) or {}
    if str(body.get("password", "")) == LOGIN_PASSWORD:
        token = make_token()
        resp = jsonify({"ok": True, "token": token})
        resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="Lax", max_age=TOKEN_TTL, path="/")
        return resp
    return jsonify({"ok": False, "error": "invalid password"}), 401


def api_session():
    tok = request.cookies.get(COOKIE_NAME) or ""
    if not tok:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            tok = auth[len("Bearer "):]
    data = parse_token(tok) or {}
    return jsonify({"authenticated": True, "user": "custodian", "exp": data.get("exp")})


APP_API = {
    "/api/session": api_session,
    "/api/overview": api_overview,
    "/api/monthly-revenue": api_monthly_revenue,
    "/api/budget": api_budget,
    "/api/market-share": api_market_share,
    "/api/market-trend": api_market_trend,
    "/api/sales-status": api_sales_status,
    "/api/skill": api_skill,
}


@app.before_request
def _gate_api():
    path = request.path
    if not path.startswith("/api/"):
        return None
    if path in ("/api/login", "/api/logout"):
        return None
    if not authorized():
        return jsonify({"error": "unauthorized"}), 401
    return None


@app.route("/", defaults={"path": ""})
@app.route("/index.html")
def serve_index(path=""):
    if authorized():
        return redirect("/dashboard", code=302)
    return redirect("/login", code=302)


@app.route("/dashboard")
def serve_dashboard():
    if authorized():
        return send_from_directory(PUBLIC, "dashboard.html")
    return redirect("/login", code=302)


@app.route("/login")
def serve_login():
    if authorized():
        return redirect("/dashboard", code=302)
    return send_from_directory(PUBLIC, "login.html")


@app.route("/web/<path:name>")
def serve_web(name: str):
    return send_from_directory(PUBLIC, name)


@app.route("/api/login", methods=["POST"])
def api_login_route():
    resp = api_login()
    return resp


@app.route("/api/logout", methods=["POST"])
def api_logout_route():
    resp = jsonify({"ok": True, "message": "logged out"})
    resp.set_cookie(COOKIE_NAME, "", httponly=True, samesite="Lax", max_age=0, path="/")
    return resp


@app.route("/api/<name>", methods=["GET"])
def api_get(name: str):
    route = f"/api/{name}"
    if route in APP_API:
        return jsonify(APP_API[route]())
    if name in STORES:
        return jsonify(load_store(name))
    return jsonify({"error": "unknown api"}), 404


@app.route("/api/<name>", methods=["POST"])
def api_post(name: str):
    # serverless filesystem is ephemeral -> keep best-effort stub
    if name not in STORES:
        return jsonify({"error": "unknown store"}), 404
    return jsonify({"ok": True, "items": load_store(name), "note": "writes not persisted on Vercel"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))