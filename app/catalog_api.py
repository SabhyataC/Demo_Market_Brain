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
from app.frames import sample_frames, crop_around
from fastapi import UploadFile, File, Form

router = APIRouter(prefix="/catalog", tags=["catalog"])


class VideoIn(BaseModel):
    video_path: str
    notes: str = ""


@router.post("/from-video")
def from_video(body: VideoIn):
    frames = sample_frames(body.video_path, "data/frames")
    if not frames:
        raise HTTPException(400, "Could not get any frames from this video")
    errors: list = []
    items = build_catalog(frames, errors, body.notes)
    if len(errors) == len(frames):
        raise HTTPException(502, f"The model could not read any frame. First error: {errors[0][1]}")
    for n, it in enumerate(items, 1):                      # one picture per row, showing only that product
        thumb = f"data/frames/thumb_{n:03d}.jpg"
        it["thumb"] = thumb if crop_around(it["best_frame"], it.get("best_x"), thumb) else it["best_frame"]
    flagged = sum(1 for it in items if it["check"])
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (kind, payload) VALUES (?, ?)",
            ("catalog_draft", json.dumps({"items": items})),
        )
        pid = cur.lastrowid
        conn.execute(
            "INSERT INTO audit_log (actor, action, detail) VALUES (?, ?, ?)",
            ("ai", "catalog_draft_created",
             f"proposal {pid}, {len(items)} items, {flagged} to check, "
             f"{len(frames) - len(errors)}/{len(frames)} frames read"),
        )
    return {
        "proposal_id": pid, "count": len(items), "items": items,
        "frames_read": len(frames) - len(errors), "frames_failed": len(errors),
    }
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
def upload(file: UploadFile = File(...), notes: str = Form("")):
    Path("data").mkdir(exist_ok=True)
    dest = Path("data") / "uploaded_video.mp4"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return from_video(VideoIn(video_path=str(dest), notes=notes))