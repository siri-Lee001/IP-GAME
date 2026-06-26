from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .asset_verify import verify_project_assets
from .character_prompts import generate_character_prompts
from .html_build import build_game_html
from .map_overview import render_map_overview
from .node_prompts import generate_node_prompts
from .video_from_images import make_videos_from_images


def _p(path: str) -> Path:
    return Path(path).expanduser().resolve()


def cmd_build_html(args: argparse.Namespace) -> int:
    out = build_game_html(_p(args.project_dir), story_path=_p(args.story) if args.story else None, ui_path=_p(args.ui) if args.ui else None)
    print(out)
    return 0


def cmd_make_videos(args: argparse.Namespace) -> int:
    only = set()
    if args.only:
        only = {x.strip() for x in args.only.split(",") if x.strip()}
    make_videos_from_images(
        _p(args.project_dir),
        story_path=_p(args.story) if args.story else None,
        only=only or None,
        skip_existing=bool(args.skip_existing),
        size=args.size,
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    ok, problems = verify_project_assets(_p(args.project_dir), story_path=_p(args.story) if args.story else None)
    if ok:
        print("ASSET VERIFY: OK")
        return 0
    print("ASSET VERIFY: FAILED")
    for p in problems:
        print("-", p)
    return 2


def cmd_generate_node_prompts(args: argparse.Namespace) -> int:
    generate_node_prompts(_p(args.project_dir), story_path=_p(args.story) if args.story else None)
    return 0


def cmd_generate_character_prompts(args: argparse.Namespace) -> int:
    generate_character_prompts(_p(args.project_dir), story_path=_p(args.story) if args.story else None)
    return 0


def cmd_render_map_overview(args: argparse.Namespace) -> int:
    out = render_map_overview(
        _p(args.project_dir),
        story_path=_p(args.story) if args.story else None,
        out_path=_p(args.out) if args.out else None,
    )
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ip-game", description="IP-GAME CLI: prompts, prototype videos, verification, and offline HTML.")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-html", help="Build game.html from story.json/ui.json")
    b.add_argument("project_dir")
    b.add_argument("--story", default=None, help="Path to story.json (default: <project_dir>/story.json)")
    b.add_argument("--ui", default=None, help="Path to ui.json (default: <project_dir>/ui.json)")
    b.set_defaults(func=cmd_build_html)

    mv = sub.add_parser("make-videos", help="Synthesize prototype mp4 files from images locally (no API).")
    mv.add_argument("project_dir")
    mv.add_argument("--story", default=None)
    mv.add_argument("--only", default=None, help="Comma-separated node IDs, e.g. N0,E0")
    mv.add_argument("--skip-existing", action="store_true")
    mv.add_argument("--size", default=None, help="Override size, e.g. 1280x720")
    mv.set_defaults(func=cmd_make_videos)

    vf = sub.add_parser("verify", help="Verify assets exist and videos are playable.")
    vf.add_argument("project_dir")
    vf.add_argument("--story", default=None)
    vf.set_defaults(func=cmd_verify)

    gnp = sub.add_parser("generate-node-prompts", help="Fill scenePrompt/storyboardPrompt and default media paths into story.json")
    gnp.add_argument("project_dir")
    gnp.add_argument("--story", default=None)
    gnp.set_defaults(func=cmd_generate_node_prompts)

    gcp = sub.add_parser("generate-character-prompts", help="Fill characterSheetPrompt and default character image paths")
    gcp.add_argument("project_dir")
    gcp.add_argument("--story", default=None)
    gcp.set_defaults(func=cmd_generate_character_prompts)

    rmo = sub.add_parser("render-map-overview", help="Render a local fallback route overview image and save its path into story.json")
    rmo.add_argument("project_dir")
    rmo.add_argument("--story", default=None)
    rmo.add_argument("--out", default=None, help="Override output image path (default: <project_dir>/assets/images/map_overview.png)")
    rmo.set_defaults(func=cmd_render_map_overview)

    return p


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

