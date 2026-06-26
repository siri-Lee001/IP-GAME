from __future__ import annotations

import json
from importlib import resources
from pathlib import Path


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_game_html(project_dir: Path, story_path: Path | None = None, ui_path: Path | None = None) -> Path:
    """
    Build a self-contained HTML file at: <project_dir>/game.html
    This does NOT inline assets; it references relative files in assets/.
    """
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    ui_path = (ui_path or (project_dir / "ui.json")).resolve()

    story = _read_json(story_path)
    ui = _read_json(ui_path)

    meta = story.get("meta") or {}
    title = meta.get("title") or "IP-GAME"
    tagline = meta.get("tagline") or ""
    synopsis = meta.get("synopsis") or ""

    template = resources.files("ip_game.templates").joinpath("game.template.html").read_text(encoding="utf-8")

    out_html = (
        template.replace("__TITLE__", _escape_html(title))
        .replace("__TAGLINE__", _escape_html(tagline))
        .replace("__SYNOPSIS__", _escape_html(synopsis))
        .replace("__STORY_JSON__", json.dumps(story, ensure_ascii=False))
        .replace("__UI_CONFIG_JSON__", json.dumps(ui, ensure_ascii=False))
    )

    out_path = project_dir / "game.html"
    out_path.write_text(out_html, encoding="utf-8")
    return out_path


def _escape_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

