"""management.py - BrandOS Management Action Center + Decision Register (PHASE 16).

Workflow (PHASES 37-40):
  NBA recommendation -> ACCEPT/MODIFY/REJECT/DEFER/ASSIGN
  -> Corrective Action (owner, deadline, progress, result)
  -> Decision Register (decision, approver, expected vs actual outcome, lessons)

Stores:
  database/decisions.json   -> decision register
  database/actions.json     -> corrective actions

API:
  GET  /api/action-center       -> NBA buckets (ACT NOW/THIS WEEK/WATCH/OPPORTUNITIES)
  GET  /api/decisions           -> decision register
  POST /api/decisions           -> record a decision (accept/reject/defer a NBA)
  GET  /api/actions             -> corrective actions
  POST /api/actions             -> create/update a corrective action
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


def _write_store(name: str, items: list[dict]) -> None:
    (DATA_DIR / f"{name}.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def _uid(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(_read_store(prefix + 's'))}"


def list_decisions() -> list[dict]:
    return _read_store("decisions")


def add_decision(record: dict) -> list[dict]:
    items = _read_store("decisions")
    rec = {
        "id": record.get("id") or _uid("decision"),
        "decision": record.get("decision"),
        "issue": record.get("issue"),
        "recommendation_id": record.get("recommendation_id"),
        "status": record.get("status", "accepted"),  # accepted/modified/rejected/deferred
        "date": record.get("date") or datetime.now().date().isoformat(),
        "approver": record.get("approver"),
        "owner": record.get("owner"),
        "evidence": record.get("evidence"),
        "data_sources": record.get("data_sources", []),
        "budget_impact": record.get("budget_impact"),
        "expected_outcome": record.get("expected_outcome"),
        "actual_outcome": record.get("actual_outcome"),
        "follow_up": record.get("follow_up"),
        "lessons": record.get("lessons"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    items.insert(0, rec)
    _write_store("decisions", items)
    return items


def list_actions() -> list[dict]:
    return _read_store("actions")


def add_action(record: dict) -> list[dict]:
    items = _read_store("actions")
    rec = {
        "id": record.get("id") or _uid("action"),
        "action": record.get("action"),
        "recommendation_id": record.get("recommendation_id"),
        "decision_id": record.get("decision_id"),
        "owner": record.get("owner"),
        "deadline": record.get("deadline"),
        "status": record.get("status", "open"),
        "progress": record.get("progress", 0),
        "result": record.get("result"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    items.insert(0, rec)
    _write_store("actions", items)
    return items


def update_action(rec_id: str, patch: dict) -> list[dict]:
    items = _read_store("actions")
    for r in items:
        if r["id"] == rec_id:
            r.update(patch)
            r["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _write_store("actions", items)
    return items


def decision_register() -> dict:
    return {
        "decisions": list_decisions(),
        "actions": list_actions(),
        "counts": {
            "decisions": len(list_decisions()),
            "open_actions": sum(1 for a in list_actions() if str(a.get("status", "")).lower() == "open"),
            "completed_actions": sum(1 for a in list_actions() if str(a.get("status", "")).lower() in ("done", "completed")),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    print(json.dumps(decision_register(), ensure_ascii=False, indent=2))
