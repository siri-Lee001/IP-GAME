from __future__ import annotations

import json
import re
from pathlib import Path


PROMPT_VERSION = "ip-game-v1.2"


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
    return f"""互动影游节点场景图（{aspect_ratio}，用于网页海报、节点开场和视频首帧）：

风格：{style}；色调：{tone}；整体情绪：{mood}。
节点：{title}
场景描述：{desc}

角色一致性要求：
{char_block or "未显式指定角色；如项目已有角色定妆图，仍应优先沿用。"}

画面要求：
1) 电影级单张场景图，主体明确，角色与环境都要有叙事信息。
2) 若角色出现，尽量呈现全身或大半身，不要只给脸部特写。
3) 构图清晰，层次明确，明亮通透，避免过暗、糊、噪点和低对比。
4) 光影必须服务剧情情绪，保留仙侠/互动短剧的戏剧张力。
5) 禁止任何可读文字、字幕、编号、logo、水印、UI 边框。
6) 高细节，高质感，可直接作为网页 poster 或视频首帧参考。
"""


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

    return f"""故事板图片（{aspect_ratio}，用于后续视频生成参考）：

风格：{style}；色调：{tone}；情绪：{mood}。
节点：{title}
节点时长：{duration_seconds}s；故事板分段：{seg}s/段（用于拆镜头，不要在画面里写字）。

核心要求（严格执行）：
1) 生成一张“电影级故事板大图”，主区域为 3x3 网格，共 9 个连续关键帧。
2) 左侧附加角色/道具参考区：主要角色全身三视图（正/侧/背，必须从头到脚）+ 核心道具缩略图。
3) 所有关键帧必须保持同一角色身份一致：不变脸、不换发型、不换服装体系、不丢关键道具。
4) 镜头顺序从左到右、从上到下，形成连续叙事；景别要有全景/中景/近景/特写变化。
5) 光影必须明亮、通透、层次清楚；严格遵守剧情中的光源，禁止低光、脏暗、重阴影导致看不清。
6) 禁止出现任何可读文字，包括字幕、编号、注释、标签、logo、水印和 UI 叠层。

剧情素材（用于镜头拆解，按时间顺序）：
description：{desc}
{script or "（无对白与旁白，按场景描述自行拆镜头）"}

角色一致性参考（严格执行）：
{char_block or "（未显式指定角色参考；如项目里已有角色定妆图，仍应优先沿用）"}

镜头语言建议：
- 节奏：从全景建立场景 → 中景推进动作 → 近景强调表情/道具 → 收束回全景或关键姿态。
- 构图：主体明确，留白有节奏，前中后景层次清晰。
- 情绪：每格都要能看出角色当下选择、压力或反转。
- 质感：高细节、清晰、电影感，不要糊、不要噪点、不要塑料感。

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

    if node.get("isEnding") is True and not media.get("endingImage"):
        media["endingImage"] = f"assets/images/endings/{nid}.jpg"
        changed = True

    if media.get("sceneImage") and not media.get("poster"):
        media["poster"] = media.get("sceneImage")
        changed = True

    prefer = media.get("storyboardImage") or media.get("sceneImage") or media.get("poster")
    if prefer and media.get("videoRefImage") != prefer:
        media["videoRefImage"] = prefer
        changed = True

    if not media.get("video"):
        media["video"] = f"assets/videos/{nid}.mp4"
        changed = True

    if not media.get("storyboardSegmentSeconds"):
        duration = int(media.get("durationSeconds") or 6)
        media["storyboardSegmentSeconds"] = max(3, min(8, duration))
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
    seg_default = 6
    prompt_dir = project_dir / "assets" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    changed = False
    for node in story.get("nodes") or []:
        media = node.setdefault("media", {})
        changed |= ensure_media_paths(node)
        duration = int(media.get("durationSeconds") or duration_default)
        seg = int(media.get("storyboardSegmentSeconds") or media.get("segmentSeconds") or seg_default)
        regenerate = (media.get("promptVersion") != PROMPT_VERSION) and not media.get("promptLocked")
        if not media.get("scenePrompt") or regenerate:
            media["scenePrompt"] = build_scene_prompt(story, meta, node, aspect_ratio)
            changed = True
        if not media.get("storyboardPrompt") or regenerate:
            media["storyboardPrompt"] = build_storyboard_prompt(story, meta, node, aspect_ratio, duration, seg)
            media["promptVersion"] = PROMPT_VERSION
            changed = True
        nid = normalize_filename(node.get("id") or node.get("title") or "node")
        (prompt_dir / f"{nid}_scene.txt").write_text(media["scenePrompt"], encoding="utf-8")
        (prompt_dir / f"{nid}_storyboard.txt").write_text(media["storyboardPrompt"], encoding="utf-8")

    if changed:
        story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

