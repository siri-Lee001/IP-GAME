from __future__ import annotations

import json
import re
from pathlib import Path


PROMPT_VERSION = "ip-game-overview-prompts-v1.2"


def normalize_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    return s.strip()[:120] if s else "untitled"


def _normalize(text: str | None) -> str:
    return str(text or "").replace("\\n", "\n").strip()


def _read_story(story_path: Path) -> dict:
    return json.loads(story_path.read_text(encoding="utf-8-sig"))


def _route_lines(story: dict) -> list[str]:
    node_map = {str(node.get("id")): node for node in (story.get("nodes") or []) if node.get("id")}
    start_id = str(story.get("startNodeId") or next(iter(node_map), ""))
    if not start_id or start_id not in node_map:
        return []

    lines: list[str] = []
    visited: set[str] = set()

    def walk(node_id: str, prefix: str) -> None:
        if node_id in visited:
            return
        node = node_map.get(node_id)
        if not node:
            return
        visited.add(node_id)
        title = str(node.get("title") or node_id)
        choices = node.get("choices") or []
        if not choices:
            lines.append(f"{prefix}{node_id} {title}")
            return
        if node_id == start_id:
            lines.append(f"起点：{node_id} {title}")
        for index, choice in enumerate(choices, start=1):
            to_id = str(choice.get("to") or "")
            target = node_map.get(to_id) or {}
            target_title = str(target.get("title") or to_id)
            branch_label = f"路线{index}" if len(choices) > 1 and node_id == start_id else "分支"
            choice_text = _normalize(choice.get("text"))
            lines.append(f"{prefix}{node_id} {title} -> {choice_text or branch_label} -> {to_id} {target_title}")
            walk(to_id, prefix + "  ")

    walk(start_id, "")
    return lines


def _landmark_lines(story: dict) -> list[str]:
    result: list[str] = []
    for node in story.get("nodes") or []:
        node_id = str(node.get("id") or "")
        title = str(node.get("title") or node_id)
        desc = _normalize(node.get("description")) or _normalize(node.get("endingText")) or _normalize(node.get("narration"))
        if node_id and title and desc:
            result.append(f"- {node_id} {title}：{desc}")
    return result


def _hero_node(story: dict) -> dict:
    nodes = [node for node in (story.get("nodes") or []) if node.get("id")]
    if not nodes:
        return {}
    start_id = str(story.get("startNodeId") or nodes[0].get("id") or "")
    node_map = {str(node.get("id")): node for node in nodes}
    start = node_map.get(start_id) or nodes[0]
    branching = [
        node
        for node in nodes
        if not node.get("isEnding") and len(node.get("choices") or []) >= 2
    ]
    return branching[0] if branching else start


def _character_anchor_lines(story: dict, limit: int = 3) -> list[str]:
    lines: list[str] = []
    for ch in (story.get("characters") or [])[:limit]:
        name = str(ch.get("name") or "").strip()
        appearance = _normalize(ch.get("appearance") or ch.get("signature") or ch.get("bio"))
        if name and appearance:
            lines.append(f"- {name}：{appearance}")
        elif name:
            lines.append(f"- {name}：保持既定角色身份锚点与造型特征")
    return lines


def build_home_poster_prompt(story: dict) -> str:
    meta = story.get("meta") or {}
    q = meta.get("questionnaire") or {}
    title = str(meta.get("title") or "互动影游")
    visual_style = _normalize(q.get("visual_style")) or "沿用本项目已确认的视觉风格，不要固定成某一种默认风格"
    genre = _normalize(q.get("genre")) or "按故事题材自然匹配"
    mood = _normalize(q.get("mood")) or "按故事情绪自然匹配"
    color_tone = _normalize(q.get("color_tone")) or "按故事世界观自行匹配高级配色"
    aspect = _normalize(q.get("aspect_ratio")) or "横版16:9"
    hero = _hero_node(story)
    hero_title = str(hero.get("title") or "故事主场景")
    hero_desc = _normalize(hero.get("description")) or "围绕主角、世界观和核心冲突，设计一张足够抓人的首页海报主视觉。"
    character_block = "\n".join(_character_anchor_lines(story)) or "- 主要角色：沿用已确认角色身份锚点与造型特征"
    notes = _normalize((q.get("notes") or meta.get("tagline") or meta.get("synopsis")))

    return f"""为互动影游《{title}》生成一张 首页海报主视觉。

这是一张高端游戏首页海报，不是章节截图，不是流程图，不是拼贴卡片，不是网页 UI 截图。它必须像成熟互动影游的封面 key art：一眼能看出题材、气质、主角和核心冲突，同时给网页标题与按钮留出安全区域。

风格要求：
- 视觉风格：{visual_style}
- 题材气质：{genre}
- 情绪氛围：{mood}
- 配色方向：{color_tone}
- 画面比例：{aspect}
- 重点：不要套固定海报风格模板，要严格跟随当前项目已确认的风格、题材、情绪和世界观

海报核心：
- 标题：{title}
- 核心场景：{hero_title}
- 剧情重点：{hero_desc}
{f"- 补充限制：{notes}" if notes else ""}

主要角色锚点：
{character_block}

构图要求：
1. 海报必须以一张完整的电影级主画面为中心，不要拼贴，不要多卡片，不要把信息拆碎。
2. 画面需要明确主角、主舞台和核心冲突，最好让观众一眼看出“这是一个怎样的故事”。
3. 给标题和开始按钮预留清晰、安全、可覆盖的区域；安全区可以在左侧、下方或中下部，但不能破坏主视觉。
4. 角色要足够醒目，但不能把画面挤满；环境必须承担世界观叙事。
5. 允许使用戏剧性光影、体积光、氛围雾、景深和高低空间层次，让海报看起来昂贵、完整、专业。
6. 必须避免文字杂讯、可读字符、UI 元素、水印、logo、编号和字幕。

美术关键词：
premium game poster key art，interactive film cover art，cinematic homepage hero image，story-first composition，clear focal hierarchy，high-end game marketing art，immersive worldbuilding，polished lighting，safe title area，premium visual storytelling

绝对禁止：
网页截图，按钮卡片拼贴，角色堆满画面，构图拥挤，标题安全区缺失，低清晰度，灰脏糊，廉价手游感，现代扁平UI，文字脏点，水印，logo。
"""


