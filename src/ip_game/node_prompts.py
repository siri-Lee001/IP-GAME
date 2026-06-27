from __future__ import annotations

import json
import re
from pathlib import Path

from .map_prompt import write_overview_prompts


PROMPT_VERSION = "ip-game-v1.3.2"


def normalize_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    return s.strip()[:120] if s else "untitled"


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def split_story_units(*values: object) -> list[str]:
    text = " ".join(clean_text(v) for v in values if clean_text(v))
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [p.strip(" ，,：:") for p in parts if p.strip(" ，,：:")]


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
        anchors = []
        for key in (
            "species",
            "age",
            "appearance",
            "faceShape",
            "hairStyle",
            "ageSignal",
            "bodyType",
            "posture",
            "costume",
            "palette",
            "signature",
            "prop",
            "visualState",
        ):
            if ch.get(key):
                anchors.append(f"{key}：{clean_text(ch.get(key))}")
        if anchors:
            line += " 身份锚点：" + "；".join(anchors)
        if ref_paths:
            line += f" 参考图路径：{'；'.join(ref_paths)}"
        refs.append(line)
    return "\n".join(refs)


def build_identity_differentiation_block(story: dict, node: dict) -> str:
    chars = story.get("characters") or []
    id_map = {str(ch.get("id")): ch for ch in chars}
    active = [id_map[str(cid)] for cid in (node.get("characterRefs") or []) if str(cid) in id_map]
    if len(active) <= 1:
        return "本节点只有一个主要角色时，也要保持其脸型、发型、服装、体态和唯一道具在所有关键帧中完全一致。"

    lines = [
        "本节点是多角色画面，必须先把角色设计成“不同的人”，而不是同一张美型脸换衣服。",
        "为每个角色分配并锁定一套独占身份矩阵：脸型轮廓、五官比例、发际线、发型剪影、年龄感、身高体态、姿态语言、服装主色/材质、唯一道具。",
        "两个同性别角色同场时，差异必须更强：一个偏柔和就让另一个偏锋利；一个松散发型就让另一个整齐束发；一个年轻圆润就让另一个成熟棱角。",
        "女性角色不得被画成男性角色的同脸柔化版；男性角色之间不得像兄弟、双胞胎或同一演员换装。",
        "左侧身份参考区必须额外放每个主要角色的清晰头像锚点 + 全身三视图，用来帮助后续单参考图视频 API 稳定认脸。",
        "右侧 9 个关键帧里，每个角色都必须沿用自己的身份矩阵，不得换脸、换发型、换年龄、换体型、互换服装主色或丢失唯一道具。",
        "",
        "角色差异矩阵（逐个锁定）：",
    ]
    for idx, ch in enumerate(active, 1):
        anchors = []
        for key in (
            "age",
            "appearance",
            "faceShape",
            "hairStyle",
            "ageSignal",
            "bodyType",
            "posture",
            "costume",
            "palette",
            "signature",
            "prop",
            "visualState",
        ):
            if ch.get(key):
                anchors.append(clean_text(ch.get(key)))
        anchor_text = "；".join(anchors) if anchors else "根据角色小传自动推断，但必须和其他角色明显不同"
        lines.append(
            f"{idx}. {ch.get('name') or ch.get('id')}：{anchor_text}。"
            "请明确区分其脸型、发型剪影、年龄感、姿态语言、服装轮廓和唯一道具。"
        )
    return "\n".join(lines)


