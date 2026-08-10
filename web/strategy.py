"""strategy.py - BrandOS Strategy Relationships (PHASE 7).

Builds the management cascade:
  CORPORATE OBJECTIVE -> BUSINESS OBJECTIVE -> STRATEGIC PILLAR
    -> BRAND / COMMERCIAL OBJECTIVE -> BRAND PLAN -> INITIATIVE
    -> CAMPAIGN / PROGRAM -> ACTIVITY -> BUDGET -> KPI
    -> TARGET -> ACTUAL -> VARIANCE -> DIAGNOSIS -> NBA
    -> DECISION -> ACTION -> OUTCOME

Connects the canonical entities (finance_budget, brand_budget, campaign,
activity, market_share, sales_achievement, kpi, projects) into a drillable
strategy map and computes a BUSINESS STRATEGY HEALTH score using only
dimensions that have real data.

Stores written to database/:
  strategic_pillars.json
  strategic_objectives.json
  brand_plan.json
  initiatives.json
  strategy_links.json      (node -> [children]) relationships
  strategy_health.json     (cached health computation)

API (in server.py):
  GET /api/strategy        -> pillars, objectives, initiatives, cascade links
  GET /api/strategy-health -> Business Strategy Health XX/100 + components
  GET /api/strategy-map    -> full drill-down cascade tree
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import canonical
import sync_sheets

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


def _write_store(name: str, items) -> None:
    DATA_DIR / f"{name}.json".replace(name, name).replace("None", "")
    (DATA_DIR / f"{name}.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Strategic Pillars (mapped from brand budget activity types + ready-mix context)
# --------------------------------------------------------------------------
STRATEGIC_PILLARS = [
    {"id": "pillar-brand", "name": "Brand Leadership", "weight": 25,
     "objective": "Build AKIJ Ready Mix as the preferred premium brand in ready-mix",
     "budget_types": ["ATL", "BTL", "OOH", "Gifts & Printing"]},
    {"id": "pillar-demand", "name": "Demand Generation & Digital", "weight": 25,
     "objective": "Drive qualified project demand through digital and channel programs",
     "budget_types": ["Digital"]},
    {"id": "pillar-commercial", "name": "Commercial & Dealer Network", "weight": 20,
     "objective": "Expand dealer network and convert project pipeline to orders",
     "budget_types": ["BTL"]},
    {"id": "pillar-market", "name": "Market Share Growth", "weight": 20,
     "objective": "Grow ready-mix market share and outperform key competitors",
     "budget_types": ["ATL", "OOH"]},
    {"id": "pillar-operations", "name": "Operational Excellence & Delivery", "weight": 10,
     "objective": "Ensure reliable dispatch, delivery and quality to protect brand promise",
     "budget_types": []},
]


# --------------------------------------------------------------------------
# Strategic Objectives (FY 2026-27) - linked to real synced data
# --------------------------------------------------------------------------
STRATEGIC_OBJECTIVES = [
    {
        "id": "so-market-share",
        "objective": "Grow AKIJ Ready Mix market share to 15% by June 2027",
        "business_rationale": "Competitive ready-mix market; AKIJ currently ~13-15% share vs Shah/Crown/NDE",
        "strategic_pillar": "pillar-market",
        "owner": "Managing Director",
        "weight": 30,
        "period": "2026-2027",
        "kpi": "Market Share",
        "initiative": "init-share-growth",
        "budget": "brand_budget:2026-2027:ATL",
        "linked_source": "market_share",
        "health": None,  # computed
    },
    {
        "id": "so-revenue",
        "objective": "Deliver FY 2026-27 net sales of BDT 4.5B at 20%+ EBITDA",
        "business_rationale": "Finance budget FY26-27 projects rising volume/rate and improved margin",
        "strategic_pillar": "pillar-commercial",
        "owner": "CFO",
        "weight": 30,
        "period": "2026-2027",
        "kpi": "Revenue Growth",
        "initiative": "init-commercial",
        "budget": "finance_budget:2026-2027",
        "linked_source": "finance_budget",
        "health": None,
    },
    {
        "id": "so-brand",
        "objective": "Build brand preference through integrated ATL/BTL/digital presence",
        "business_rationale": "Brand budget BDT 25.9M across ATL/Digital/BTL/OOH/Printing in FY26-27",
        "strategic_pillar": "pillar-brand",
        "owner": "Head of Brand & Marketing",
        "weight": 20,
        "period": "2026-2027",
        "kpi": "Brand Health Score",
        "initiative": "init-brand-campaigns",
        "budget": "brand_budget:2026-2027",
        "linked_source": "brand_budget",
        "health": None,
    },
    {
        "id": "so-mtd-sales",
        "objective": "Achieve monthly sales targets (Aug-26 target 1.34M CFT)",
        "business_rationale": "MTD sales statement reconciles sales vs target at employee/project level",
        "strategic_pillar": "pillar-commercial",
        "owner": "Head of Sales",
        "weight": 20,
        "period": "2026-08",
        "kpi": "Sales Target Achievement",
        "initiative": "init-sales-execution",
        "budget": None,
        "linked_source": "sales_achievement",
        "health": None,
    },
]


# --------------------------------------------------------------------------
# Brand Plan FY 2026-27
# --------------------------------------------------------------------------
BRAND_PLAN = {
    "id": "brand-plan-2026-27",
    "fiscal_year": "2026-2027",
    "situation_analysis": "AKIJ Ready Mix competes with Shah, Crown, NDE, Basundhara in a growing ready-mix market",
    "business_challenge": "Grow share and revenue while building premium brand preference",
    "market_challenge": "Aggressive competitor expansion and price-based competition",
    "strategic_objectives": ["so-market-share", "so-revenue", "so-brand", "so-mtd-sales"],
    "brand_objective": "Be the most trusted ready-mix concrete brand for developers, contractors and dealers",
    "target_customer": "Developers, contractors, project consultants, dealers",
    "positioning": "Premium quality, reliable supply, on-time delivery",
    "value_proposition": "Consistent quality + dependable dispatch = zero project downtime",
    "strategic_pillars": ["pillar-brand", "pillar-demand", "pillar-commercial", "pillar-market", "pillar-operations"],
    "initiatives": ["init-share-growth", "init-commercial", "init-brand-campaigns", "init-sales-execution", "init-dealer-network"],
    "budget": 25907508.0,  # brand budget FY total from Source B
    "approval_status": "approved",
    "owner": "Head of Brand & Marketing",
}


# --------------------------------------------------------------------------
# Initiatives
# --------------------------------------------------------------------------
INITIATIVES = [
    {"id": "init-share-growth", "name": "Market Share Growth Program", "objective_id": "so-market-share",
     "description": "Win share through targeted ATL/OOH and competitor response", "owner": "Brand Team",
     "campaigns": ["cmp-billboard-atl"], "kpis": ["Market Share"]},
    {"id": "init-commercial", "name": "Commercial Conversion Engine", "objective_id": "so-revenue",
     "description": "Convert project pipeline into orders and grow volume/revenue", "owner": "Sales",
     "campaigns": [], "kpis": ["Revenue Growth"]},
    {"id": "init-brand-campaigns", "name": "Integrated Brand Campaigns", "objective_id": "so-brand",
     "description": "ATL + Digital + BTL campaign execution within brand budget", "owner": "Marketing Ops",
     "campaigns": ["cmp-social-launch", "cmp-email-spring"], "kpis": ["Brand Health Score", "Campaign ROI"]},
    {"id": "init-sales-execution", "name": "Sales Target Execution", "objective_id": "so-mtd-sales",
     "description": "Hit monthly sales targets across sales force and projects", "owner": "Head of Sales",
     "campaigns": [], "kpis": ["Sales Target Achievement"]},
    {"id": "init-dealer-network", "name": "Dealer Network Expansion", "objective_id": "so-revenue",
     "description": "Expand and activate dealer network in Dhaka & Chattogram", "owner": "Commercial",
     "campaigns": [], "kpis": ["Revenue Growth"]},
]


# --------------------------------------------------------------------------
# Cascade / link helpers
# --------------------------------------------------------------------------
def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build_links() -> dict:
    """Compute the drillable cascade tree using real stores."""
    objectives = _read_store("strategic_objectives") or STRATEGIC_OBJECTIVES
    pillars = _read_store("strategic_pillars") or STRATEGIC_PILLARS
    initiatives = _read_store("initiatives") or INITIATIVES
    campaigns = _read_store("campaigns")
    kpis = _read_store("kpis")
    projects = _read_store("projects")

    # link pillars -> objectives
    pillar_links = {p["id"]: [] for p in pillars}
    for o in objectives:
        pillar_links.setdefault(o.get("strategic_pillar"), []).append(o["id"])

    # link objectives -> initiatives
    obj_init = {o["id"]: [] for o in objectives}
    for i in initiatives:
        obj_init.setdefault(i.get("objective_id"), []).append(i["id"])

    # link initiatives -> campaigns (by kpi name / description match or explicit)
    init_camp = {i["id"]: [] for i in initiatives}
    for i in initiatives:
        for c in campaigns:
            ctype = str(c.get("type", "")).upper()
            cid = c.get("id")
            if cid in (i.get("campaigns") or []):
                init_camp[i["id"]].append(cid)

    # link campaigns -> budget (brand budget by activity type)
    budget_map = {}
    for b in _read_store("brand_budget"):
        budget_map[str(b.get("activity_type", "")).upper()] = b["id"]
    campaign_budget = {}
    for c in campaigns:
        ctype = str(c.get("type", "")).upper()
        if ctype in budget_map:
            campaign_budget[c["id"]] = budget_map[ctype]

    # link objectives -> kpis
    obj_kpi = {o["id"]: [] for o in objectives}
    for k in kpis:
        name = str(k.get("name", "")).lower()
        for o in objectives:
            kpi_name = str(o.get("kpi", "")).lower()
            if kpi_name in name or name in kpi_name:
                obj_kpi.setdefault(o["id"], []).append(k["id"])

    # link objectives -> projects (commercial)
    obj_projects = {o["id"]: [] for o in objectives}
    for prj in projects:
        # link revenue objective to active projects
        if str(prj.get("status", "")).lower() in ("active", "new"):
            obj_projects.setdefault("so-revenue", []).append(prj["id"])

    return {
        "pillars": pillar_links,
        "objective_initiatives": obj_init,
        "initiative_campaigns": init_camp,
        "campaign_budget": campaign_budget,
        "objective_kpis": obj_kpi,
        "objective_projects": obj_projects,
    }


def _kpi_status(k) -> str:
    st = str(k.get("status", "")).lower()
    if st in ("at risk", "behind"):
        return "critical"
    if st in ("on track", "met"):
        return "healthy"
    if st in ("pending", "review"):
        return "attention"
    return "unknown"


# --------------------------------------------------------------------------
# Business Strategy Health Score
# --------------------------------------------------------------------------
def compute_health() -> dict:
    """Weighted health score using only dimensions with valid data."""
    components = []

    # 1. KPI health
    kpis = _read_store("kpis")
    if kpis:
        total = 0.0
        for k in kpis:
            status = _kpi_status(k)
            total += {"healthy": 100, "attention": 60, "critical": 30, "unknown": 50}[status]
        avg = round(total / len(kpis), 1)
        components.append({"dimension": "Strategic KPI Achievement", "score": avg,
                           "data": [k.get("name") for k in kpis], "weight": 25})

    # 2. Market share performance (trend from live market share sheet)
    ms_trend = None
    try:
        import market_fetch
        ms_trend = market_fetch.get_market_trend(force=False).get("items")
    except Exception:
        ms_trend = None
    if ms_trend:
        akij_vals = [(_num(i.get("market_share_akij")) or _num(i.get("akij")) or 0) for i in ms_trend]
        akij_vals = [v for v in akij_vals if v is not None]
        if akij_vals:
            latest = akij_vals[-1]
            prev = akij_vals[-2] if len(akij_vals) > 1 else latest
            growth = (latest - prev) / prev * 100 if prev else 0
            # share in % (market_share_akij is a fraction e.g. 0.134); scale
            if latest <= 1:
                latest_pct = latest * 100
            else:
                latest_pct = latest
            score = round(min(100, max(0, latest_pct * 5)), 1)  # 20% -> 100
            components.append({"dimension": "Market Share Performance",
                               "score": score, "latest_share_pct": round(latest_pct, 2),
                               "mo_m_change_pct": round(growth, 2), "weight": 20})

    # 3. Brand budget utilization (approved vs remaining)
    bb = _read_store("brand_budget")
    if bb:
        total_budget = sum(_num(b.get("annual_total")) or 0 for b in bb)
        spent = sum(_num(b.get("till_date_cost")) or 0 for b in bb)
        remaining = sum(_num(b.get("remaining_budget")) or 0 for b in bb)
        util = (spent / total_budget * 100) if total_budget else 0
        # low utilization early in FY = healthy (not over-spent)
        score = round(100 - abs(util - 30) * 2, 1)  # target ~30% YTD utilization
        components.append({"dimension": "Brand Budget Efficiency", "score": max(0, min(100, score)),
                           "budget": total_budget, "spend": spent, "remaining": remaining,
                           "utilization_pct": round(util, 1), "weight": 20})

    # 4. Sales target achievement (MTD)
    sa = _read_store("sales_achievement")
    if sa:
        ach = _num(sa[-1].get("achievement_pct")) if sa else None
        if ach is not None:
            score = round(min(100, ach * 1.0), 1)  # direct pct
            components.append({"dimension": "Sales Target Achievement", "score": score,
                               "achievement_pct": ach, "weight": 20})

    # 5. Campaign execution (any campaign with budget/spend counts as executing)
    camps = _read_store("campaigns")
    if camps:
        executed = [c for c in camps if (_num(c.get("spend")) is not None or _num(c.get("budget")) is not None)]
        ratio = len(executed) / len(camps) if camps else 0
        components.append({"dimension": "Campaign Execution", "score": round(ratio * 100, 1),
                           "executed": len(executed), "total": len(camps), "weight": 15})

    # weighted score
    if not components:
        return {"health": None, "components": [], "note": "insufficient data"}
    weighted = sum(c["score"] * c["weight"] for c in components) / sum(c["weight"] for c in components)
    return {
        "health": round(weighted, 1),
        "grade": "Healthy" if weighted >= 70 else ("Attention" if weighted >= 50 else "Critical"),
        "components": components,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "dimensions_with_data": len(components),
    }


# --------------------------------------------------------------------------
# Persist + API payloads
# --------------------------------------------------------------------------
def _persist_strategy_stores() -> None:
    _write_store("strategic_pillars", STRATEGIC_PILLARS)
    _write_store("strategic_objectives", STRATEGIC_OBJECTIVES)
    _write_store("brand_plan", BRAND_PLAN)
    _write_store("initiatives", INITIATIVES)
    health = compute_health()
    _write_store("strategy_health", health)


def strategy_payload() -> dict:
    objectives = _read_store("strategic_objectives") or STRATEGIC_OBJECTIVES
    pillars = _read_store("strategic_pillars") or STRATEGIC_PILLARS
    initiatives = _read_store("initiatives") or INITIATIVES
    return {
        "pillars": pillars,
        "objectives": objectives,
        "initiatives": initiatives,
        "brand_plan": _read_store("brand_plan") or BRAND_PLAN,
        "links": build_links(),
        "health": _read_store("strategy_health") or compute_health(),
        "sources": {
            "campaigns": len(_read_store("campaigns")),
            "kpis": len(_read_store("kpis")),
            "projects": len(_read_store("projects")),
            "brand_budget": len(_read_store("brand_budget")),
            "finance_budget": len(_read_store("finance_budget")),
            "market_share": len(_read_store("market_share")),
        },
    }


def strategy_map() -> dict:
    """Full drill-down cascade tree."""
    payload = strategy_payload()
    links = payload["links"]
    campaigns = {c["id"]: c for c in _read_store("campaigns")}
    kpis = {k["id"]: k for k in _read_store("kpis")}
    projects = {p["id"]: p for p in _read_store("projects")}

    tree = []
    for pillar in payload["pillars"]:
        pnode = {"id": pillar["id"], "name": pillar["name"], "type": "pillar", "children": []}
        for oid in links["pillars"].get(pillar["id"], []):
            obj = next((o for o in payload["objectives"] if o["id"] == oid), None)
            if not obj:
                continue
            onode = {"id": obj["id"], "name": obj["objective"], "type": "objective",
                     "kpi": obj.get("kpi"), "budget": obj.get("budget"), "children": []}
            for iid in links["objective_initiatives"].get(obj["id"], []):
                ini = next((i for i in payload["initiatives"] if i["id"] == iid), None)
                if not ini:
                    continue
                inode = {"id": ini["id"], "name": ini["name"], "type": "initiative",
                         "owner": ini.get("owner"), "children": []}
                for cid in links["initiative_campaigns"].get(ini["id"], []):
                    camp = campaigns.get(cid)
                    if not camp:
                        continue
                    cnode = {"id": camp["id"], "name": camp["name"], "type": "campaign",
                             "budget": links["campaign_budget"].get(cid), "status": camp.get("status"),
                             "spend": camp.get("spend"), "children": []}
                    inode["children"].append(cnode)
                for kid in links["objective_kpis"].get(obj["id"], []):
                    k = kpis.get(kid)
                    if k:
                        inode["children"].append({"id": k["id"], "name": k["name"], "type": "kpi",
                                                  "target": k.get("target"), "actual": k.get("actual"),
                                                  "status": _kpi_status(k)})
                onode["children"].append(inode)
            pnode["children"].append(onode)
        tree.append(pnode)
    return {"tree": tree, "health": payload["health"]}


def seed() -> dict:
    _persist_strategy_stores()
    return strategy_payload()


if __name__ == "__main__":
    print(json.dumps(seed(), ensure_ascii=False, indent=2))
