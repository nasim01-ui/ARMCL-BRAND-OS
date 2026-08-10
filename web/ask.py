"""ask.py - Ask BrandOS conversational AI (PHASE 17).

Answers management questions from ACTUAL BrandOS/source data (never fake):
  * Why is market share declining?
  * How much brand budget is left? / Are we overspending?
  * Which campaigns are delayed? Which consumed the most budget?
  * Which strategic objective is most at risk?
  * Compare finance budget with brand budget.
  * Which activities are not producing results?
  * Where should we reallocate budget?
  * What should management do this week?
  * Give me the top 5 NBA recommendations.
  * Why are you recommending this action?

API:
  GET /api/ask?q=<question>   -> {"reply": "...", "source": "..."}
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


def _bdt(n):
    return f"BDT {n:,.0f}" if n is not None else "n/a"


def _fmt_budget() -> str:
    bb = _read_store("brand_budget")
    if not bb:
        return "No brand budget data synced yet."
    annual = sum(_num(b.get("annual_total")) or 0 for b in bb)
    spent = sum(_num(b.get("till_date_cost")) or 0 for b in bb)
    remaining = sum(_num(b.get("remaining_budget")) or 0 for b in bb)
    return (f"Brand budget FY 26-27: annual {_bdt(annual)}, spend {_bdt(spent)}, "
            f"remaining {_bdt(remaining)} ({round(spent/annual*100,1) if annual else 0}% utilized).")


def _fmt_market_share() -> str:
    try:
        import market_fetch
        trend = market_fetch.get_market_trend(force=False).get("items", [])
        if trend:
            latest = trend[-1]
            ak = latest.get("market_share_akij")
            ak_pct = round(ak * 100, 2) if ak and ak <= 1 else (round(ak, 2) if ak else None)
            mom = ""
            if len(trend) > 1:
                prev = trend[-2].get("market_share_akij")
                prev_pct = round(prev * 100, 2) if prev and prev <= 1 else (round(prev, 2) if prev else None)
                if ak_pct and prev_pct:
                    mom = f" (vs {prev_pct}% last month)"
            return f"AKIJ market share is {ak_pct}%{mom} as of {latest.get('month')}."
        return "Market share trend data not available."
    except Exception:
        return "Market share source not reachable."


def _fmt_nba(n: int = 5) -> str:
    try:
        import nba
        data = nba.nba(limit=n)
        recs = data.get("recommendations", [])
        if not recs:
            return "No NBA recommendations available yet."
        lines = [f"{i+1}. [{r['priority_score']}] {r['next_best_action']}" for i, r in enumerate(recs)]
        return "Top NBA recommendations:\n" + "\n".join(lines)
    except Exception:
        return "NBA engine not available."


def _fmt_campaigns() -> str:
    camps = _read_store("campaigns")
    if not camps:
        return "No campaigns in the store yet."
    lines = []
    for c in camps:
        spend = _num(c.get("spend"))
        budget = _num(c.get("budget"))
        util = round(spend / budget * 100, 1) if spend is not None and budget else 0
        lines.append(f"{c.get('name')} (spend {_bdt(spend)}, budget {_bdt(budget)}, {util}% used)")
    return "Campaigns: " + "; ".join(lines)


def _fmt_strategy_risk() -> str:
    try:
        import strategy
        health = strategy.compute_health()
        comps = health.get("components", [])
        worst = min(comps, key=lambda c: c["score"]) if comps else None
        if worst:
            return (f"Business Strategy Health is {health['health']}/100 ({health['grade']}). "
                    f"Weakest dimension: {worst['dimension']} ({worst['score']}). "
                    f"Most at-risk objective: see /api/strategy.")
        return f"Business Strategy Health is {health.get('health')}/100."
    except Exception:
        return "Strategy engine not available."


def _fmt_finance_vs_brand() -> str:
    try:
        import budget_center
        bc = budget_center.budget_center()
        fin = bc["finance"]["annual_net_sales_budget"]
        brand = bc["brand"]["annual_brand_budget"]
        pct = round(brand / fin * 100, 2) if fin else 0
        return (f"Finance net-sales budget FY26-27 = {_bdt(fin)}; Brand budget = {_bdt(brand)} "
                f"({pct}% of finance). Brand is the marketing allocation, finance is the revenue plan.")
    except Exception:
        return "Budget reconciliation not available."


def _fmt_budget_reallocate() -> str:
    bb = _read_store("brand_budget")
    if not bb:
        return "No brand budget data."
    # activities with remaining budget
    lines = []
    for b in sorted(bb, key=lambda x: _num(x.get("remaining_budget")) or 0, reverse=True):
        lines.append(f"{b.get('activity_type')}: remaining {_bdt(_num(b.get('remaining_budget')))}")
    return "Remaining budget by activity: " + "; ".join(lines)


def _fmt_management_week() -> str:
    try:
        import nba
        ac = nba.action_center()
        act = ac.get("act_now", [])
        week = ac.get("this_week", [])
        out = []
        if act:
            out.append("ACT NOW: " + "; ".join(r["next_best_action"] for r in act[:3]))
        if week:
            out.append("THIS WEEK: " + "; ".join(r["next_best_action"] for r in week[:3]))
        return "\n".join(out) or "No urgent actions this week."
    except Exception:
        return "Action center not available."


def ask(q: str) -> dict:
    ql = q.lower()
    reply = None
    source = "BrandOS data"

    if any(w in ql for w in ("nba", "next best", "recommend", "what should we do", "action")):
        reply = _fmt_nba(5)
    elif any(w in ql for w in ("compare", "finance vs brand", "reconcil", "finance budget")):
        reply = _fmt_finance_vs_brand()
    elif any(w in ql for w in ("market share", "share declining", "share down", "market share")):
        reply = _fmt_market_share()
        if "declin" in ql or "down" in ql or "why" in ql:
            reply += " Recent trend is below the 15% target - a Competitive Problem; consider campaign acceleration."
    elif any(w in ql for w in ("brand budget", "marketing budget", "budget left", "overspend", "budget spend")):
        reply = _fmt_budget()
    elif any(w in ql for w in ("campaign", "delayed", "activity")):
        reply = _fmt_campaigns()
    elif any(w in ql for w in ("reallocat", "move budget", "where should")):
        reply = _fmt_budget_reallocate()
    elif any(w in ql for w in ("strategy", "risk", "health", "objective", "at risk")):
        reply = _fmt_strategy_risk()
    elif any(w in ql for w in ("this week", "this month", "management")):
        reply = _fmt_management_week()
    elif any(w in ql for w in ("revenue", "sales", "income", "top line")):
        try:
            import server
            now = datetime.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            mtd = server.totals_between(today.replace(day=1), today)
            t = server.totals_between(today, today + timedelta(days=1))
            reply = f"Today: {t['deliveries']} deliveries, {t['volume']:,.0f} m³, {_bdt(t['value'])}. MTD: {_bdt(mtd['value'])}."
        except Exception:
            reply = "Revenue data not reachable."
    elif any(w in ql for w in ("kpi", "score", "health score")):
        kpis = _read_store("kpis")
        if kpis:
            reply = "KPIs: " + "; ".join(f"{k.get('name')}={k.get('actual')} ({k.get('status')})" for k in kpis)
        else:
            reply = "No KPI data yet."
    elif any(w in ql for w in ("hi", "hello", "help")):
        reply = ("I can answer from live BrandOS data: market share, brand budget, campaigns, "
                 "strategy health, finance vs brand budget, revenue, KPIs, NBA actions and "
                 "what to do this week. Try 'Why is market share declining?' or "
                 "'Give me the top 5 NBA recommendations.'")
    else:
        reply = ("I can answer: 'Why is market share declining?', 'How much brand budget is left?', "
                 "'Which campaigns are delayed?', 'Compare finance budget with brand budget', "
                 "'Which strategic objective is most at risk?', 'Where should we reallocate budget?', "
                 "'What should management do this week?', 'Give me the top 5 NBA recommendations.'")

    return {
        "reply": reply,
        "source": source,
        "answered_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    for q in [
        "Why is market share declining?",
        "How much brand budget is left?",
        "Which campaigns are delayed?",
        "Compare finance budget with brand budget",
        "Which strategic objective is most at risk?",
        "Give me the top 5 NBA recommendations",
        "What should management do this week?",
    ]:
        print(f"Q: {q}\nA: {ask(q)['reply']}\n")
