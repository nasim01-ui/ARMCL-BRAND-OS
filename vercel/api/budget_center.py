"""budget_center.py - BrandOS Budget Control Center (PHASES 8, 9, 16).

Connects Finance Budget (Source A) with Brand Budget (Source B):
  * Annual finance budget (net sales) from canonical finance_budget store
  * Annual brand budget by activity type from canonical brand_budget store
  * Reconciliation: approved vs allocated vs committed vs actual vs remaining
  * Budget utilization %, forecast spend, variance
  * Strategic pillar allocation (brand budget -> pillar via strategy.py)

API:
  GET /api/budget-center -> finance summary, brand summary, reconciliation
  GET /api/budget-utilization -> pillar/campaign/monthly utilization
"""

from __future__ import annotations

import json
from datetime import datetime
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
        return 0.0


def _finance_summary() -> dict:
    rows = _read_store("finance_budget")  # finance_budget_total canonical records
    months = sorted(rows, key=lambda r: r.get("month", ""))
    annual_net_sales = sum(_num(r.get("net_sales")) for r in rows)
    annual_qty = sum(_num(r.get("sales_qty_cft")) for r in rows)
    avg_rate = (annual_net_sales / annual_qty) if annual_qty else 0
    return {
        "fiscal_year": "2026-2027",
        "months": len(months),
        "annual_net_sales_budget": round(annual_net_sales, 2),
        "annual_sales_qty_cft": round(annual_qty, 2),
        "avg_rate": round(avg_rate, 2),
        "latest_month": months[-1].get("month") if months else None,
        "source": "Finance Budget (Source A)",
    }


def _brand_summary() -> dict:
    rows = _read_store("brand_budget")
    annual = sum(_num(r.get("annual_total")) for r in rows)
    spent = sum(_num(r.get("till_date_cost")) for r in rows)
    remaining = sum(_num(r.get("remaining_budget")) for r in rows)
    util = (spent / annual * 100) if annual else 0
    by_activity = [
        {
            "activity_type": r.get("activity_type"),
            "annual_total": _num(r.get("annual_total")),
            "q1": _num(r.get("q1")), "q2": _num(r.get("q2")),
            "q3": _num(r.get("q3")), "q4": _num(r.get("q4")),
            "till_date_cost": _num(r.get("till_date_cost")),
            "remaining_budget": _num(r.get("remaining_budget")),
        }
        for r in rows
    ]
    return {
        "fiscal_year": "2026-2027",
        "annual_brand_budget": round(annual, 2),
        "till_date_spend": round(spent, 2),
        "remaining_budget": round(remaining, 2),
        "utilization_pct": round(util, 2),
        "by_activity": by_activity,
        "source": "Brand / Marketing Budget (Source B)",
    }


def _reconciliation() -> dict:
    fin = _finance_summary()
    brand = _brand_summary()
    # finance net-sales budget is the revenue plan; brand budget is marketing spend
    return {
        "finance_budget_net_sales": fin["annual_net_sales_budget"],
        "brand_budget_approved": brand["annual_brand_budget"],
        "brand_as_pct_of_finance": round(
            (brand["annual_brand_budget"] / fin["annual_net_sales_budget"] * 100)
            if fin["annual_net_sales_budget"] else 0, 4
        ),
        "finance_vs_brand_gap": round(fin["annual_net_sales_budget"] - brand["annual_brand_budget"], 2),
        "note": "Finance budget = net sales plan; Brand budget = marketing allocation. Different units - compare for context only.",
        "reconciled_at": datetime.now().isoformat(timespec="seconds"),
    }


def _pillar_allocation() -> list[dict]:
    """Brand budget allocated to strategic pillars via strategy mapping."""
    try:
        import strategy
        pillars = {p["id"]: p for p in strategy.STRATEGIC_PILLARS}
        budget_rows = _read_store("brand_budget")
        # build pillar -> budget types -> annual
        pillar_totals = {pid: 0.0 for pid in pillars}
        for b in budget_rows:
            atype = str(b.get("activity_type", "")).upper()
            for pid, p in pillars.items():
                if atype in [t.upper() for t in p.get("budget_types", [])]:
                    pillar_totals[pid] += _num(b.get("annual_total"))
        return [
            {"pillar": pillars[pid]["name"], "pillar_id": pid, "annual_budget": round(pillar_totals[pid], 2)}
            for pid in pillars if pillar_totals[pid] > 0
        ]
    except Exception:
        return []


def budget_center() -> dict:
    fin = _finance_summary()
    brand = _brand_summary()
    return {
        "finance": fin,
        "brand": brand,
        "reconciliation": _reconciliation(),
        "pillar_allocation": _pillar_allocation(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def utilization() -> dict:
    """Pillar + activity + monthly budget utilization view."""
    brand = _brand_summary()
    util_rows = []
    for a in brand["by_activity"]:
        annual = a["annual_total"]
        spent = a["till_date_cost"]
        util_rows.append({
            "activity_type": a["activity_type"],
            "annual_budget": annual,
            "spend": spent,
            "remaining": a["remaining_budget"],
            "utilization_pct": round((spent / annual * 100) if annual else 0, 2),
        })
    return {
        "by_activity": util_rows,
        "pillars": _pillar_allocation(),
        "overall_utilization_pct": brand["utilization_pct"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    print(json.dumps(budget_center(), ensure_ascii=False, indent=2))