def build_keyframe_list(node: dict, duration_seconds: int) -> str:
    title = clean_text(node.get("title")) or "剧情节点"
    desc = clean_text(node.get("description"))
    narration = clean_text(node.get("narration"))
    dialogue = clean_text(node.get("dialogue"))
    ending = clean_text(node.get("endingText"))
    choices = " / ".join(clean_text(c.get("text")) for c in (node.get("choices") or []) if clean_text(c.get("text")))
    units = split_story_units(desc, narration, dialogue, ending)
    if not units:
        units = [title]

    fallbacks = [
        desc or title,
        narration or desc or title,
        "主要角色进入本段核心行动，关键道具和场景冲突同时出现",
        "角色关系和情绪压力升级，观众能看出谁在主动、谁在被动",
        "角色与道具或环境发生明确互动，动作线清楚可读",
        "用眼神、表情或手部动作强调本段最重要的情绪变化",
        "角色作出行动选择，身体姿态从犹豫转为明确",
        "环境、旁观者或光影对角色行动产生反应",
        choices or ending or "角色停在通往下一节点的关键姿态上",
    ]

    def unit(index: int) -> str:
        if index < len(units):
            return units[index]
        return fallbacks[min(index, len(fallbacks) - 1)]

    beats = [
        ("01/09", "全景，固定镜头", f"建立{title}的场景空间、时间和主要光源；角色以全身或大半身入画。动作：{unit(0)}"),
        ("02/09", "中全景，缓慢推镜头", f"角色进入主要行动位置，环境中的关键道具或冲突被观众看见。动作：{unit(1)}"),
        ("03/09", "中景，轻微横移镜头", f"角色开始执行本段核心动作，身体姿态和服装轮廓保持清楚。动作：{unit(2)}"),
        ("04/09", "近中景，跟拍镜头", f"矛盾升级或关系变化出现；允许更近的情绪镜头，但脸型、发型和服装不得漂移。动作：{unit(3)}"),
        ("05/09", "全身动作镜头，稳定构图", f"展示角色与道具/场景的互动，人物从头到脚尽量完整可见。动作：{unit(4)}"),
        ("06/09", "近景或半身特写，柔和推镜", f"强调眼神、表情或手部道具；这是唯一可偏近的情绪帧，仍必须保持身份一致。动作：{unit(5)}"),
        ("07/09", "中全景，跟拍或拉镜头", f"角色作出行动或转折，画面从情绪回到叙事推进。动作：{unit(6)}"),
        ("08/09", "大全景，升镜或横移", f"展示行动造成的结果、场景变化或群体反应。动作：{unit(7)}"),
        ("09/09", "远景或收束镜头，固定构图", f"收束到下一节点/结局前的关键姿态。动作：{choices or unit(8)}"),
    ]
    return "\n".join(f"- {num}：{shot}。{text}" for num, shot, text in beats)


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
    identity_block = build_identity_differentiation_block(story, node)

    seg = max(1, int(segment_seconds))
    frame_count = max(6, min(12, int(duration_seconds // seg) + 6))
    keyframes = build_keyframe_list(node, duration_seconds)

    return f"""视频参考合成故事板图片（{aspect_ratio}，用于后续视频生成参考，兼容单参考图视频 API）：

风格：{style}；色调：{tone}；情绪：{mood}。
节点：{title}
节点时长：{duration_seconds}s；故事板分段：{seg}s/段（用于拆镜头，不要在画面里写字）。

导演级核心命令（严格执行）：
1) 生成一张“视频参考合成故事板大图”，不是普通插画，不是网页 UI，不是流程图。
2) 画面布局：左侧 24%-30% 是角色/道具身份参考区；右侧 70%-76% 是 3x3 网格，共 9 个连续关键帧。
3) 左侧身份参考区必须包含本节点主要角色的全身三视图（正面/侧面/背面，从头到脚）和关键道具缩略图；如果角色较多，优先放本节点最重要的 1-3 个角色。
4) 右侧 9 个关键帧按从左到右、从上到下阅读，形成连续叙事；每帧都要能看出动作、情绪、场景和镜头推进。
5) 关键帧中的角色优先全身或大半身可见，尤其是动作帧必须从头到脚尽量完整；允许 1-2 帧近景/半身情绪镜头，但不得变脸、换发型、换衣服或丢失关键道具。
6) 角色造型在身份参考区、9 个关键帧、不同故事板之间必须完全一致；禁止融合脸、同款脸、同款发型、服装互换、年龄漂移、性别漂移。
7) 本图后续可能作为“单参考图”传给视频 API，所以左侧身份参考区必须清晰、明亮、可识别，不能被背景或特效淹没。
8) 禁止出现任何可读文字，包括字幕、编号、注释、标签、logo、水印和 UI 叠层；下方关键帧列表只是给你理解镜头，不要画进画面。

角色差异强化指令（严格执行）：
{identity_block}

剧情素材（用于镜头拆解，按时间顺序）：
description：{desc}
{script or "（无对白与旁白，按场景描述自行拆镜头）"}

角色一致性参考（严格执行）：
{char_block or "（未显式指定角色参考；如项目里已有角色定妆图，仍应优先沿用）"}

光影强制指令：
- 严格遵守剧情中的光线元素，例如月光、阳光、火光、灯光、灵气光、舞台光。
- 画面必须明亮、通透、层次清楚，禁止把“电影感”误处理成低光、脏暗、高反差黑影。
- 若剧情是白天、室外自然光、舞台明亮、仙侠灵气等场景，整体亮度保持在 70% 以上；若剧情写明月光或夜景，也要采用高调柔和照明，让角色脸、服装和道具清楚可见。
- 执行剧本中的色彩主调，不要自动生成暗色版本。

关键帧列表（请按这些镜头理解画面，不要在画面中生成文字、字幕或编号）：
{keyframes}

镜头语言与构图建议：
- 以国际电影导演分镜标准处理节奏：建立场景 → 推进动作 → 情绪转折 → 结果收束。
- 构图主体明确，留白有节奏，前中后景层次清晰；每格都有不同景别和镜头运动感。
- 情绪必须可见：每格都要能看出角色当下选择、压力、关系变化或反转。
- 质感高细节、清晰、通透，不要糊、不要噪点、不要塑料感。

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
    story = json.loads(story_path.read_text(encoding="utf-8-sig"))
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

    write_overview_prompts(project_dir, story_path=story_path)

