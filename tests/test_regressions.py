from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ip_game.asset_verify import verify_project_assets
from ip_game.html_build import build_game_html
from ip_game.map_overview import render_map_overview
from ip_game.node_prompts import generate_node_prompts


def _base_story() -> dict:
    return {
        "meta": {
            "title": "测试影游",
            "questionnaire": {
                "visual_style": "电影级 CG 写实",
                "genre": "奇幻冒险",
                "mood": "轻松",
                "aspect_ratio": "横版16:9",
            },
            "deliveryTier": "prototype",
        },
        "startNodeId": "N0",
        "characters": [
            {
                "id": "hero",
                "name": "小主角",
                "appearance": "白色短毛小兽，背小布包",
                "signature": "白毛，小布包",
            }
        ],
        "nodes": [
            {
                "id": "N0",
                "title": "命运开端",
                "description": "主角第一次遇到命运分叉。",
                "narration": "第一段旁白\\n第二句旁白",
                "choices": [{"text": "走向岔路", "to": "N1"}],
                "characterRefs": ["hero"],
            },
            {
                "id": "N1",
                "title": "三条岔路",
                "description": "主角站在三条路前。",
                "choices": [{"text": "奔向结局", "to": "E1"}],
                "characterRefs": ["hero"],
            },
            {
                "id": "E1",
                "title": "结局",
                "description": "故事来到结尾。",
                "endingText": "这是一个测试结局。",
                "isEnding": True,
                "choices": [],
                "characterRefs": ["hero"],
            },
        ],
    }


class RegressionTests(unittest.TestCase):
    def test_generate_node_prompts_handles_bom_and_writes_overview_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            story_path = project / "story.json"
            story_path.write_text(json.dumps(_base_story(), ensure_ascii=False, indent=2), encoding="utf-8-sig")

            generate_node_prompts(project)

            updated = json.loads(story_path.read_text(encoding="utf-8"))
            meta = updated["meta"]
            self.assertIn("posterPrompt", meta)
            self.assertIn("mapOverviewPrompt", meta)
            self.assertEqual(meta["posterPromptVersion"], "ip-game-overview-prompts-v1.2")
            self.assertEqual(meta["mapOverviewPromptVersion"], "ip-game-overview-prompts-v1.2")
            self.assertTrue((project / "assets" / "prompts" / "home_poster.txt").exists())
            self.assertTrue((project / "assets" / "prompts" / "map_overview.txt").exists())

    def test_build_html_uses_new_map_overview_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "story.json").write_text(json.dumps(_base_story(), ensure_ascii=False, indent=2), encoding="utf-8")
            (project / "ui.json").write_text("{}", encoding="utf-8")

            out = build_game_html(project)
            html = out.read_text(encoding="utf-8")

            self.assertIn('id="mapOverviewImage"', html)
            self.assertIn('id="mapButtons"', html)
            self.assertIn("replace(/\\\\n/g, '\\n')", html)
            self.assertNotIn("mapSvg", html)
            self.assertNotIn("mapFlow", html)
            self.assertNotIn("renderMapDiagram", html)

    def test_verify_flags_missing_map_overview_image_when_referenced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            story = _base_story()
            story["meta"]["mapOverviewImage"] = "assets/images/map_overview.png"
            (project / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

            ok, problems = verify_project_assets(project)

            self.assertFalse(ok)
            self.assertTrue(any("meta.mapOverviewImage" in item for item in problems))

    def test_render_map_overview_creates_png_and_updates_story(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            story = _base_story()
            for node in story["nodes"]:
                node_id = node["id"]
                node.setdefault("media", {})["sceneImage"] = f"assets/images/scenes/{node_id}.png"
            (project / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
            scene_dir = project / "assets" / "images" / "scenes"
            scene_dir.mkdir(parents=True, exist_ok=True)
            for node in story["nodes"]:
                img_path = scene_dir / f"{node['id']}.png"
                Image.new("RGB", (1600, 900), "#334455").save(img_path)

            out = render_map_overview(project)

            self.assertTrue(out.exists())
            self.assertEqual(out.suffix.lower(), ".png")
            updated = json.loads((project / "story.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["meta"]["mapOverviewImage"], "assets/images/map_overview.png")


if __name__ == "__main__":
    unittest.main()
