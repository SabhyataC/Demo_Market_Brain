import json
import re
from app.model_client import ask_with_image

PROMPT = """List every product clearly visible on this shelf.
Skip products that are mostly cut off.
Return ONLY a JSON array, no other text. Each item:
{"name": "product name as printed", "brand": "brand or null", "category": "food|beauty|home|other"}"""


def parse_json_list(text: str) -> list[dict]:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []


def extract_from_frame(image_path: str) -> list[dict]:
    return parse_json_list(ask_with_image(PROMPT, image_path))

import re as _re


def _tokens(name: str) -> set[str]:
    return set(_re.findall(r"[a-z0-9]+", name.lower()))


def _same(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def build_catalog(frame_paths: list[str]) -> list[dict]:
    catalog: list[dict] = []
    for path in frame_paths:
        seen_this_frame = []
        for item in extract_from_frame(path):
            name = (item.get("name") or "").strip()
            if not name:
                continue
            match = next((c for c in catalog if _same(c["name"], name)), None)
            if match:
                if len(name) > len(match["name"]):
                    match["name"] = name
                if path not in match["frames"]:
                    match["frames"].append(path)
            else:
                catalog.append({
                    "name": name,
                    "brand": item.get("brand"),
                    "category": item.get("category", "other"),
                    "frames": [path],
                })
    return catalog