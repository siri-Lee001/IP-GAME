from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _ffmpeg() -> str:
    # imageio-ffmpeg provides a bundled ffmpeg binary for cross-platform usage.
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _probe_ffprobe() -> str:
    ffmpeg = Path(_ffmpeg())
    if ffmpeg.name.lower().startswith("ffmpeg"):
        cand = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe")
        if cand.exists():
            return str(cand)
    return "ffprobe"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _size_from_aspect(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "竖版9:16":
        return (1080, 1920)
    return (1920, 1080)


def make_videos_from_images(
    project_dir: Path,
    story_path: Path | None = None,
    only: set[str] | None = None,
    skip_existing: bool = False,
    size: str | None = None,
) -> None:
    """
    Pure local synthesis: sceneImage + storyboardImage -> mp4 (H.264 + silent AAC track).
    No API calls.
    """
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = _read_json(story_path)

    meta = story.get("meta") or {}
    q = meta.get("questionnaire") or {}
    aspect_ratio = q.get("aspect_ratio", "横版16:9")

    if size:
        w, h = [int(x) for x in size.lower().split("x")]
    else:
        w, h = _size_from_aspect(aspect_ratio)

    out_dir = project_dir / "assets" / "videos"
    _ensure_dir(out_dir)

    ffmpeg = _ffmpeg()

    def to_abs(rel: str | None) -> str | None:
        if not rel:
            return None
        return str((project_dir / rel).resolve())

    for node in story.get("nodes") or []:
        nid = str(node.get("id") or "")
        if not nid:
            continue
        if only and nid not in only:
            continue

        media = node.get("media") or {}
        out_rel = media.get("video") or f"assets/videos/{nid}.mp4"
        out_path = (project_dir / out_rel).resolve()
        _ensure_dir(out_path.parent)
        if skip_existing and out_path.exists() and out_path.stat().st_size > 0:
            continue

        scene = to_abs(media.get("sceneImage") or media.get("poster"))
        board = to_abs(media.get("storyboardImage") or media.get("videoRefImage"))

        # fallback: endingImage for endings if storyboard missing
        if (not board) and (node.get("isEnding") is True):
            board = to_abs(media.get("endingImage"))

        if not scene and not board:
            # nothing to build; leave empty
            continue

        duration = int(media.get("durationSeconds") or (meta.get("videoDefaults") or {}).get("durationSeconds") or 6)
        scene_dur = min(2, max(1, duration // 3))
        board_dur = max(1, duration - scene_dur)

        tmp_dir = project_dir / ".tmp_render"
        _ensure_dir(tmp_dir)
        seg1 = tmp_dir / f"{nid}.seg1.mp4"
        seg2 = tmp_dir / f"{nid}.seg2.mp4"
        concat_list = tmp_dir / f"{nid}.concat.txt"
        final_tmp = tmp_dir / f"{nid}.tmp.mp4"

        def render_still(img_path: str, out_mp4: Path, seconds: int) -> None:
            # contain+pad (no crop)
            filt = f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
            cmd = [
                ffmpeg,
                "-y",
                "-loop",
                "1",
                "-t",
                str(seconds),
                "-i",
                img_path,
                "-vf",
                filt,
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(out_mp4),
            ]
            _run(cmd)

        if scene:
            render_still(scene, seg1, scene_dur)
        else:
            render_still(board, seg1, scene_dur)

        if board:
            render_still(board, seg2, board_dur)
        else:
            render_still(scene, seg2, board_dur)

        concat_list.write_text(f"file '{seg1.as_posix()}'\nfile '{seg2.as_posix()}'\n", encoding="utf-8")

        # concat + add silent audio track for compatibility
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(final_tmp),
        ]
        _run(cmd)

        # atomic replace
        if final_tmp.exists() and final_tmp.stat().st_size > 0:
            out_path.write_bytes(final_tmp.read_bytes())

    # cleanup tmp can be left for debugging; do not delete automatically


def probe_video_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    ffprobe = _probe_ffprobe()
    try:
        subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)], check=True, capture_output=True)
        return True
    except Exception:
        return False

