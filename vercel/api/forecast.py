"""forecast.py - BrandOS Forecast & Early Warning Engine (PHASE 18, 41, 42).

Forecasting (where history exists) and early-warning detection:
  * Market Share trend forecast (linear)
  * Brand Budget utilization forecast
  * MTD sales run-rate forecast vs monthly target
  * Finance budget monthly net-sales trend
  * Early warnings before a target is missed (deteriorating trajectory)

Clearly distinguishes ACTUAL / TARGET / FORECAST.

API:
  GET /api/forecast            -> forecasts across connected KPIs
  GET /api/early-warning       -> trajectories with warning flags + NBA pointer
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
        return None


def _linear_proj(values: list, steps: int = 3) -> list:
    """Simple linear regression forecast for the next N points."""
    if len(values) < 2:
        return [None] * steps
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((xs[i] - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n))
    slope = num / den if den else 0
    intercept = mean_y - slope * mean_x
    return [round(slope * (n + i) + intercept, 2) for i in range(1, steps + 1)]


def forecast() -> dict:
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "series": {}}

    # 1. Market share forecast
    try:
        import market_fetch
        trend = market_fetch.get_market_trend(force=False).get("items", [])
        if trend:
            vals = [(_num(i.get("market_share_akij")) or 0) for i in trend if i.get("market_share_akij") is not None]
            vals = [v * 100 if v <= 1 else v for v in vals]
            if len(vals) >= 2:
                fcast = _linear_proj(vals, 3)
                out["series"]["market_share_pct"] = {
                    "actual": vals,
                    "forecast_next_3": fcast,
                    "target": 15.0,
                    "latest": vals[-1],
                }
    except Exception:
        pass

    # 2. MTD sales run-rate forecast
    try:
        import market_fetch
        sa = market_fetch.get_sales_status(force=False)
        if sa.get("mtd_sales") and sa.get("monthly_target") and sa.get("days_consumed"):
            mtd = sa["mtd_sales"]
            target = sa["monthly_target"]
            days = sa["days_consumed"]
            run_rate = mtd / days if days else 0
            month_days = sa.get("days_consumed") + (sa.get("days_remaining") or 0) or 31
            projected = run_rate * month_days
            out["series"]["mtd_sales_run_rate"] = {
                "actual_mtd": mtd,
                "target": target,
                "days_consumed": days,
                "run_rate_per_day": round(run_rate, 2),
                "projected_eom": round(projected, 2),
                "projected_achievement_pct": round(projected / target * 100, 1) if target else None,
            }
    except Exception:
        pass

    # 3. Finance budget monthly net-sales trend
    fin = _read_store("finance_budget")
    if fin:
        rows = sorted(fin, key=lambda r: r.get("month", ""))
        vals = [(_num(r.get("net_sales")) or 0) for r in rows]
        if len(vals) >= 3:
            out["series"]["finance_net_sales"] = {
                "actual_months": [r.get("month") for r in rows],
                "actual": vals,
                "forecast_next_3": _linear_proj(vals, 3),
            }

    # 4. Brand budget utilization trajectory
    bb = _read_store("brand_budget")
    if bb:
        annual = sum(_num(b.get("annual_total")) or 0 for b in bb)
        spent = sum(_num(b.get("till_date_cost")) or 0 for b in bb)
        util = round(spent / annual * 100, 1) if annual else 0
        out["series"]["brand_budget_util_pct"] = {
            "actual_ytd": util,
            "target_ytd_pacing": 30.0,
            "annual_budget": annual,
            "note": "0% YTD utilization = under-execution risk, not overspend",
        }

    return out


def early_warning() -> dict:
    """Detect deteriorating trajectories BEFORE target miss."""
    warnings = []
    fc = forecast()

    # Market share below target & trending down
    ms = fc["series"].get("market_share_pct")
    if ms:
        latest = ms["latest"]
        target = ms["target"]
        fcast = ms.get("forecast_next_3", [])
        if latest < target:
            warning = {
                "kpi": "Market Share",
                "level": "warning",
                "actual": latest,
                "target": target,
                "gap_pct": round((target - latest) / target * 100, 1),
                "trend": "below target",
                "forecast": fcast[-1] if fcast else None,
                "message": f"Market share {latest}% below {target}% target.",
                "nba": "Accelerate strategically important campaigns (see NBA share-utilization).",
            }
            if fcast and fcast[-1] is not None and fcast[-1] < latest:
                warning["level"] = "critical"
                warning["message"] = f"Market share {latest}% is BELOW target and forecast declining to {fcast[-1]}%."
            warnings.append(warning)

    # MTD sales run-rate miss
    mtd = fc["series"].get("mtd_sales_run_rate")
    if mtd:
        ach = mtd.get("projected_achievement_pct")
        if ach is not None and ach < 100:
            level = "critical" if ach < 60 else "warning"
            warnings.append({
                "kpi": "MTD Sales Achievement",
                "level": level,
                "actual": mtd["actual_mtd"],
                "target": mtd["target"],
                "projected_eom": mtd["projected_eom"],
                "projected_achievement_pct": ach,
                "message": f"On current run-rate, month-end sales will hit {ach}% of target.",
                "nba": "Review sales-by-zone and assign owners to lagging zones.",
            })

    # Brand budget under-execution
    bb = fc["series"].get("brand_budget_util_pct")
    if bb and bb["actual_ytd"] < 20:
        warnings.append({
            "kpi": "Brand Budget Utilization",
            "level": "warning",
            "actual": bb["actual_ytd"],
            "target": bb["target_ytd_pacing"],
            "message": f"Brand budget only {bb['actual_ytd']}% utilized YTD - campaigns may be under-delivering.",
            "nba": "Reallocate or accelerate campaigns before requesting incremental budget.",
        })

    return {
        "warnings": warnings,
        "count": len(warnings),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "forecast": fc,
    }


if __name__ == "__main__":
    print(json.dumps(early_warning(), ensure_ascii=False, indent=2))
