from __future__ import annotations

import json
import re
from pathlib import Path


def normalize_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    return s.strip()[:120] if s else "untitled"


def build_character_ref_block(story: dict, node: dict) -> str:
    chars = story.get("characters") or []
    id_map = {str(ch.get("id")): ch for ch in chars}
    refs = []
    for cid in node.get("characterRefs") or []:
        ch = id_map.get(str(cid))
        if not ch:
            continue
        img = ch.get("images") or {}
        local_refs = ch.get("referenceImages") or []
        source = ch.get("imageSourceStrategy") or ("local" if local_refs else "generate")
        ref_paths = [p for p in [img.get("sheet"), img.get("front"), img.get("side"), img.get("back"), img.get("face")] if p]
        ref_paths.extend([p for p in local_refs if p and p not in ref_paths])
        line = f"角色：{ch.get('name')}"
        if ch.get("visualState"):
            line += f"（{ch.get('visualState')}）"
        if source == "local":
            line += "；该角色已有用户确认过的本地角色图，后续画面必须优先沿用这些参考图，不得擅自重新设计。"
        else:
            line += "；该角色已有确认过的角色定妆基准图，后续画面必须保持一致。"
        if ref_paths:
            line += f" 参考图路径：{'；'.join(ref_paths)}"
        refs.append(line)
    return "\n".join(refs)


def build_scene_prompt(story: dict, meta: dict, node: dict, aspect_ratio: str) -> str:
    q = (meta.get("questionnaire") or {})
    style = q.get("visual_style", "CG写实")
    tone = q.get("color_tone", "古风淡雅")
    mood = q.get("mood", "热血")
    title = (node.get("title") or "").strip()
    desc = (node.get("description") or "").strip()
    char_block = build_character_ref_block(story, node)
    return (
        f"互动影游节点场景图（{aspect_ratio}，用于网页展示与视频开场）："
        f"{style}风格，{tone}色调，整体情绪偏{mood}。"
        f"场景：{title}。{desc}。"
        f"{('角色一致性要求：' + char_block + '。') if char_block else ''}"
        f"画面要求：清晰构图，明亮通透，避免过暗。"
        f"禁止出现可读文字。高细节，高质感。"
    )


def build_storyboard_prompt(story: dict, meta: dict, node: dict, aspect_ratio: str, duration_seconds: int, segment_seconds: int) -> str:
    q = (meta.get("questionnaire") or {})
    style = q.get("visual_style", "CG写实")
    tone = q.get("color_tone", "古风淡雅")
    mood = q.get("mood", "热血")
    title = (node.get("title") or "").strip()
    desc = (node.get("description") or "").strip()
    script = "\n".join(
        [x for x in [(node.get("narration") or "").strip(), (node.get("dialogue") or "").strip()] if x]
    )
    char_block = build_character_ref_block(story, node)

    seg = max(1, int(segment_seconds))
    frame_count = max(6, min(12, int(duration_seconds // seg) + 6))

    return f"""你是电影分镜师。请为“{title}”生成一张故事板合成图（{aspect_ratio}）。

风格：{style}；色调：{tone}；情绪：{mood}。
场景描述：{desc}

输出要求：
1) 单张图片，干净的 3x3 九宫格（九格等大），每格都有清晰镜头画面。
2) 镜头顺序从左到右、从上到下，形成连续叙事。
3) 镜头语言：景别要有变化（远景/中景/近景/特写），动作要清晰，构图要稳定。
4) 角色在九格之间必须是同一角色同一造型，发型/服装/关键识别点保持一致。
5) 禁止出现任何可读文字（包括字幕、编号、注释都不要写出来）。
6) 若已存在用户确认过的角色图/三视图/设定图，必须优先沿用，不得擅自改脸、改发型、改服装体系。

剧情素材（用于镜头拆解，按时间顺序）：
{script or "（无对白与旁白，按场景描述自行拆镜头）"}

角色一致性参考（严格执行）：
{char_block or "（未显式指定角色参考；如项目里已有角色定妆图，仍应优先沿用）"}

镜头长度提示：总时长 {duration_seconds}s，建议每格约 {seg}s，共 {frame_count} 份镜头信息，浓缩到 9 格中表达。
"""


def ensure_media_paths(node: dict) -> bool:
    media = node.setdefault("media", {})
    changed = False
    nid = node.get("id") or ""

    if not media.get("sceneImage"):
        media["sceneImage"] = f"assets/images/scenes/{nid}.jpg"
        changed = True

    sb_default = f"assets/images/storyboards/{nid}_board.jpg"
    ending_img = (media.get("endingImage") or "").strip()
    sb_cur = (media.get("storyboardImage") or "").strip()
    if node.get("isEnding") is True:
        if (not sb_cur) or (ending_img and sb_cur == ending_img):
            media["storyboardImage"] = sb_default
            changed = True
    else:
        if not sb_cur:
            media["storyboardImage"] = sb_default
            changed = True

    prefer = media.get("storyboardImage") or media.get("sceneImage") or media.get("poster")
    if prefer and media.get("videoRefImage") != prefer:
        media["videoRefImage"] = prefer
        changed = True

    if not media.get("video"):
        media["video"] = f"assets/videos/{nid}.mp4"
        changed = True
    return changed


def generate_node_prompts(project_dir: Path, story_path: Path | None = None) -> None:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = json.loads(story_path.read_text(encoding="utf-8"))
    meta = story.get("meta") or {}
    q = meta.get("questionnaire") or {}
    aspect_ratio = q.get("aspect_ratio", "横版16:9")
    duration_default = int((meta.get("videoDefaults") or {}).get("durationSeconds") or 6)
    seg_default = 2

    changed = False
    for node in story.get("nodes") or []:
        media = node.setdefault("media", {})
        changed |= ensure_media_paths(node)
        duration = int(media.get("durationSeconds") or duration_default)
        seg = int(media.get("segmentSeconds") or seg_default)
        if not media.get("scenePrompt"):
            media["scenePrompt"] = build_scene_prompt(story, meta, node, aspect_ratio)
            changed = True
        if not media.get("storyboardPrompt"):
            media["storyboardPrompt"] = build_storyboard_prompt(story, meta, node, aspect_ratio, duration, seg)
            changed = True

    if changed:
        story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

