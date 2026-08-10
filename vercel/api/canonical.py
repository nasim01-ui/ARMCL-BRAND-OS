"""canonical.py - BrandOS canonical data model, source mappings, validation.

PHASE 5 of the BrandOS master prompt:
  * Canonical entities (extend, do not recreate the existing JSON stores).
  * Source-field -> canonical-field mapping configuration.
  * Validation rules per entity (schema change protection).
  * Lineage metadata helpers (source_type, source_file_id, source_gid, ...).

Sources (see data_source_registry.md):
  A  Finance Budget        Google Sheets  1RCrI84M2w9xSgt9Unl7LInA4RzkKxvU6 / 583178831
  B  Brand Budget          Google Sheets  1GamxQqXTXavG1rtPpaV9xkVyrqgZbCRg2PHjosXG7yU / 250903347
  C  Campaign Activity     Google Sheets  1_Ayxtcz-LJd6M9HLUs5GWM351HM-yDpa / 1629490999
  D  Market Share          Google Sheets  1NDWiW6q1PuykQ2uuNLcMuyU_90tVSBqLARlQxiaPgss / 1519626691
  E  MSSQL DWH             MCP (mssql-test-server) -> DWH
  E2 MTD Sales Statement   Google Sheets  1vPlcijsZkj4p6ZHmzg7jEAutNrW5l2YKlbNUtgXkNbI / 990537426
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"

# --------------------------------------------------------------------------
# Data Source Registry
# --------------------------------------------------------------------------
DATA_SOURCES = {
    "finance_budget": {
        "id": "src_finance_budget",
        "name": "Finance Budget",
        "source_type": "google_sheets",
        "file_id": "1RCrI84M2w9xSgt9Unl7LInA4RzkKxvU6",
        "gid": "583178831",
        "sheet": "Working By CFC month to Month",
        "domain": "finance_budget",
        "grain": "monthly_pnl",
        "owner": "Finance",
        "mapping_status": "defined",
    },
    "brand_budget": {
        "id": "src_brand_budget",
        "name": "Brand / Marketing Budget",
        "source_type": "google_sheets",
        "file_id": "1GamxQqXTXavG1rtPpaV9xkVyrqgZbCRg2PHjosXG7yU",
        "gid": "250903347",
        "sheet": "Budget Summary",
        "domain": "brand_budget",
        "grain": "quarterly_by_activity",
        "owner": "Marketing",
        "mapping_status": "defined",
    },
    "campaign_activity": {
        "id": "src_campaign_activity",
        "name": "Campaign / Brand Activity / Execution",
        "source_type": "google_sheets",
        "file_id": "1_Ayxtcz-LJd6M9HLUs5GWM351HM-yDpa",
        "gid": "1629490999",
        "sheet": "Guideline (template only)",
        "domain": "campaign_activity",
        "grain": "activity",
        "owner": "Marketing",
        "mapping_status": "template_only",  # actual data GID needs confirmation
    },
    "market_share": {
        "id": "src_market_share",
        "name": "Market Share",
        "source_type": "google_sheets",
        "file_id": "1NDWiW6q1PuykQ2uuNLcMuyU_90tVSBqLARlQxiaPgss",
        "gid": "1519626691",
        "sheet": "Market Share",
        "domain": "market_share",
        "grain": "monthly_competitor",
        "owner": "Marketing",
        "mapping_status": "integrated",
    },
    "mtd_sales_statement": {
        "id": "src_mtd_sales_statement",
        "name": "MTD Sales Statement (ARMCL-Aug26)",
        "source_type": "google_sheets",
        "file_id": "1vPlcijsZkj4p6ZHmzg7jEAutNrW5l2YKlbNUtgXkNbI",
        "gid": "990537426",
        "sheet": "ARMCL-Aug26",
        "domain": "sales_achievement",
        "grain": "monthly_summary",
        "owner": "Sales",
        "mapping_status": "integrated",
    },
    "mssql_dwh": {
        "id": "src_mssql_dwh",
        "name": "MSSQL DWH (MCP)",
        "source_type": "mcp",
        "mcp_server": "mssql-test-server",
        "server": "203.202.241.211",
        "database": "DWH",
        "domain": "delivery_sales_budget_target",
        "grain": "transaction/monthly",
        "owner": "IT / DWH",
        "mapping_status": "connected",
        "tables": [
            "sms.tblDeliveryHeaderArc",
            "bgt.tblBudgetIncomeExpenseHeaderArc",
            "bgt.tblBudgetIncomeExpenseRowArc",
            "oms.tblCustomerSalesTargetHeaderArc",
            "mes.tblDetailSalesPlanHeaderArc",
            "mes.tblDetailSalesPlanRowArc",
            "fin.tblExpenseRegisterHeaderArc",
            "fin.tblExpenseRegisterRowArc",
        ],
    },
}

# --------------------------------------------------------------------------
# Canonical Entities (schema: entity -> ordered fields with type + required)
# --------------------------------------------------------------------------
# type in {str, num, date, int, bool, list, obj}; null allowed unless required
CANONICAL_ENTITIES = {
    "strategic_objective": {
        "fields": {
            "id": {"type": "str", "required": True},
            "objective": {"type": "str", "required": True},
            "business_rationale": {"type": "str"},
            "strategic_pillar": {"type": "str"},
            "owner": {"type": "str"},
            "weight": {"type": "num"},
            "period": {"type": "str"},
            "target": {"type": "num"},
            "kpi": {"type": "str"},
            "initiative": {"type": "str"},
            "budget": {"type": "num"},
            "expected_result": {"type": "str"},
            "actual_result": {"type": "str"},
            "forecast": {"type": "str"},
            "health": {"type": "str"},
            "risks": {"type": "list"},
            "assumptions": {"type": "list"},
        },
        "relationships": ["kpi", "initiative", "campaign", "budget", "market_share"],
    },
    "brand_plan": {
        "fields": {
            "id": {"type": "str", "required": True},
            "fiscal_year": {"type": "str", "required": True},
            "situation_analysis": {"type": "str"},
            "business_challenge": {"type": "str"},
            "market_challenge": {"type": "str"},
            "strategic_objective": {"type": "str"},
            "brand_objective": {"type": "str"},
            "target_customer": {"type": "str"},
            "positioning": {"type": "str"},
            "value_proposition": {"type": "str"},
            "strategic_pillars": {"type": "list"},
            "initiatives": {"type": "list"},
            "campaigns": {"type": "list"},
            "channel_strategy": {"type": "str"},
            "budget": {"type": "num"},
            "kpis": {"type": "list"},
            "expected_outcome": {"type": "str"},
            "timeline": {"type": "str"},
            "owner": {"type": "str"},
            "risk": {"type": "list"},
            "assumptions": {"type": "list"},
            "approval_status": {"type": "str"},
        },
        "relationships": ["strategic_objective", "budget", "campaign", "kpi"],
    },
    "campaign": {
        "fields": {
            "id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "campaign_type": {"type": "str"},
            "channel": {"type": "str"},
            "start_date": {"type": "date"},
            "end_date": {"type": "date"},
            "owner": {"type": "str"},
            "strategic_objective": {"type": "str"},
            "initiative": {"type": "str"},
            "budget": {"type": "num"},
            "spend": {"type": "num"},
            "target_kpi": {"type": "num"},
            "actual_kpi": {"type": "num"},
            "status": {"type": "str"},
            "completion_pct": {"type": "num"},
            "evidence": {"type": "str"},
            "issue": {"type": "str"},
            "execution_health": {"type": "str"},
        },
        "relationships": ["strategic_objective", "initiative", "activity", "brand_budget", "kpi"],
    },
    "activity": {
        "fields": {
            "id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "campaign_id": {"type": "str"},
            "activity_type": {"type": "str"},
            "channel": {"type": "str"},
            "location": {"type": "str"},
            "target_audience": {"type": "str"},
            "start_date": {"type": "date"},
            "end_date": {"type": "date"},
            "owner": {"type": "str"},
            "budget": {"type": "num"},
            "spend": {"type": "num"},
            "status": {"type": "str"},
            "output": {"type": "str"},
            "target_kpi": {"type": "num"},
            "actual_kpi": {"type": "num"},
            "result": {"type": "str"},
            "remarks": {"type": "str"},
        },
        "relationships": ["campaign", "strategic_objective", "brand_budget"],
    },
    "finance_budget": {
        "fields": {
            "id": {"type": "str", "required": True},
            "fiscal_year": {"type": "str", "required": True},
            "month": {"type": "str", "required": True},
            "line_item": {"type": "str", "required": True},
            "budget": {"type": "num"},
            "actual": {"type": "num"},
            "variance": {"type": "num"},
            "variance_pct": {"type": "num"},
            "pct_of_net_sales": {"type": "num"},
        },
        "relationships": ["finance_budget_total", "brand_budget"],
    },
    "finance_budget_total": {
        "fields": {
            "id": {"type": "str", "required": True},
            "fiscal_year": {"type": "str", "required": True},
            "month": {"type": "str"},
            "net_sales": {"type": "num"},
            "cogs": {"type": "num"},
            "gross_profit": {"type": "num"},
            "ebitda": {"type": "num"},
            "net_profit": {"type": "num"},
            "sales_qty_cft": {"type": "num"},
            "rate": {"type": "num"},
        },
        "relationships": ["finance_budget", "kpi"],
    },
    "brand_budget": {
        "fields": {
            "id": {"type": "str", "required": True},
            "fiscal_year": {"type": "str", "required": True},
            "activity_type": {"type": "str", "required": True},
            "q1": {"type": "num"},
            "q2": {"type": "num"},
            "q3": {"type": "num"},
            "q4": {"type": "num"},
            "annual_total": {"type": "num"},
            "pct": {"type": "num"},
            "till_date_cost": {"type": "num"},
            "remaining_budget": {"type": "num"},
            "status": {"type": "str"},
        },
        "relationships": ["campaign", "activity", "finance_budget", "strategic_objective"],
    },
    "market_share": {
        "fields": {
            "id": {"type": "str", "required": True},
            "month": {"type": "str", "required": True},
            "competitor": {"type": "str", "required": True},
            "share_pct": {"type": "num"},
            "volume": {"type": "num"},
            "growth": {"type": "num"},
            "akij_share_pct": {"type": "num"},
            "market_rank": {"type": "int"},
        },
        "relationships": ["strategic_objective", "campaign", "sales"],
    },
    "kpi": {
        "fields": {
            "id": {"type": "str", "required": True},
            "name": {"type": "str", "required": True},
            "target": {"type": "num"},
            "actual": {"type": "num"},
            "variance": {"type": "num"},
            "variance_pct": {"type": "num"},
            "period": {"type": "str"},
            "previous_period": {"type": "num"},
            "trend": {"type": "str"},
            "status": {"type": "str"},
            "strategic_impact": {"type": "str"},
            "business_impact": {"type": "str"},
            "owner": {"type": "str"},
        },
        "relationships": ["strategic_objective", "campaign", "budget", "market_share"],
    },
    "sales_achievement": {
        "fields": {
            "id": {"type": "str", "required": True},
            "month": {"type": "str", "required": True},
            "monthly_target": {"type": "num"},
            "mtd_sales": {"type": "num"},
            "achievement_pct": {"type": "num"},
            "present_ads": {"type": "num"},
            "logical_sales_till_date": {"type": "num"},
            "remaining_sales": {"type": "num"},
            "days_consumed": {"type": "int"},
            "days_remaining": {"type": "int"},
            "rads": {"type": "num"},
        },
        "relationships": ["kpi", "finance_budget_total", "strategic_objective"],
    },
    "ai_recommendation": {
        "fields": {
            "id": {"type": "str", "required": True},
            "observation": {"type": "str"},
            "target_vs_actual": {"type": "str"},
            "variance": {"type": "str"},
            "data_sources": {"type": "list"},
            "diagnosis": {"type": "str"},
            "root_cause_hypothesis": {"type": "str"},
            "missing_data": {"type": "list"},
            "next_best_action": {"type": "str", "required": True},
            "alternative_action": {"type": "str"},
            "action_type": {"type": "str"},
            "intervention_level": {"type": "str"},
            "business_impact": {"type": "str"},
            "budget_impact": {"type": "str"},
            "owner": {"type": "str"},
            "deadline": {"type": "date"},
            "priority_score": {"type": "int"},
            "confidence": {"type": "num"},
            "source_freshness": {"type": "str"},
            "status": {"type": "str"},
        },
        "relationships": ["management_decision", "kpi", "campaign", "budget", "market_share", "sales_achievement"],
    },
    "management_decision": {
        "fields": {
            "id": {"type": "str", "required": True},
            "decision": {"type": "str", "required": True},
            "issue": {"type": "str"},
            "recommendation_id": {"type": "str"},
            "date": {"type": "date"},
            "approver": {"type": "str"},
            "owner": {"type": "str"},
            "evidence": {"type": "str"},
            "data_sources": {"type": "list"},
            "budget_impact": {"type": "str"},
            "expected_outcome": {"type": "str"},
            "actual_outcome": {"type": "str"},
            "follow_up": {"type": "str"},
            "result": {"type": "str"},
            "lessons": {"type": "str"},
        },
        "relationships": ["ai_recommendation", "corrective_action", "kpi"],
    },
    "corrective_action": {
        "fields": {
            "id": {"type": "str", "required": True},
            "action": {"type": "str", "required": True},
            "decision_id": {"type": "str"},
            "owner": {"type": "str"},
            "deadline": {"type": "date"},
            "status": {"type": "str"},
            "progress": {"type": "num"},
            "result": {"type": "str"},
        },
        "relationships": ["management_decision", "ai_recommendation", "kpi"],
    },
    "data_sync": {
        "fields": {
            "id": {"type": "str", "required": True},
            "source_id": {"type": "str", "required": True},
            "started_at": {"type": "str", "required": True},
            "finished_at": {"type": "str"},
            "status": {"type": "str", "required": True},
            "records_imported": {"type": "int"},
            "records_updated": {"type": "int"},
            "errors": {"type": "list"},
            "warnings": {"type": "list"},
        },
        "relationships": [],
    },
}

# --------------------------------------------------------------------------
# Source-field -> canonical-field mappings
# --------------------------------------------------------------------------
# Each mapping: source key -> { entity, field_map: {source_col_index_or_name: canonical_field} }
SOURCE_MAPPINGS = {
    "finance_budget": {
        "entity": "finance_budget_total",
        # finance sheet columns (0-indexed) - see Phase 2 audit:
        # 0=Month, 1=SalesQty Budget25-26, 2=SalesQty Actual25-26, 3=SalesQty Budget26-27,
        # 4=Rate Actual25-26, 5=Rate Budget26-27, 7=NetSales Budget25-26,
        # 8=NetSales Actual25-26, 9=NetSales Budget26-27, ...
        "field_map": {
            "month": {"col": 0},
            "sales_qty_cft": {"col": 3},
            "rate": {"col": 5},
            "net_sales": {"col": 9},
        },
        "fiscal_year": "2026-2027",
        "expected_header_rows": [3, 4],
        "data_start_row": 5,
    },
    "brand_budget": {
        "entity": "brand_budget",
        "field_map": {
            "activity_type": {"col": 1},
            "q1": {"col": 2},
            "q2": {"col": 3},
            "q3": {"col": 4},
            "q4": {"col": 5},
            "annual_total": {"col": 6},
            "pct": {"col": 7},
            "till_date_cost": {"col": 8},
            "remaining_budget": {"col": 9},
        },
        "fiscal_year": "2026-2027",
        "expected_header_rows": [3],
        "data_start_row": 4,
        "skip_rows_if": {"col": 1, "value": "Total"},
    },
    "campaign_activity": {
        "entity": "activity",
        "field_map": {
            # Placeholder - actual source GID/tab pending confirmation
            "name": {"col": None},
            "activity_type": {"col": None},
            "channel": {"col": None},
            "start_date": {"col": None},
            "end_date": {"col": None},
            "owner": {"col": None},
            "budget": {"col": None},
            "spend": {"col": None},
            "status": {"col": None},
            "output": {"col": None},
            "target_kpi": {"col": None},
            "actual_kpi": {"col": None},
            "result": {"col": None},
            "remarks": {"col": None},
        },
        "mapping_status": "template_only",
        "data_start_row": 1,
    },
    "market_share": {
        "entity": "market_share",
        "field_map": {
            "month": {"col": 0},
            "shah_cement": {"col": 1},
            "crown": {"col": 2},
            "nde": {"col": 3},
            "basundhara": {"col": 4},
            "akij": {"col": 5},
            "akij_share_pct": {"col": 6},
        },
        "header_row": 1,
        "data_start_row": 2,
    },
    "mtd_sales_statement": {
        "entity": "sales_achievement",
        "field_map": {
            "monthly_target": {"label_col": 15, "label": "Monthly Target", "value_col": 16},
            "mtd_sales": {"label_col": 15, "label": "Sales Till Date", "value_col": 16},
            "achievement_pct": {"label_col": 15, "label": "Achiv % till date", "value_col": 16},
            "present_ads": {"label_col": 15, "label": "Present ADS", "value_col": 16},
            "logical_sales_till_date": {"label_col": 15, "label": "Logical Sales till date", "value_col": 16},
            "remaining_sales": {"label_col": 15, "label": "Remaining Sales", "value_col": 16},
            "days_consumed": {"label_col": 15, "label": "Day's consumed", "value_col": 16},
            "days_remaining": {"label_col": 15, "label": "Days Remaining", "value_col": 16},
            "rads": {"label_col": 15, "label": "RADS", "value_col": 16},
        },
        "month_header_prefix": "Month Name:",
        "data_start_row": 1,
    },
    "mssql_dwh": {
        "entity": "delivery_sales",
        "table": "sms.tblDeliveryHeaderArc",
        "field_map": {
            "delivery_date": {"col": "dteDeliveryDate"},
            "net_value": {"col": "numTotalNetValue"},
            "volume": {"col": "numTotalDeliveryQuantity"},
            "zone": {"col": "strTransportZoneName"},
            "dealer": {"col": "strSoldToPartnerName"},
            "business_unit_id": {"col": "intBusinessUnitId"},
        },
        "business_unit_id": 175,
    },
}

# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------
REQUIRED_FIELDS_CACHE: dict[str, list[str]] = {}


def entity_fields(entity: str) -> list[str]:
    """Ordered field names for an entity."""
    return list(CANONICAL_ENTITIES.get(entity, {}).get("fields", {}).keys())


def required_fields(entity: str) -> list[str]:
    if entity not in REQUIRED_FIELDS_CACHE:
        REQUIRED_FIELDS_CACHE[entity] = [
            f for f, spec in CANONICAL_ENTITIES.get(entity, {}).get("fields", {}).items()
            if spec.get("required")
        ]
    return REQUIRED_FIELDS_CACHE[entity]


def validate_record(entity: str, record: dict) -> list[str]:
    """Return a list of validation errors for a canonical record."""
    errors: list[str] = []
    schema = CANONICAL_ENTITIES.get(entity)
    if not schema:
        return [f"unknown canonical entity: {entity}"]
    fields = schema["fields"]
    for field, spec in fields.items():
        val = record.get(field)
        if spec.get("required") and (val is None or val == ""):
            errors.append(f"{entity}.{field}: required")
            continue
        if val is None or val == "":
            continue
        ftype = spec["type"]
        if ftype == "num":
            try:
                float(val)
            except (TypeError, ValueError):
                errors.append(f"{entity}.{field}: expected number, got {val!r}")
        elif ftype == "int":
            try:
                int(val)
            except (TypeError, ValueError):
                errors.append(f"{entity}.{field}: expected integer, got {val!r}")
        elif ftype == "list" and not isinstance(val, list):
            errors.append(f"{entity}.{field}: expected list, got {type(val).__name__}")
        elif ftype == "date" and not isinstance(val, (str, datetime)):
            errors.append(f"{entity}.{field}: expected date/string, got {val!r}")
    return errors


def map_record(source: str, raw_row: list, context: dict | None = None) -> dict | None:
    """Map a raw source row to a canonical record using SOURCE_MAPPINGS.

    Returns None if the row should be skipped (e.g. total rows).
    """
    mapping = SOURCE_MAPPINGS.get(source)
    if not mapping or mapping.get("mapping_status") == "template_only":
        return None
    entity = mapping["entity"]
    field_map = mapping["field_map"]
    record: dict = {}
    for canonical_field, spec in field_map.items():
        col = spec.get("col")
        if col is None:
            continue
        try:
            record[canonical_field] = raw_row[col]
        except IndexError:
            record[canonical_field] = None
    # skip total / subtotal rows based on skip config
    skip = mapping.get("skip_rows_if")
    if skip:
        col = skip.get("col")
        val = skip.get("value")
        if col is not None and raw_row and str(raw_row[col]).strip() == str(val):
            return None
    # attach lineage
    record["id"] = _record_id(entity, record)
    if context:
        record.update(context)
    return record


def _record_id(entity: str, record: dict) -> str:
    """Deterministic id from key fields for idempotent imports."""
    schema = CANONICAL_ENTITIES.get(entity, {}).get("fields", {})
    key_fields = [f for f in ("id", "month", "activity_type", "name", "fiscal_year", "competitor") if f in schema]
    parts = []
    for f in key_fields:
        v = record.get(f)
        if v is not None:
            parts.append(f"{f}={v}")
    if parts:
        return f"{entity}:{hashlib.md5(':'.join(parts).encode()).hexdigest()[:12]}"
    return f"{entity}:{datetime.now().timestamp():.0f}"


# --------------------------------------------------------------------------
# Lineage helper
# --------------------------------------------------------------------------
def lineage(source: str, record: dict | None = None, row: int | None = None) -> dict:
    src = DATA_SOURCES.get(source, {})
    meta = {
        "source_type": src.get("source_type"),
        "source_system": src.get("name"),
        "source_file_id": src.get("file_id"),
        "source_gid": src.get("gid"),
        "source_sheet": src.get("sheet"),
        "synced_at": datetime.now().isoformat(timespec="seconds"),
    }
    if row is not None:
        meta["source_row"] = row
    return meta


def source_registry() -> dict:
    return DATA_SOURCES


def persist_registry() -> None:
    out = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": DATA_SOURCES,
        "entities": {k: list(v["fields"].keys()) for k, v in CANONICAL_ENTITIES.items()},
        "mappings": {
            k: {
                "entity": v.get("entity"),
                "mapping_status": v.get("mapping_status", "defined"),
                "data_start_row": v.get("data_start_row"),
                "field_map": {kk: s for kk, s in (v.get("field_map") or {}).items()},
            }
            for k, v in SOURCE_MAPPINGS.items()
        },
    }
    p = DATA_DIR / "canonical_registry.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(persist_registry(), ensure_ascii=False, indent=2))
