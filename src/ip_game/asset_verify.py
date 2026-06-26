from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .video_from_images import probe_video_ok


def _target_ratio(aspect_ratio: str) -> float:
    if "9:16" in aspect_ratio:
        return 9 / 16
    return 16 / 9


def _is_final_delivery(meta: dict) -> bool:
    tier = str(meta.get("deliveryTier") or meta.get("runMode") or "").lower()
    return tier in {"final", "production", "release", "api", "video-api"}


def verify_project_assets(project_dir: Path, story_path: Path | None = None) -> tuple[bool, list[str]]:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = json.loads(story_path.read_text(encoding="utf-8-sig"))
    meta = story.get("meta") or {}
    q = meta.get("questionnaire") or {}
    expected_ratio = _target_ratio(str(q.get("aspect_ratio") or "横版16:9"))
    final_delivery = _is_final_delivery(meta)
    problems: list[str] = []

    def check_rel(rel: str | None, what: str, node_id: str) -> Path | None:
        if not rel:
            problems.append(f"[{node_id}] missing {what}")
            return None
        p = (project_dir / rel).resolve()
        if not p.exists():
            problems.append(f"[{node_id}] not found {what}: {rel}")
            return None
        if p.is_file() and p.stat().st_size <= 0:
            problems.append(f"[{node_id}] empty file {what}: {rel}")
            return None
        return p

    def check_image(rel: str | None, what: str, node_id: str) -> None:
        p = check_rel(rel, what, node_id)
        if not p:
            return
        try:
            with Image.open(p) as img:
                w, h = img.size
        except Exception as exc:
            problems.append(f"[{node_id}] image unreadable {what}: {rel} ({exc})")
            return
        if w <= 0 or h <= 0:
            problems.append(f"[{node_id}] invalid image size {what}: {rel}")
            return
        ratio = w / h
        if abs(ratio - expected_ratio) > 0.08:
            problems.append(f"[{node_id}] image aspect mismatch {what}: {rel} ({w}x{h})")

    poster = (meta.get("poster") or "").strip()
    if poster:
        check_image(poster, "meta.poster", "meta")
    map_overview = (meta.get("mapOverviewImage") or "").strip()
    if map_overview:
        check_image(map_overview, "meta.mapOverviewImage", "meta")

    for node in story.get("nodes") or []:
        nid = str(node.get("id") or "")
        media = node.get("media") or {}
        # Images are optional, but if referenced they should exist
        for k in ("sceneImage", "storyboardImage", "endingImage", "poster", "videoRefImage"):
            if media.get(k):
                check_image(media.get(k), k, nid)

        # Video should exist if referenced
        if media.get("video"):
            rel = media.get("video")
            p = (project_dir / rel).resolve()
            if not probe_video_ok(p):
                problems.append(f"[{nid}] video not playable or missing: {rel}")
            elif final_delivery and p.stat().st_size < 1024 * 1024:
                problems.append(f"[{nid}] final delivery video is suspiciously small: {rel}")

    if final_delivery:
        for ch in story.get("characters") or []:
            cid = str(ch.get("id") or ch.get("name") or "character")
            for rel in (ch.get("referenceImages") or []):
                check_image(rel, "character.referenceImages", cid)
            for key, rel in (ch.get("images") or {}).items():
                if rel:
                    check_image(rel, f"character.images.{key}", cid)

    ok = len(problems) == 0
    return ok, problems

