from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


@dataclass
class TreeEdge:
    text: str
    node: "TreeNode"


@dataclass
class TreeNode:
    id: str
    title: str
    is_ending: bool
    image_path: Path | None
    children: list[TreeEdge]
    row: float = 0.0
    depth: int = 0


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _project_rel(path: Path, project_dir: Path) -> str:
    return path.resolve().relative_to(project_dir.resolve()).as_posix()


def _font(size: int, bold: bool = False, serif: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[str] = []
    if serif:
        candidates += [
            r"C:\Windows\Fonts\STKAITI.TTF",
            r"C:\Windows\Fonts\simkai.ttf",
            r"C:\Windows\Fonts\STSONG.TTF",
            r"C:\Windows\Fonts\simsun.ttc",
        ]
    if bold:
        candidates += [
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\STXIHEI.TTF",
        ]
    candidates += [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _soft_rect_mask(size: tuple[int, int], border: int = 160) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((border, border, size[0] - border, size[1] - border), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(border * 0.55))


def _normalize(text: str | None) -> str:
    return str(text or "").replace("\\n", "\n").strip()


def _build_tree(story: dict, project_dir: Path) -> TreeNode | None:
    node_map = {str(node.get("id")): node for node in (story.get("nodes") or []) if node.get("id")}
    start_id = str(story.get("startNodeId") or next(iter(node_map), ""))
    if not start_id or start_id not in node_map:
        return None

    def build(node_id: str, seen: set[str]) -> TreeNode | None:
        if node_id in seen:
            return None
        raw = node_map.get(node_id)
        if not raw:
            return None
        media = raw.get("media") or {}
        image_rel = media.get("sceneImage") or media.get("poster") or media.get("endingImage")
        image_path = (project_dir / image_rel).resolve() if image_rel else None
        next_seen = set(seen)
        next_seen.add(node_id)
        children: list[TreeEdge] = []
        for choice in raw.get("choices") or []:
            child = build(str(choice.get("to") or ""), next_seen)
            if child is not None:
                children.append(TreeEdge(text=_normalize(choice.get("text")), node=child))
        return TreeNode(
            id=node_id,
            title=str(raw.get("title") or node_id),
            is_ending=bool(raw.get("isEnding")),
            image_path=image_path if image_path and image_path.exists() else None,
            children=children,
        )

    return build(start_id, set())


def _layout_tree(root: TreeNode) -> tuple[int, int]:
    max_depth = 0
    leaf_index = 0

    def walk(node: TreeNode, depth: int) -> None:
        nonlocal max_depth, leaf_index
        node.depth = depth
        max_depth = max(max_depth, depth)
        if not node.children:
            node.row = float(leaf_index)
            leaf_index += 1
            return
        for edge in node.children:
            walk(edge.node, depth + 1)
        node.row = sum(edge.node.row for edge in node.children) / len(node.children)

    walk(root, 0)
    return max_depth, max(leaf_index, 1)


def _collect_nodes(root: TreeNode) -> list[TreeNode]:
    nodes: list[TreeNode] = []

    def walk(node: TreeNode) -> None:
        nodes.append(node)
        for edge in node.children:
            walk(edge.node)

    walk(root)
    return nodes


def _sample_bezier(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], steps: int = 120) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        mt = 1 - t
        x = (
            mt * mt * mt * p0[0]
            + 3 * mt * mt * t * p1[0]
            + 3 * mt * t * t * p2[0]
            + t * t * t * p3[0]
        )
        y = (
            mt * mt * mt * p0[1]
            + 3 * mt * mt * t * p1[1]
            + 3 * mt * t * t * p2[1]
            + t * t * t * p3[1]
        )
        points.append((x, y))
    return points


def _text_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="center")
    x = box[0] + (box[2] - box[0] - (bbox[2] - bbox[0])) / 2
    y = box[1] + (box[3] - box[1] - (bbox[3] - bbox[1])) / 2 - 1
    draw.multiline_text((x, y), text, font=font, fill=fill, spacing=4, align="center")


