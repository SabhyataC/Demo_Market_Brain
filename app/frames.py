import subprocess
from pathlib import Path


def sample_frames(video_path: str, out_dir: str, fps: float = 1.0) -> list[str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("frame_*.jpg"):
        old.unlink()
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", video_path,
         "-vf", f"fps={fps}", "-q:v", "2",
         str(out / "frame_%03d.jpg")],
        check=True,
    )
    return sorted(str(p) for p in out.glob("frame_*.jpg"))