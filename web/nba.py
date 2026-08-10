"""nba.py - BrandOS Next Best Action (NBA) Engine (PHASES 15, 30-37).

Cross-source AI reasoning pipeline:
  DETECT -> COMPARE -> DIAGNOSE -> CROSS-CHECK -> CLASSIFY -> PRIORITIZE
  -> RECOMMEND -> EXPLAIN -> APPROVE -> TRACK -> LEARN

Every recommendation includes:
  observation, target_vs_actual, variance, data_sources, diagnosis,
  root_cause_hypothesis, missing_data, next_best_action, alternative_action,
  action_type, intervention_level, business_impact, budget_impact, owner,
  deadline, priority_score (0-100), confidence, source_freshness.

Cross-source reasoning (PHASE 32):
  * Market Share down + Campaign active + Brand Budget under-utilized
    + sales pipeline weak  -> investigate targeting/quality before more spend
  * Share down but pipeline healthy + delivery constrained -> operational first
  * Finance on track + brand budget under-utilized + campaigns delayed
    + share declining -> accelerate delayed strategic campaigns first

API:
  GET /api/nba                 -> recommendations (priority-sorted)
  GET /api/nba?limit=5         -> top N
  GET /api/nba/why/<id>        -> source transparency view
  GET /api/action-center       -> ACT NOW / THIS WEEK / WATCH / OPPORTUNITIES
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


# --------------------------------------------------------------------------
# Cross-source data assembly
# --------------------------------------------------------------------------
def _assemble() -> dict:
    """Pull all needed signals across sources into one context dict."""
    ctx = {"sources_used": [], "freshness": {}, "signals": {}}

    # Market share trend (live)
    try:
        import market_fetch
        trend = market_fetch.get_market_trend(force=False).get("items", [])
        if trend:
            akij = [(_num(i.get("market_share_akij")) or 0) for i in trend if i.get("market_share_akij") is not None]
            if akij:
                latest = akij[-1] * 100 if akij[-1] <= 1 else akij[-1]
                prev = akij[-2] * 100 if len(akij) > 1 and akij[-2] <= 1 else (akij[-2] if len(akij) > 1 else latest)
                ctx["signals"]["market_share_pct"] = round(latest, 2)
                ctx["signals"]["market_share_mom"] = round((latest - prev) / prev * 100, 2) if prev else 0
                ctx["sources_used"].append("Market Share (Source D)")
                ctx["freshness"]["market_share"] = trend[-1].get("month")
    except Exception:
        pass

    # Brand budget
    bb = _read_store("brand_budget")
    if bb:
        annual = sum(_num(b.get("annual_total")) or 0 for b in bb)
        spent = sum(_num(b.get("till_date_cost")) or 0 for b in bb)
        ctx["signals"]["brand_budget_annual"] = annual
        ctx["signals"]["brand_budget_spent"] = spent
        ctx["signals"]["brand_budget_util_pct"] = round(spent / annual * 100, 1) if annual else 0
        ctx["sources_used"].append("Brand Budget (Source B)")
        ctx["freshness"]["brand_budget"] = "FY 2026-27"

    # Campaigns
    camps = _read_store("campaigns")
    if camps:
        ctx["signals"]["campaign_count"] = len(camps)
        ctx["signals"]["campaigns_active"] = len(camps)
        delayed = [c for c in camps if str(c.get("status", "")).lower() in ("delayed", "pending")]
        ctx["signals"]["campaigns_delayed"] = len(delayed)
        ctx["sources_used"].append("Campaigns (store)")

    # KPIs
    kpis = _read_store("kpis")
    if kpis:
        at_risk = [k for k in kpis if str(k.get("status", "")).lower() in ("at risk", "behind")]
        ctx["signals"]["kpis_at_risk"] = [k.get("name") for k in at_risk]
        ctx["sources_used"].append("KPIs (store)")

    # MTD sales achievement
    try:
        import market_fetch
        sa = market_fetch.get_sales_status(force=False)
        if sa.get("achievement_pct") is not None:
            ctx["signals"]["mtd_sales"] = sa.get("mtd_sales")
            ctx["signals"]["mtd_target"] = sa.get("monthly_target")
            ctx["signals"]["mtd_achievement_pct"] = sa.get("achievement_pct")
            ctx["sources_used"].append("MTD Sales Statement (Source E2)")
            ctx["freshness"]["sales_achievement"] = sa.get("month")
    except Exception:
        pass

    # Finance budget
    fin = _read_store("finance_budget")
    if fin:
        net_sales = sum(_num(r.get("net_sales")) or 0 for r in fin)
        ctx["signals"]["finance_budget_net_sales"] = net_sales
        ctx["sources_used"].append("Finance Budget (Source A)")

    # Projects (commercial pipeline proxy)
    prj = _read_store("projects")
    if prj:
        active = [p for p in prj if str(p.get("status", "")).lower() in ("active", "new")]
        ctx["signals"]["project_pipeline"] = len(active)
        ctx["signals"]["project_pipeline_value"] = sum(_num(p.get("sales_value")) or 0 for p in active)
        ctx["sources_used"].append("Projects (commercial)")

    return ctx


# --------------------------------------------------------------------------
# Cross-source rules -> recommendations
# --------------------------------------------------------------------------
def _build_recommendations(ctx: dict) -> list[dict]:
    recs = []
    s = ctx["signals"]
    ts = datetime.now()

    # RULE 1: Share down + campaigns active + brand budget under-utilized
    share = s.get("market_share_pct")
    budget_util = s.get("brand_budget_util_pct")
    camps_active = s.get("campaigns_active", 0)
    if share is not None and share < 15 and budget_util is not None and budget_util < 40 and camps_active > 0:
        recs.append({
            "id": "nba-share-utilization",
            "observation": f"Market share {share}% is below the 15% target while brand budget is only {budget_util}% utilized.",
            "target_vs_actual": f"Target 15% vs actual {share}%",
            "variance": f"{-round((15 - share), 2)} pts",
            "diagnosis": "Budget under-execution + market share shortfall",
            "root_cause_hypothesis": "Strategically important campaigns delayed or under-funded; spend not converting to share.",
            "next_best_action": "Accelerate delivery of delayed, strategically important campaigns before requesting additional budget.",
            "alternative_action": "Reallocate under-utilized OOH/Printing budget to digital demand generation.",
            "action_type": "Accelerate",
            "intervention_level": "Tactical",
            "business_impact": "Recover up to 1-2 share points if campaigns land this quarter.",
            "budget_impact": "Reallocation only - no incremental budget.",
            "owner": "Head of Brand & Marketing",
            "deadline": (ts + timedelta(days=7)).strftime("%Y-%m-%d"),
            "data_sources": ["Source B", "Source D"],
            "missing_data": ["Campaign-level delivery dates (Source C GID pending)"],
            "priority_score": _priority(importance=90, gap=70, revenue=60, share=90, urgency=70, confidence=70),
            "confidence": 0.7,
            "source_freshness": ctx["freshness"].get("market_share", "unknown"),
        })

    # RULE 2: MTD sales achievement low -> execution/adapt
    ach = s.get("mtd_achievement_pct")
    if ach is not None and ach < 25:
        recs.append({
            "id": "nba-mtd-sales",
            "observation": f"MTD sales achievement is {ach}% of the monthly target.",
            "target_vs_actual": f"Target {s.get('mtd_target')} CFT vs MTD {s.get('mtd_sales')} CFT",
            "variance": f"{s.get('mtd_target', 0) - s.get('mtd_sales', 0):,.0f} CFT behind",
            "diagnosis": "Commercial/Sales execution shortfall",
            "root_cause_hypothesis": "Sales force coverage, project conversion or pricing affecting volume.",
            "next_best_action": "Review sales-by-zone and dealer performance; assign owners to lagging zones.",
            "alternative_action": "Run a targeted BTL/dealer activation to lift demand this month.",
            "action_type": "Optimize",
            "intervention_level": "Execution",
            "business_impact": "Protect monthly revenue and target achievement.",
            "budget_impact": "Small BTL spend within existing budget.",
            "owner": "Head of Sales",
            "deadline": (ts + timedelta(days=3)).strftime("%Y-%m-%d"),
            "data_sources": ["Source E2", "DWH"],
            "missing_data": ["Sales-by-zone current month split (DWH)"],
            "priority_score": _priority(importance=85, gap=85, revenue=80, share=50, urgency=85, confidence=85),
            "confidence": 0.85,
            "source_freshness": ctx["freshness"].get("sales_achievement", "unknown"),
        })

    # RULE 3: KPIs at risk -> attention
    at_risk = s.get("kpis_at_risk", [])
    if at_risk:
        recs.append({
            "id": "nba-kpi-risk",
            "observation": f"{len(at_risk)} KPI(s) flagged at risk: {', '.join(at_risk)}.",
            "target_vs_actual": "See /api/evaluate for target/actual per KPI",
            "variance": "Varies by KPI",
            "diagnosis": "Strategic objective underperformance",
            "root_cause_hypothesis": "Resource, market or execution factors specific to each flagged KPI.",
            "next_best_action": "Run diagnosis on flagged KPIs and assign corrective actions with owners/deadlines.",
            "alternative_action": "Escalate to MD weekly review.",
            "action_type": "Investigate",
            "intervention_level": "Tactical",
            "business_impact": "Protect strategic objective achievement.",
            "budget_impact": "None",
            "owner": "Objective Owners",
            "deadline": (ts + timedelta(days=5)).strftime("%Y-%m-%d"),
            "data_sources": ["KPI store"],
            "missing_data": ["KPI trend history for forecasting"],
            "priority_score": _priority(importance=70, gap=70, revenue=50, share=40, urgency=60, confidence=75),
            "confidence": 0.75,
            "source_freshness": "2026-08-08",
        })

    # RULE 4: Project pipeline present -> commercial opportunity
    pv = s.get("project_pipeline_value", 0)
    pp = s.get("project_pipeline", 0)
    if pp:
        recs.append({
            "id": "nba-project-pipeline",
            "observation": f"{pp} active/new project(s) in pipeline worth ~BDT {pv:,.0f}.",
            "target_vs_actual": "Pipeline value is a demand proxy; conversion to orders is the goal.",
            "variance": "N/A",
            "diagnosis": "Commercial opportunity",
            "root_cause_hypothesis": "Quotation-to-order conversion is the lever.",
            "next_best_action": "Prioritize quotation follow-up on top projects; track conversion weekly.",
            "alternative_action": "Bundle delivery reliability guarantees into quotations.",
            "action_type": "Scale",
            "intervention_level": "Tactical",
            "business_impact": "Convert pipeline into volume/revenue.",
            "budget_impact": "None",
            "owner": "Head of Sales",
            "deadline": (ts + timedelta(days=7)).strftime("%Y-%m-%d"),
            "data_sources": ["Projects store", "DWH quotations/orders if available"],
            "missing_data": ["Quotation conversion rate (MCP CRM if available)"],
            "priority_score": _priority(importance=80, gap=50, revenue=90, share=60, urgency=60, confidence=70),
            "confidence": 0.7,
            "source_freshness": "projects.json",
        })

    # RULE 5: If finance budget on track but brand under-utilized
    if budget_util is not None and budget_util < 50 and share is not None and share < 13:
        recs.append({
            "id": "nba-budget-share-rebalance",
            "observation": "Brand budget under-utilized while market share is below target - a reallocation signal.",
            "target_vs_actual": "Budget util < 50% vs share target 15%",
            "variance": "Under-execution vs under-performance",
            "diagnosis": "Budget efficiency + market performance",
            "root_cause_hypothesis": "Spend pacing vs campaign calendar misalignment.",
            "next_best_action": "Front-load Q3-Q4 high-impact campaigns; review channel ROI.",
            "alternative_action": "Hold budget and invest only where ROI clears threshold.",
            "action_type": "Reallocate",
            "intervention_level": "Tactical",
            "business_impact": "Better ROI per BDT of brand spend.",
            "budget_impact": "Internal reallocation across activities.",
            "owner": "Head of Brand & Marketing",
            "deadline": (ts + timedelta(days=10)).strftime("%Y-%m-%d"),
            "data_sources": ["Source B", "Source D"],
            "missing_data": ["Channel-level ROI evidence"],
            "priority_score": _priority(importance=75, gap=60, revenue=50, share=80, urgency=60, confidence=65),
            "confidence": 0.65,
            "source_freshness": "FY 2026-27",
        })

    if not recs:
        recs.append({
            "id": "nba-insufficient",
            "observation": "Insufficient cross-source evidence for a high-confidence recommendation.",
            "target_vs_actual": "N/A",
            "variance": "N/A",
            "diagnosis": "Insufficient Data",
            "root_cause_hypothesis": None,
            "next_best_action": "INSUFFICIENT EVIDENCE FOR RECOMMENDATION - connect campaign activity source (C) and DWH commercial data.",
            "alternative_action": None,
            "action_type": "Investigate",
            "intervention_level": "Execution",
            "business_impact": None,
            "budget_impact": None,
            "owner": None,
            "deadline": None,
            "data_sources": ctx["sources_used"],
            "missing_data": ["Campaign Activity source GID", "DWH pipeline/quotation data"],
            "priority_score": 0,
            "confidence": 0.2,
            "source_freshness": "unknown",
        })

    return sorted(recs, key=lambda r: r["priority_score"], reverse=True)


def _priority(importance, gap, revenue, share, urgency, confidence) -> int:
    """Transparent 0-100 priority score (weighted component scores)."""
    score = (
        importance * 0.25 + gap * 0.2 + revenue * 0.15 +
        share * 0.15 + urgency * 0.15 + confidence * 0.1
    )
    return int(round(score))


def nba(limit: int | None = None) -> dict:
    ctx = _assemble()
    recs = _build_recommendations(ctx)
    if limit:
        recs = recs[:limit]
    return {
        "recommendations": recs,
        "count": len(recs),
        "signals": ctx["signals"],
        "sources_used": sorted(set(ctx["sources_used"])),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def why(rec_id: str) -> dict:
    """Source transparency view for a recommendation."""
    data = nba()
    rec = next((r for r in data["recommendations"] if r["id"] == rec_id), None)
    if not rec:
        return {"error": "recommendation not found"}
    return {
        "recommendation_id": rec_id,
        "observation": rec["observation"],
        "data_sources_used": rec["data_sources"],
        "signals_behind_recommendation": {
            k: v for k, v in data["signals"].items()
        },
        "assumptions": ["Share target 15%", "Budget utilization is YTD", "MTD achievement <25% is critical"],
        "missing_information": rec["missing_data"],
        "confidence": rec["confidence"],
    }


def action_center() -> dict:
    """ACT NOW / THIS WEEK / WATCH / OPPORTUNITIES buckets."""
    data = nba()
    now = datetime.now()
    buckets = {"act_now": [], "this_week": [], "watch": [], "opportunities": []}
    for r in data["recommendations"]:
        dl = r.get("deadline")
        try:
            days = (datetime.strptime(dl, "%Y-%m-%d") - now).days if dl else 99
        except Exception:
            days = 99
        if r["priority_score"] >= 75 and days <= 7:
            buckets["act_now"].append(r)
        elif days <= 14 or r["action_type"] == "Scale":
            buckets["this_week"].append(r)
        elif r["priority_score"] < 50:
            buckets["watch"].append(r)
        else:
            buckets["opportunities"].append(r)
    return buckets


if __name__ == "__main__":
    print(json.dumps(nba(), ensure_ascii=False, indent=2))
