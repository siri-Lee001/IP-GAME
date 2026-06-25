from __future__ import annotations

import json
import re
from pathlib import Path


PROMPT_VERSION = "ip-game-character-v1.2"


def normalize_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    return s.strip()[:120] if s else "untitled"


def infer_kind(ch: dict) -> str:
    text = " ".join(
        [
            str(ch.get("name") or ""),
            str(ch.get("bio") or ""),
            str(ch.get("appearance") or ""),
            str(ch.get("personality") or ""),
        ]
    )
    t = text.lower()
    if any(k in text for k in ["少女", "男孩", "女孩", "少年", "青年", "中年", "老人", "凡人", "人类", "女子", "男子"]):
        return "人类角色"
    if any(k in text for k in ["鸟", "雀", "鹰", "凤", "鸦"]) or "bird" in t:
        return "鸟类角色"
    if any(k in text for k in ["狐", "狼", "猫", "狗", "虎", "龟", "兔", "鹿", "兽"]) or "animal" in t:
        return "动物/灵兽角色"
    if any(k in text for k in ["龙", "麒麟", "妖怪", "妖族", "魔族", "魔物", "神兽", "精灵", "异兽"]) or "monster" in t:
        return "妖怪/神异生物角色"
    if any(k in text for k in ["机关", "机器人", "机甲"]) or "robot" in t:
        return "机器人/机关角色"
    return "人类或拟人角色"


def build_prompt(meta: dict, ch: dict) -> str:
    q = meta.get("questionnaire") or {}
    style = q.get("visual_style", "CG写实")
    name = ch.get("name", "角色")
    kind = infer_kind(ch)
    age_temperament = f"{ch.get('age', '年龄未明')}，{ch.get('personality', ch.get('bio', '气质待定'))}"
    appearance = ch.get("appearance") or ch.get("bio") or ""
    identity_markers = "、".join(ch.get("consistencyKeywords") or []) or "保持同一角色识别特征"
    refs = ch.get("referenceImages") or []
    src_strategy = (ch.get("imageSourceStrategy") or "").strip() or ("local" if refs else "generate")
    ref_note = ""
    if src_strategy == "local" and refs:
        ref_note = (
            "\n本角色已提供用户确认过的本地角色参考图，后续节点场景图、故事板图、结局图必须优先沿用这些参考图，"
            "不得擅自重新生成新的角色基准图覆盖掉用户素材。"
            f"\n本地角色参考图：{'；'.join(refs)}"
        )

    return f"""21:9超宽横版角色完整设定卡，纯白干净棚拍背景。

以“{name}”为唯一身份锚点：必须严格保持以下身份特征一致：
- 物种/形态：{kind}
- 年龄感/气质：{age_temperament}
- 面部或头部轮廓：依据以下描述严格还原：{appearance}
- 眼部特征：根据角色描述自动提炼，但必须在全图保持一致
- 鼻口/吻部特征：根据角色描述自动提炼，但必须在全图保持一致
- 发际线、发型结构、毛发/羽毛/耳朵/角/触角/头饰等顶部特征：{appearance}
- 服装、配饰、鞋履或肢体末端装备：{appearance}
- 关键识别点：{identity_markers}

只允许同一个角色，禁止换脸、禁止五官或头部结构漂移、禁止发型/毛发结构简化、禁止头饰缺失、禁止物种特征丢失。
如果角色是动物、神兽、妖怪、机器人或其他非人角色，必须严格保留其原始种属结构与比例，不得擅自人类化。

单张合成图，左中右三分区构图，三区统一光影与色彩，柔光棚拍布光，光源方向一致。

左区（占画面宽度约25%）：
- 角色正面超高清特写
- 构图为头部至胸部/对应身体上半部分
- 头顶所有关键结构完整入画，不裁切
- 眼神平视前方，自然放松，主要视觉器官清晰锐利对焦
- 服装、领口、配饰与角色设定严格一致

中区（占画面宽度约45%）：
- 三张全身站姿图并排排列，头顶与脚底在同一水平线对齐，角色高度一致
- 必须完整呈现角色全身/完整躯体
- 中区左：全身正面站姿，中性站姿
- 中区中：全身 90° 侧面站姿（面朝左），中性站姿
- 中区右：全身背面站姿，中性站姿

右区（占画面宽度约30%）：
- 2列×3行肖像网格，六格等大
- 第一行左：正面朝左45°，无表情
- 第一行右：正背面视图或头部后侧视图
- 第二行左：正面低头30°，无表情
- 第二行右：正面抬头30°，无表情
- 第三行左：正面，开心表情，情绪克制不过度夸张
- 第三行右：正面，生气表情，情绪克制不过度夸张

质感与画质：
- {style}
- 高端写实棚拍 / 电影级角色设定质感
- 真实材质细节，不磨皮不塑料；若非人角色则保持真实羽毛/鳞片/皮毛/金属纹理
- 全图各分区曝光与色彩一致，8K细节，轻胶片颗粒，超干净白底

强约束：
- 画面内不允许任何可读文字、标签、字幕、logo、UI叠层、水印
- 不要多余人物/多余生物
- 不要畸形肢体/多肢体/脸崩/眼神涣散/关键器官缺失
- 全图所有分区必须是同一角色，同一头部结构，同一发型/毛发结构/物种结构
- 表情变化只允许微表情变化，不改变脸型、骨骼、头部结构或物种特征
{ref_note}
"""


def generate_character_prompts(project_dir: Path, story_path: Path | None = None) -> None:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = json.loads(story_path.read_text(encoding="utf-8"))
    meta = story.get("meta") or {}

    prompt_dir = project_dir / "assets" / "prompts" / "characters"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    changed = False
    for ch in story.get("characters") or []:
        images = ch.get("images") or {}
        cid = normalize_filename(ch.get("id") or ch.get("name") or "character")

        refs = ch.get("referenceImages") or []
        src_strategy = (ch.get("imageSourceStrategy") or "").strip() or ("local" if refs else "generate")
        ch["imageSourceStrategy"] = src_strategy

        if src_strategy != "local":
            images.setdefault("sheet", f"assets/images/characters/{cid}_sheet.jpg")
            images.setdefault("front", f"assets/images/characters/{cid}_front.jpg")
            images.setdefault("side", f"assets/images/characters/{cid}_side.jpg")
            images.setdefault("back", f"assets/images/characters/{cid}_back.jpg")
            images.setdefault("face", f"assets/images/characters/{cid}_face.jpg")

        ch["images"] = images
        regenerate = (ch.get("characterPromptVersion") != PROMPT_VERSION) and not ch.get("promptLocked")
        if not ch.get("characterSheetPrompt") or regenerate:
            ch["characterSheetPrompt"] = build_prompt(meta, ch)
            ch["characterPromptVersion"] = PROMPT_VERSION
            changed = True

        (prompt_dir / f"{cid}_sheet.txt").write_text(ch["characterSheetPrompt"], encoding="utf-8")

    if changed:
        story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