def render_map_overview(project_dir: Path, story_path: Path | None = None, out_path: Path | None = None) -> Path:
    project_dir = project_dir.resolve()
    story_path = (story_path or (project_dir / "story.json")).resolve()
    out_path = (out_path or (project_dir / "assets" / "images" / "map_overview.png")).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    story = _read_json(story_path)
    root = _build_tree(story, project_dir)
    if root is None:
        raise ValueError("story.json does not contain a valid start node")

    max_depth, leaf_count = _layout_tree(root)
    all_nodes = _collect_nodes(root)

    width = 2048
    height = max(1240, 340 + leaf_count * 160)
    pad_x = 92
    pad_y = 138
    x_gap = 430
    row_gap = max(150, (height - pad_y * 2 - 180) // max(leaf_count - 1, 1))
    story_size = (280, 158)
    ending_size = (220, 124)

    scene_candidates = [
        node.image_path for node in all_nodes if node.image_path is not None
    ]
    if not scene_candidates:
        background = Image.new("RGB", (width, height), "#11161f")
    else:
        background = _cover(Image.open(scene_candidates[0]), (width, height))
    background = ImageEnhance.Color(background).enhance(0.86)
    background = ImageEnhance.Brightness(background).enhance(0.58)

    for index, candidate in enumerate(scene_candidates[1:4], start=1):
        overlay = _cover(Image.open(candidate), (width, height))
        overlay = ImageEnhance.Color(overlay).enhance(0.74)
        overlay = ImageEnhance.Brightness(overlay).enhance(0.48)
        overlay = overlay.filter(ImageFilter.GaussianBlur(12 + index * 2))
        masked = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        masked.paste(overlay.convert("RGBA"), (0, 0))
        mask = _soft_rect_mask((width, height), border=150 + index * 18)
        background = Image.composite(masked.convert("RGB"), background, mask)

    bg = background.convert("RGBA")
    shade = Image.new("RGBA", (width, height), (10, 16, 24, 78))
    bg = Image.alpha_composite(bg, shade)

    vignette = Image.new("L", (width, height), 0)
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_draw.ellipse((-220, -140, width + 220, height + 200), fill=220)
    vignette = ImageChops.invert(vignette.filter(ImageFilter.GaussianBlur(180)))
    bg = Image.composite(Image.new("RGBA", (width, height), (4, 8, 14, 255)), bg, vignette)

    draw_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(draw_layer)
    glow_draw = ImageDraw.Draw(glow_layer)

    title_font = _font(56, bold=True, serif=True)
    subtitle_font = _font(26, serif=True)
    body_font = _font(24, bold=True)
    small_font = _font(18, bold=True)
    plaque_font = _font(26, bold=True, serif=True)
    tiny_font = _font(16, bold=True)

    def card_rect(node: TreeNode) -> tuple[int, int, int, int]:
        w, h = ending_size if node.is_ending else story_size
        x = int(pad_x + node.depth * x_gap)
        y = int(pad_y + node.row * row_gap)
        return (x, y, x + w, y + h)

    gold = ImageColor.getrgb("#E5C57B")
    gold_soft = ImageColor.getrgb("#A7864B")
    cream = ImageColor.getrgb("#F8F0D8")

    for node in all_nodes:
        for edge in node.children:
            src = card_rect(node)
            dst = card_rect(edge.node)
            src_w = src[2] - src[0]
            src_h = src[3] - src[1]
            dst_h = dst[3] - dst[1]
            p0 = (src[2] - 8, src[1] + src_h * 0.5)
            p1 = (src[2] + 80, src[1] + src_h * 0.5)
            p2 = (dst[0] - 80, dst[1] + dst_h * 0.5)
            p3 = (dst[0] + 8, dst[1] + dst_h * 0.5)
            points = _sample_bezier(p0, p1, p2, p3, steps=90)
            for radius, alpha in [(18, 26), (10, 44), (6, 80)]:
                for x, y in points[::3]:
                    glow_draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(245, 203, 118, alpha))
            draw.line(points, fill=(229, 197, 123, 204), width=4, joint="curve")

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(8))
    bg = Image.alpha_composite(bg, glow_layer)
    bg = Image.alpha_composite(bg, draw_layer)

    frame = ImageDraw.Draw(bg)
    frame.rounded_rectangle((24, 24, width - 24, height - 24), radius=26, outline=(224, 196, 134, 108), width=2)

    title_box = (58, 48, 520, 240)
    frame.rounded_rectangle(title_box, radius=32, fill=(11, 16, 23, 170), outline=(224, 196, 134, 170), width=2)
    title = str((story.get("meta") or {}).get("title") or "互动影游")
    frame.text((title_box[0] + 24, title_box[1] + 24), "游戏路径全览", font=subtitle_font, fill=(236, 211, 153, 255))
    frame.text((title_box[0] + 24, title_box[1] + 62), title, font=title_font, fill=(250, 243, 224, 255))
    stats = f"{sum(1 for node in all_nodes if not node.is_ending)} 个剧情节点  ·  {sum(1 for node in all_nodes if node.is_ending)} 个结局"
    frame.text((title_box[0] + 24, title_box[1] + 146), stats, font=body_font, fill=(226, 213, 186, 238))
    frame.text((title_box[0] + 24, title_box[1] + 182), "从起点出发，沿三条修行路线改写兔生。", font=small_font, fill=(202, 191, 169, 230))

    def paste_card(node: TreeNode) -> None:
        rect = card_rect(node)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        shadow = Image.new("RGBA", (w + 26, h + 48), (0, 0, 0, 0))
        shadow_mask = _rounded_mask((w, h), 24 if not node.is_ending else 20)
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 180))
        shadow.paste(shadow_layer, (10, 12), shadow_mask)
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        bg.alpha_composite(shadow, (rect[0] - 12, rect[1] - 10))

        card = Image.new("RGBA", (w, h), (18, 24, 34, 236))
        if node.image_path and node.image_path.exists():
            art = _cover(Image.open(node.image_path), (w, h))
            art = ImageEnhance.Color(art).enhance(0.96)
            art = ImageEnhance.Brightness(art).enhance(0.92)
            card = art.convert("RGBA")
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=24 if not node.is_ending else 20, fill=(0, 0, 0, 0), outline=(224, 196, 134, 180), width=2)
        overlay_draw.rectangle((0, int(h * 0.58), w, h), fill=(8, 13, 22, 168))
        card = Image.alpha_composite(card, overlay)

        mask = _rounded_mask((w, h), 24 if not node.is_ending else 20)
        bg.paste(card, (rect[0], rect[1]), mask)

        draw_card = ImageDraw.Draw(bg)
        id_chip_w = 54 if node.is_ending else 62
        chip = (rect[0] + 16, rect[1] + 14, rect[0] + 16 + id_chip_w, rect[1] + 42)
        chip_fill = (92, 117, 197, 210) if node.depth == 0 else ((83, 163, 122, 206) if not node.is_ending else (160, 111, 63, 210))
        draw_card.rounded_rectangle(chip, radius=14, fill=chip_fill, outline=(255, 255, 255, 48), width=1)
        _text_center(draw_card, chip, node.id, tiny_font, "#F6F3EA")

        title_lines = [node.title]
        if node.is_ending and len(node.title) > 8:
            title_lines = [node.title[:8], node.title[8:16]]
        elif not node.is_ending and len(node.title) > 10:
            title_lines = [node.title[:10], node.title[10:20]]
        text_box = (rect[0] + 16, rect[1] + int(h * 0.62), rect[2] - 16, rect[3] - 12)
        _text_center(draw_card, text_box, "\n".join(title_lines[:2]), plaque_font if not node.is_ending else body_font, "#F8F0D8")

    for node in all_nodes:
        paste_card(node)

    out_rgb = bg.convert("RGB")
    if out_path.suffix.lower() == ".png":
        out_rgb.save(out_path)
    else:
        out_rgb.save(out_path, quality=94)

    meta = story.setdefault("meta", {})
    meta["mapOverviewImage"] = _project_rel(out_path, project_dir)
    _write_json(story_path, story)
    return out_path
