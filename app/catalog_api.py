import json
from fastapi import APIRouter
from pydantic import BaseModel
from app.db import get_conn
from app.frames import sample_frames
from app.catalog import build_catalog
from fastapi import APIRouter, HTTPException
import shutil
from pathlib import Path
from fastapi import UploadFile, File

router = APIRouter(prefix="/catalog", tags=["catalog"])


class VideoIn(BaseModel):
    video_path: str


@router.post("/from-video")
def from_video(body: VideoIn):
    frames = sample_frames(body.video_path, "data/frames")
    items = build_catalog(frames)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (kind, payload) VALUES (?, ?)",
            ("catalog_draft", json.dumps({"items": items})),
        )
        pid = cur.lastrowid
        conn.execute(
            "INSERT INTO audit_log (actor, action, detail) VALUES (?, ?, ?)",
            ("ai", "catalog_draft_created", f"proposal {pid}, {len(items)} items"),
        )
    return {"proposal_id": pid, "count": len(items), "items": items}

class DraftEdit(BaseModel):
    items: list[dict]


@router.put("/draft/{pid}")
def edit_draft(pid: int, body: DraftEdit):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, kind FROM proposals WHERE id = ?", (pid,)
        ).fetchone()
        if not row or row["kind"] != "catalog_draft":
            raise HTTPException(404, "Catalog draft not found")
        if row["status"] != "pending":
            raise HTTPException(400, f"Already {row['status']}")
        conn.execute(
            "UPDATE proposals SET payload = ? WHERE id = ?",
            (json.dumps({"items": body.items}), pid),
        )
        conn.execute(
            "INSERT INTO audit_log (actor, action, detail) VALUES (?, ?, ?)",
            ("owner", "catalog_draft_edited", f"proposal {pid}, {len(body.items)} items"),
        )
    return {"proposal_id": pid, "count": len(body.items)}

@router.post("/upload")
def upload(file: UploadFile = File(...)):
    Path("data").mkdir(exist_ok=True)
    dest = Path("data") / "uploaded_video.mp4"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return from_video(VideoIn(video_path=str(dest)))