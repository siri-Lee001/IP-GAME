from __future__ import annotations

import json
from pathlib import Path

from .video_from_images import probe_video_ok


def verify_project_assets(project_dir: Path, story_path: Path | None = None) -> tuple[bool, list[str]]:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = json.loads(story_path.read_text(encoding="utf-8"))
    problems: list[str] = []

    def check_rel(rel: str | None, what: str, node_id: str) -> None:
        if not rel:
            problems.append(f"[{node_id}] missing {what}")
            return
        p = (project_dir / rel).resolve()
        if not p.exists():
            problems.append(f"[{node_id}] not found {what}: {rel}")
            return
        if p.is_file() and p.stat().st_size <= 0:
            problems.append(f"[{node_id}] empty file {what}: {rel}")

    for node in story.get("nodes") or []:
        nid = str(node.get("id") or "")
        media = node.get("media") or {}
        # Images are optional, but if referenced they should exist
        for k in ("sceneImage", "storyboardImage", "endingImage", "poster"):
            if media.get(k):
                check_rel(media.get(k), k, nid)

        # Video should exist if referenced
        if media.get("video"):
            rel = media.get("video")
            p = (project_dir / rel).resolve()
            if not probe_video_ok(p):
                problems.append(f"[{nid}] video not playable or missing: {rel}")

    ok = len(problems) == 0
    return ok, problems

