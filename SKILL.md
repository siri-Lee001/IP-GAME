---
name: IP-GAME
version: 0.1.0
language: zh-CN
entrypoint: ip-game (CLI)
platform: cross-platform (Windows/macOS/Linux)
---

# IP-GAME Skill（跨平台互动影游生成器）

把结构化剧本 `story.json` 打包成可离线试玩的 `game.html`，并可选用“静态图合成视频”的方式在本地生成节点 `mp4`（不调用任何视频 API）。

这个 `SKILL.md` 作为**使用说明入口**：给“其它平台/Agent 框架”读取后即可知道该怎么调用仓库能力、怎么组织输入输出、以及有哪些安全边界。

---

## 你能做什么

- 从 `story.json` / `ui.json` 生成 `game.html`（本地 `file://` 直接双击可玩）
- 从 `assets/images/*` 合成 `assets/videos/<节点ID>.mp4`（纯本地 ffmpeg，默认 5–15 秒，适合测试）
- 为每个剧情节点生成：
  - `media.scenePrompt`
  - `media.storyboardPrompt`
  以及默认媒体路径（便于接入任意生图/生视频平台）
- 为角色生成“多视角定妆提示词”（不限物种），并把“本地角色图优先”规则写入提示词
- 资产自检：检查引用素材是否存在、视频是否可播放、是否出现 0 字节文件

---

## 非目标（明确不做）

- 不直接调用任何云端生图/生视频 API（本仓库保持“可落地、可离线”的最小闭环）
- 不内置/不管理任何密钥（不接受把 key 写进仓库）
- 不自动帮用户写完整剧情（剧情生成属于上层 LLM/平台职责；本仓库更偏“打包与落地工具链”）

---

## 输入与输出约定

### 输入（项目目录）

项目目录必须包含：

```text
<project>/
  story.json
  ui.json                 # 可选，不存在时会用默认
  assets/
    images/               # scenes/storyboards/endings/characters 等
    videos/               # 将在这里生成 N0.mp4/E0.mp4...
```

### 输出

- `<project>/game.html`
- `<project>/assets/videos/<节点ID>.mp4`（可选，使用静态图合成时生成）
- `story.json` 可能被补写（当执行 `generate-*` 时）

---

## 运行方式（CLI）

本 Skill 的调用方式是命令行，跨平台一致：

### 安装

```bash
pip install .
```

### 命令清单

```text
ip-game build-html <project-dir> [--story story.json] [--ui ui.json]
ip-game make-videos <project-dir> [--story story.json] [--only N0,E0] [--skip-existing] [--size 1280x720]
ip-game verify <project-dir> [--story story.json]
ip-game generate-node-prompts <project-dir> [--story story.json]
ip-game generate-character-prompts <project-dir> [--story story.json]
```

---

## 推荐调用流程（SOP）

### SOP A：只生成可试玩网页（最快）

1. 用户提供/已有 `story.json`
2. 执行：
   - `ip-game build-html <project-dir>`
3. 交付：`game.html`

### SOP B：静态图合成视频 + 网页（推荐测试链路）

1. 确保每个节点至少有 `sceneImage` 或 `storyboardImage`（建议两者都有）
2. 执行：
   - `ip-game make-videos <project-dir> --size 1280x720`
   - `ip-game build-html <project-dir>`
   - `ip-game verify <project-dir>`
3. 交付：`assets/videos/*.mp4` + `game.html`

### SOP C：先补齐提示词（用于接外部生图平台）

1. 执行：
   - `ip-game generate-character-prompts <project-dir>`
   - `ip-game generate-node-prompts <project-dir>`
2. 将提示词交给任意平台生成图片/视频（平台外部完成）
3. 再回到本仓库：
   - `ip-game make-videos ...`（可选）
   - `ip-game build-html ...`

---

## 关键机制

### 1) 角色一致性与“本地角色图优先”

`story.json.characters[]` 支持以下字段（用于跨平台一致性）：

- `visualState`：幼年态/成年态/入魔态/修仙态……
- `imageSourceStrategy`：`local | generate`
- `referenceImages`：用户提供的角色参考图路径列表（若非空必须优先）

当 `imageSourceStrategy=local` 且 `referenceImages` 非空时：
- **角色环节必须使用本地素材**
- 后续节点图/故事板提示词必须写明“不得擅自换脸换发型换服装体系”

### 2) 节点提示词生成

`generate-node-prompts` 会：
- 补齐 `media.scenePrompt` / `media.storyboardPrompt`
- 补齐默认媒体路径（sceneImage/storyboardImage/videoRefImage/video）
- 若节点声明了 `node.characterRefs`，会把对应角色的 `referenceImages/images.*` 写入提示词，强化一致性

### 3) 静态图合成视频

`make-videos` 的合成策略：
- 开场使用 `sceneImage`（优先）做短时段
- 主体使用 `storyboardImage` 做剩余时段
- 使用 `contain+pad`，避免裁切导致构图损坏
- 输出 H.264 + AAC（静音轨），提高跨播放器兼容性

---

## 安全机制

- **默认不触网**：所有命令均为本地文件处理，不访问网络
- **不包含密钥**：仓库不允许写入 `.env`/token/key；建议在平台侧用密钥管理器注入
- **输出可控**：只写入项目目录内文件（`game.html`、`assets/videos/`、提示词补写到 `story.json`）
- **自检兜底**：`verify` 能发现丢素材/0 字节视频/无法播放视频等常见事故

---

## 给其它平台/Agent 的“调用提示词”

把下面这一段作为上层平台的“Skill 指令”即可（适用于多数 Agent 框架）：

```text
你有一个本地工具仓库 IP-GAME，可通过 CLI `ip-game` 执行。
目标是将 <project-dir> 中的 story.json 打包为 game.html，并可选地用静态图合成视频。

规则：
1) 不调用任何云端 API，不要生成/索要密钥。
2) 先运行 `ip-game verify <project-dir>` 了解缺失素材。
3) 若用户要求生成视频，用 `ip-game make-videos <project-dir> --size 1280x720`（测试用），再 verify。
4) 最后运行 `ip-game build-html <project-dir>` 输出 game.html。
5) 任何失败都要把错误信息原样输出并给出下一步建议（缺图/缺字段/路径不对）。
```

