"""evaluate.py - BrandOS EVALUATE + ADAPT engines (PHASES 13, 14, 27, 29).

For every KPI compute where possible:
  Target, Actual, Variance, Variance %, Previous Period, Trend, Forecast,
  Status (Green/Amber/Red), Strategic Impact, Business Impact.

When a metric underperforms, run diagnosis (PHASE 28) and classify the
required intervention (PHASE 29):
  EXECUTION OPTIMIZATION | TACTICAL ADJUSTMENT | STRATEGIC ADJUSTMENT | STRATEGIC RESET

API:
  GET /api/evaluate      -> KPI table with variance + status
  GET /api/diagnosis     -> underperforming metrics with diagnosis + adapt level
"""

from __future__ import annotations

import json
import re
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


def _parse_num_field(val) -> float | None:
    """Parse '15% YoY' -> 15.0, '3.5x' -> 3.5, '78' -> 78."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group()) if m else None


def _status(target, actual) -> dict:
    """Green/Amber/Red with variance."""
    t = _parse_num_field(target)
    a = _parse_num_field(actual)
    if t is None or a is None:
        return {"status": "unknown", "variance": None, "variance_pct": None, "color": "grey"}
    variance = a - t
    variance_pct = (variance / t * 100) if t else 0
    # higher is better
    if a >= t:
        color, status = "green", "Healthy"
    elif a >= t * 0.9:
        color, status = "amber", "Attention"
    else:
        color, status = "red", "Critical"
    return {"status": status, "variance": round(variance, 2), "variance_pct": round(variance_pct, 2), "color": color}


def evaluate() -> list[dict]:
    kpis = _read_store("kpis")
    out = []
    for k in kpis:
        t = _num_parse = _parse_num_field(k.get("target"))
        a = _parse_num_field(k.get("actual"))
        st = _status(k.get("target"), k.get("actual"))
        # map existing status string if provided
        existing = str(k.get("status", "")).lower()
        if existing in ("at risk", "behind"):
            st = {"status": "Critical", "variance": st["variance"], "variance_pct": st["variance_pct"], "color": "red"}
        elif existing in ("on track", "met"):
            st = {"status": "Healthy", "variance": st["variance"], "variance_pct": st["variance_pct"], "color": "green"}
        out.append({
            "id": k.get("id"),
            "name": k.get("name"),
            "target": k.get("target"),
            "actual": k.get("actual"),
            "target_num": t,
            "actual_num": a,
            "owner": k.get("owner"),
            **st,
            "strategic_impact": "High" if t is not None else "Unknown",
        })
    return out


DIAGNOSIS_CLASSES = [
    "Brand Problem", "Campaign Execution Problem", "Commercial Problem",
    "Market Problem", "Competitive Problem", "Budget Problem",
    "Operational Problem", "Quality Problem", "Customer Problem",
    "Strategic Assumption Problem", "External Issue", "Insufficient Data",
]


def _diagnose_kpi(k: dict) -> dict:
    name = (k.get("name") or "").lower()
    color = k.get("color")
    if color == "green":
        return {"diagnosis": None, "adapt": None}
    diagnosis = "Insufficient Data"
    if "market share" in name:
        diagnosis = "Competitive Problem"
    elif "revenue" in name or "sales" in name:
        diagnosis = "Commercial Problem"
    elif "campaign" in name or "roi" in name:
        diagnosis = "Campaign Execution Problem"
    elif "brand" in name:
        diagnosis = "Brand Problem"
    elif "budget" in name:
        diagnosis = "Budget Problem"
    elif "delivery" in name or "dispatch" in name or "quality" in name:
        diagnosis = "Operational Problem"
    elif "customer" in name:
        diagnosis = "Customer Problem"
    return {
        "diagnosis": diagnosis,
        "adapt": _classify_adapt(diagnosis, color),
    }


def _classify_adapt(diagnosis: str, color: str) -> str:
    if color == "amber":
        return "EXECUTION OPTIMIZATION"
    if diagnosis == "Competitive Problem":
        return "TACTICAL ADJUSTMENT"
    if diagnosis in ("Market Problem", "Strategic Assumption Problem"):
        return "STRATEGIC ADJUSTMENT"
    if diagnosis in ("External Issue",) and color == "red":
        return "STRATEGIC RESET"
    return "TACTICAL ADJUSTMENT"


def diagnosis() -> dict:
    """Underperforming metrics with diagnosis + adaptation level."""
    kpis = evaluate()
    flagged = [k for k in kpis if k.get("color") in ("red", "amber")]
    items = []
    for k in flagged:
        d = _diagnose_kpi(k)
        items.append({**k, **d})
    return {
        "flagged": len(items),
        "total_kpis": len(kpis),
        "items": items,
        "diagnosis_classes": DIAGNOSIS_CLASSES,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    print(json.dumps({"evaluate": evaluate(), "diagnosis": diagnosis()}, ensure_ascii=False, indent=2))