def build_map_overview_prompt(story: dict) -> str:
    meta = story.get("meta") or {}
    q = meta.get("questionnaire") or {}
    title = str(meta.get("title") or "互动影游")
    visual_style = _normalize(q.get("visual_style")) or "沿用本项目已确认的视觉风格，不要固定成某一种默认风格"
    genre = _normalize(q.get("genre")) or "按故事题材自然匹配"
    mood = _normalize(q.get("mood")) or "按故事情绪自然匹配"
    color_tone = _normalize(q.get("color_tone")) or "按故事世界观自行匹配高级配色"
    aspect = _normalize(q.get("aspect_ratio")) or "横版16:9"

    route_lines = _route_lines(story)
    landmark_lines = _landmark_lines(story)

    route_block = "\n".join(route_lines) if route_lines else "根据 story.json 的起点、分支和结局关系，自行整理清楚的路径层级。"
    landmark_block = "\n".join(landmark_lines) if landmark_lines else "根据每个节点的标题、简介、旁白和结局信息，把每个节点设计成独立章节地标。"

    return f"""为互动影游《{title}》生成一张 高定游戏CG密集信息路径图 主视觉。

这不是普通地图，不是网页截图，不是流程图，不是思维导图，不是信息图表，而是一张电影级、商业级、可直接用于游戏“章节地图页”的 fantasy route overview key art。

风格要求：
- 视觉风格：{visual_style}
- 题材气质：{genre}
- 情绪氛围：{mood}
- 配色方向：{color_tone}
- 画面比例：{aspect}
- 重点：不要把风格锁死成固定模板，要严格跟随当前故事项目的已确认风格、题材、情绪和世界观

核心目标：
生成一张“完整世界观场景 + 清晰章节路径 + 高密度信息地标”的游戏路径总览图。
整张图必须像成熟互动影游或RPG游戏里的章节总览主视觉，既好看、华丽、专业，也让玩家一眼能看懂从哪里开始、会分成哪些路线、每条路线最终通往哪些结局。

路径结构文字：
{route_block}

节点地标说明：
{landmark_block}

画面构图要求：
1. 整张图必须是一张完整的大世界主视觉，不是多个矩形卡片拼贴。
2. 用地形、建筑、桥梁、石阶、灵气流线、道路、发光轨迹、路标、灯火等方式，把起点、主枢纽、分支和终点自然连接起来。
3. 主路径和分支必须一眼可读，阅读顺序明确：起点 -> 主枢纽/主干 -> 分支路线 -> 结局终点。
4. 每个节点都应是“独立章节地标”，像可探索地点，而不是方框、线框、思维导图节点。
5. 远看先读懂路径逻辑，近看再看到每个节点自己的叙事细节。
6. 允许在节点周围出现角色小型演出，但角色只作为点睛，不要让人物堆满全图，不要复制粘贴感。
7. 层次一定要丰富：近景、中景、远景，地势高低变化，空气透视、体积光、云雾、自然光影、局部高亮。
8. 整体要像“高定游戏CG密集信息路径图”，不是单纯风景画。

信息呈现要求：
1. 路径本身必须漂亮，有高级的引导感，可以是发光道路、金色轨迹、灵气路线、光点路标等。
2. 每个节点附近要留出适合放章节标题的视觉区域，例如牌匾、卷轴、石碑、悬浮铭牌、地标标签。
3. 如果模型支持文字能力，可生成高级章节名牌匾；如果模型文字能力一般，则生成精致的牌匾占位，不强求可读文字。

美术关键词：
高定游戏CG密集信息路径图，chapter route overview key art，premium game chapter map，interactive story route overview，fantasy world path illustration，dense visual storytelling，readable branching progression，cinematic game environment art，luxury game concept art，rich atmosphere，clear route logic

绝对禁止：
流程图，思维导图，办公信息图，网页截图，现代UI面板，漂浮矩形卡片，廉价手游界面，拼贴海报，节点方框，混乱连线，路径不可读，角色重复复制，廉价质感，塑料感，低清晰度，糊，脏，灰，乱。
"""


def write_overview_prompts(project_dir: Path, story_path: Path | None = None) -> tuple[Path, Path]:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    story = _read_story(story_path)
    poster_prompt = build_home_poster_prompt(story)
    map_prompt = build_map_overview_prompt(story)
    meta = story.setdefault("meta", {})
    meta["posterPrompt"] = poster_prompt
    meta["posterPromptVersion"] = PROMPT_VERSION
    meta["mapOverviewPrompt"] = map_prompt
    meta["mapOverviewPromptVersion"] = PROMPT_VERSION
    if not meta.get("mapOverviewImage"):
        meta["mapOverviewImage"] = "assets/images/map_overview.png"
    story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

    prompt_dir = project_dir / "assets" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    poster_out = prompt_dir / "home_poster.txt"
    map_out = prompt_dir / "map_overview.txt"
    poster_out.write_text(poster_prompt, encoding="utf-8")
    map_out.write_text(map_prompt, encoding="utf-8")
    return poster_out, map_out


def write_map_overview_prompt(project_dir: Path, story_path: Path | None = None) -> Path:
    _, map_out = write_overview_prompts(project_dir, story_path=story_path)
    return map_out
