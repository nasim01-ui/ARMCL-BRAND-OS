"""audit.py - BrandOS Audit Log (PHASE 20 hardening).

Records every privileged/management action: login, sync, decision changes,
action changes, store writes. Append-only log with actor + action + target +
before/after summary.

API:
  GET /api/audit-log    -> recent audit entries (role: md/admin)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"
MAX_ENTRIES = 500


def _read() -> list[dict]:
    p = DATA_DIR / "audit_log.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(items: list[dict]) -> None:
    (DATA_DIR / "audit_log.json").write_text(
        json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def log(actor: str, action: str, target: str = "", detail: str = "", role: str = "") -> dict:
    entry = {
        "id": f"audit-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "actor": actor or "unknown",
        "role": role or "",
        "action": action,
        "target": target,
        "detail": detail,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    items = _read()
    items.insert(0, entry)
    _write(items[:MAX_ENTRIES])
    return entry


def list_log(limit: int = 100) -> list[dict]:
    return _read()[:limit]


if __name__ == "__main__":
    print(json.dumps(list_log(20), ensure_ascii=False, indent=2))
