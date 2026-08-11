"""commercial.py - BrandOS MCP/Commercial data integration (PHASES 12, 22, 23).

Connects the READY-MIX business model using the MSSQL DWH (via MCP server config):
  BRAND & MARKET -> PROJECT DEMAND -> SALES PIPELINE -> QUOTATION -> ORDER
  -> PRODUCTION -> DISPATCH -> DELIVERY -> QUALITY -> CUSTOMER EXPERIENCE
  -> REVENUE / VOLUME / MARGIN

Reuses the DWH queries in server.py (delivery, zone, dealer, monthly revenue,
budget). Provides a commercial command-center payload.

API:
  GET /api/commercial    -> delivery totals, zone/dealer split, monthly trend,
                            project pipeline, customer book
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"


def _read_store(name: str) -> list[dict]:
    p = DATA_DIR / f"{name}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _month_name(m: int) -> str:
    names = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    return names[m - 1]


# Cache DWH-heavy payload to avoid 15 sequential queries per request
_CACHE: dict = {"payload": None, "at": 0}
_TTL = 300  # seconds


def commercial_payload() -> dict:
    import time as _time

    now = datetime.now()
    if _CACHE["payload"] and (now.timestamp() - _CACHE["at"]) < _TTL:
        return _CACHE["payload"]
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    out = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "sources": ["MSSQL DWH (MCP)", "Projects store", "Customers store", "Dealers store"],
    }

    # Delivery data via DWH (reuse server helpers if available)
    try:
        import server
        out["today"] = server.totals_between(today, today + timedelta(days=1))
        out["month_to_date"] = server.totals_between(month_start, today + timedelta(days=1))
        out["zones"] = server.sales_by_zone(today, today + timedelta(days=1))
        out["dealers_today"] = server.sales_by_dealer(today, today + timedelta(days=1), top=10)
        out["monthly_revenue"] = server.monthly_revenue(12)
        out["dwh_connected"] = isinstance(out["today"], dict) and "error" not in out["today"]
    except Exception as e:
        out["dwh_connected"] = False
        out["dwh_error"] = str(e)

    # Project pipeline (demand)
    projects = _read_store("projects")
    active = [p for p in projects if str(p.get("status", "")).lower() in ("active", "new")]
    out["project_pipeline"] = {
        "count": len(active),
        "total_value": round(sum(_num(p.get("sales_value")) or 0 for p in active), 2),
        "total_requirement_cft": round(sum(_num(p.get("requirement")) or 0 for p in active), 2),
        "items": active,
    }

    # Customers
    customers = _read_store("customers")
    out["customer_book"] = {"count": len(customers), "items": customers}

    # Dealers
    dealers = _read_store("dealers")
    out["dealer_network"] = {
        "count": len(dealers),
        "active": sum(1 for d in dealers if str(d.get("status", "")).lower() == "active"),
        "items": dealers,
    }

    _CACHE["payload"] = out
    _CACHE["at"] = now.timestamp()
    return out


if __name__ == "__main__":
    print(json.dumps(commercial_payload(), ensure_ascii=False, indent=2))
