"""nasim_procurement.py - Dynamic IR/PR/PO procurement for an employee.

Fetches Item Requests (IR) created by a given employee (by user id), then
traces the linked Purchase Requests (PR) and Purchase Orders (PO) via item
name matching within the same plant, and returns a combined register.

Used by the Nasim Marketing Procurement dashboard pane (enroll 563614).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _query(sql, params=()):
    import server
    return server._q(sql, params)


def _user_id_for(reference_id: int) -> int | None:
    """Map an employee reference id (enroll) to the DWH user id (intUserId)."""
    rows = _query(
        "SELECT TOP 1 intUserId FROM dco.tblUserArc WHERE intUserReferenceId=%s",
        (reference_id,),
    )
    if isinstance(rows, dict) or not rows:
        return None
    return int(rows[0][0])


def get_procurement(enroll: int = 563614, business_unit: int = 175) -> dict:
    """Return IRs created by the employee + linked PRs/POs + marketing budget."""
    user_id = _user_id_for(enroll)

    # 1. IRs created by the employee
    irs = []
    if user_id:
        rows = _query(
            """SELECT h.intItemRequestId, h.strItemRequestCode, h.strCostCenterName,
                      h.strCostElementName, h.strPurpose, h.numTotalQty, h.strPlantName,
                      h.strWarehouseName, h.dteRequestDate, h.isApproved, h.isComplete, h.isClosed
               FROM wms.tblItemRequestHeaderArc h
               WHERE h.intBusinessUnitId=%s AND h.isActive=1 AND h.intActionBy=%s
               ORDER BY h.dteRequestDate DESC""",
            (business_unit, user_id),
        )
        if not isinstance(rows, dict):
            for r in rows:
                irs.append({
                    "ir_id": r[0], "ir_code": r[1], "cost_center": r[2] or "",
                    "cost_element": r[3] or "", "purpose": r[4] or "",
                    "total_qty": float(r[5] or 0), "plant": (r[6] or "").strip(),
                    "warehouse": (r[7] or "").strip(),
                    "request_date": str(r[8]),
                    "approved": bool(r[9]), "complete": bool(r[10]), "closed": bool(r[11]),
                })

    # 2. IR line items
    ir_ids = [i["ir_id"] for i in irs]
    ir_items = {}
    if ir_ids:
        ph = ",".join(str(x) for x in ir_ids)
        rows = _query(
            f"""SELECT intItemRequestId, strItemRequestCode, strItemName, numRequestQuantity,
                       numApprovedQuantity, numIssueQuantity
                FROM wms.tblItemRequestRowArc
                WHERE intItemRequestId IN ({ph}) AND IsActive=1""",
        )
        if not isinstance(rows, dict):
            for r in rows:
                ir_items.setdefault(r[0], []).append({
                    "ir_code": r[1], "item": r[2] or "",
                    "requested": float(r[3] or 0), "approved": float(r[4] or 0),
                    "issued": float(r[5] or 0),
                })

    # 3. Linked PRs and POs by item-name match per plant
    prs, pos = [], []
    for ir in irs:
        plant = ir["plant"]
        for line in ir_items.get(ir["ir_id"], []):
            item = line["item"]
            # find PR with same item + plant created ON/AFTER the IR date
            rows = _query(
                """SELECT TOP 5 h.strPurchaseRequestCode, h.dteRequestDate, h.strCostCenter,
                          h.strPurpose, h.isApproved, r.numRequestQuantity, r.numApprovedQuantity
                   FROM pro.tblPurchaseRequestHeaderArc h
                   JOIN pro.tblPurchaseRequestRowArc r ON r.intPurchaseRequestId = h.intPurchaseRequestId
                   WHERE h.intBusinessUnitId=%s AND h.isActive=1 AND r.isActive=1
                     AND r.strItemName LIKE %s AND h.strPlantName LIKE %s
                     AND h.dteRequestDate >= %s
                   ORDER BY h.dteRequestDate DESC""",
                (business_unit, f"%{item}%", f"%{plant}%", ir["request_date"]),
            )
            if not isinstance(rows, dict):
                for r in rows:
                    prs.append({
                        "ir_code": ir["ir_code"], "pr_code": r[0], "date": str(r[1]),
                        "cost_center": r[2] or "", "purpose": r[3] or "",
                        "approved": bool(r[4]), "qty": float(r[5] or 0),
                        "approved_qty": float(r[6] or 0),
                    })
            # find PO whose row's reference code is one of the PRs just found
            # (tight linkage: PO -> PR -> IR via exact PR reference code)
            for pr in prs:
                if pr["ir_code"] != ir["ir_code"]:
                    continue
                rows = _query(
                    """SELECT TOP 5 h.strPurchaseOrderNo, h.dtePurchaseOrderDate, h.strBusinessPartnerName,
                              h.numTotalAmount, h.numTotalQty, h.isApproved, h.isClosed,
                              r.strItemName, r.numOrderQty, r.numTotalValue
                       FROM pro.tblPurchaseOrderHeaderArc h
                       JOIN pro.tblPurchaseOrderRowArc r ON r.intPurchaseOrderId = h.intPurchaseOrderId
                       WHERE h.intBusinessUnitId=%s AND h.isActive=1 AND r.isActive=1
                         AND r.strReferenceCode = %s
                       ORDER BY h.dtePurchaseOrderDate DESC""",
                    (business_unit, pr["pr_code"]),
                )
                if not isinstance(rows, dict):
                    for r in rows:
                        pos.append({
                            "ir_code": ir["ir_code"], "pr_code": pr["pr_code"],
                            "po_no": r[0], "po_date": str(r[1]),
                            "vendor": r[2] or "", "po_amount": float(r[3] or 0),
                            "po_qty": float(r[4] or 0), "approved": bool(r[5]),
                            "closed": bool(r[6]), "item": r[7] or "",
                            "order_qty": float(r[8] or 0), "po_value": float(r[9] or 0),
                        })

    return {
        "employee": {"enroll": enroll, "user_id": user_id},
        "marketing_budget": 25907508.0,
        "irs": irs,
        "ir_items": ir_items,
        "prs": prs,
        "pos": pos,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    print(json.dumps(get_procurement(), ensure_ascii=False, indent=2))
