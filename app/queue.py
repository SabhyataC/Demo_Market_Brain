import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_conn
from app.audit import log
from app.budget import check_budget

router = APIRouter()


class ProposalIn(BaseModel):
    kind: str          # e.g. "catalog_draft", "promotion", "ad_draft"
    payload: dict


@router.post("/proposals")
def create_proposal(p: ProposalIn):
    if p.kind == "ad_draft":
        check_budget(p.payload)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (kind, payload) VALUES (?, ?)",
            (p.kind, json.dumps(p.payload)),
        )
        pid = cur.lastrowid
    log("ai", "proposal_created", f"id={pid} kind={p.kind}")
    return {"id": pid, "status": "pending"}


@router.get("/proposals")
def list_proposals(status: str = "pending"):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM proposals WHERE status = ? ORDER BY id", (status,)
        ).fetchall()
    return [dict(r) | {"payload": json.loads(r["payload"])} for r in rows]


def _decide(pid: int, status: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, kind, payload FROM proposals WHERE id = ?", (pid,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Proposal not found")
        if status == "approved" and row["kind"] == "ad_draft":
            check_budget(json.loads(row["payload"]))
        if row["status"] != "pending":
            raise HTTPException(400, f"Already {row['status']}")
        conn.execute(
            "UPDATE proposals SET status = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, pid),
        )
        if status == "approved" and row["kind"] == "catalog_draft":
            items = json.loads(row["payload"]).get("items", [])
            for it in items:
                conn.execute(
                    "INSERT INTO products (name, brand) VALUES (?, ?)",
                    (it.get("name"), it.get("brand")),
                )
            added = len(items)
    log("owner", f"proposal_{status}", f"id={pid}")
    if status == "approved" and row["kind"] == "catalog_draft":
        log("owner", "catalog_imported", f"proposal={pid} products={added}")
    return {"id": pid, "status": status}


@router.post("/proposals/{pid}/approve")
def approve(pid: int):
    return _decide(pid, "approved")


@router.post("/proposals/{pid}/reject")
def reject(pid: int):
    return _decide(pid, "rejected")


@router.get("/audit")
def get_audit(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]