# IP-GAME

IP-GAME is a portable interactive film game generator. It turns a structured `story.json` plus optional `ui.json` into an offline playable `game.html`, and provides helper commands for character prompts, node image prompts, local video fallback, and asset verification.

This repository is designed to be shared as a Codex-style skill or used as a normal Python CLI package.

## What It Does

- Follows a 6-step interactive film SOP: story, smart questions, script confirmation, character references, node images, video source, final package.
- Generates character sheet prompts and node scene/storyboard prompts.
- Fills standard asset paths in `story.json`.
- Builds a richer offline `game.html` with poster page, intro modal, route map, node replay, chapter jump, ending page, and TTS toggle.
- Optionally synthesizes simple local MP4 videos from still images for prototype testing.
- Verifies images, aspect ratio, videos, and final delivery risk.

## Install

Python `>=3.10` is required.

```bash
pip install -U pip
pip install .
```

Development mode:

```bash
pip install -e .
```

For local static video synthesis, make sure ffmpeg is available. The package depends on `imageio-ffmpeg`, which provides a bundled ffmpeg path for common environments.

## Project Layout

```text
<project>/
  story.json
  ui.json
  assets/
    images/
      characters/
      scenes/
      storyboards/
      endings/
    prompts/
      characters/
    videos/
  game.html
```

## Quick Start

Generate prompts and default media paths:

```bash
ip-game generate-character-prompts <project-dir>
ip-game generate-node-prompts <project-dir>
```

Build the playable HTML:

```bash
ip-game build-html <project-dir>
```

Create prototype videos from still images:

```bash
ip-game make-videos <project-dir> --skip-existing
```

Verify before delivery:

```bash
ip-game verify <project-dir>
```

## Commands

```text
ip-game build-html <project-dir> [--story story.json] [--ui ui.json]
ip-game generate-character-prompts <project-dir> [--story story.json]
ip-game generate-node-prompts <project-dir> [--story story.json]
ip-game make-videos <project-dir> [--story story.json] [--only N0,E0] [--skip-existing] [--size 1280x720]
ip-game verify <project-dir> [--story story.json]
```

## Delivery Tiers

Use `story.meta.deliveryTier` to make quality explicit.

- `prototype`: flow test or playable draft. Static-image MP4s and placeholder assets are allowed.
- `final`: production-style delivery. Character references, node images, ending images, aspect ratio consistency, and playable videos are expected.

The verifier is stricter for `final` and flags suspiciously small videos.

## Video API

The CLI does not call any cloud video API by default. A provider reference is included at:

```text
providers/video.provider.json
```

It describes an Aliyun DashScope Wan image-to-video async setup and expects the key in the `DASHSCOPE_API_KEY` environment variable. The file is a configuration reference only. It contains no secrets and should not be auto-triggered without user confirmation.

Recommended source order:

1. User-confirmed video API for high-quality output.
2. User-provided local MP4 files.
3. Local static synthesis for prototype fallback.

## Skill Usage

For Codex or another agent platform:

- Use `SKILL.md` as the skill entry point.
- Use `INTERACTION.md` as the required conversation SOP.
- Do not skip character-source confirmation before node-image generation.
- Do not describe prototype fallback videos as final rendered videos.

## Safety

- No API keys, cookies, or tokens are included.
- Generated output stays inside the project directory.
- Local file paths are stored as relative paths where possible.
- Existing user assets should not be overwritten without explicit permission.

## License

MIT
