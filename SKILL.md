---
name: ip-game
description: Create and package IP-GAME interactive film games from story.json and ui.json. Use for 互动影游, 剧情游戏, 一键互动影游, character-consistent scene/video prompts, node videos, offline game.html, or IP-GAME SOP delivery.
---

# IP-GAME

IP-GAME 是一条“互动影游制作流水线”技能，不只是把 `story.json` 拼成网页。正确使用时，必须从剧本确认、角色一致性、节点图片、视频来源、主题包装到资产自检完整走完，并且清楚标记当前交付是 `prototype` 还是 `final`。

运行入口：`ip-game` CLI。当前仓库版本：`0.2.0`。默认安全边界：不内置密钥；本地 CLI 默认不触网；所有输出写入项目目录。

## 必须先读

- 对话 SOP：`INTERACTION.md`
- 可选视频 API 配置说明：`providers/video.provider.json`

如果用户要求“用 IP-GAME 做一个互动影游”，先按 `INTERACTION.md` 的 6 步流程执行。除非用户明确要求跳过，否则不要直接生成网页。

## 工作机制

1. 接收一句话故事、短剧本或完整设定。
2. 信息不足时只做一次 8 问补充；用户允许 AI 默认后继续。
3. 先交付并确认结构化剧本：梗概、角色小传、服化道、路线图、节点清单、主题色建议。
4. 角色图先行：必须确认角色图来源，生成或整理角色定妆图后，再进入节点图。
5. 节点图：每个节点至少规划 `sceneImage` 和 `storyboardImage` 两类图，比例必须全链路一致。
6. 视频：让用户选择视频 API、本地已有视频、或本地静态合成。静态合成只能视为测试/保底，不能冒充高质量成片。
7. 生成 `game.html`，内含开场海报、播放页、分支选择、路线图、章节跳转、结局页、TTS 开关和本地素材引用。
8. 运行 `verify` 检查图片、视频、比例、可播放性和最终交付风险。

## 质量分层

- `prototype`：允许用静态图合成视频或占位素材，目标是跑通流程和试玩交互。
- `final`：必须有可读图片、同一比例、角色参考图、可播放视频；视频过小会被 `verify` 标记为疑似低质。

不要把 `prototype` 结果说成最终成品。发生 API 不可用、缺图、缺视频时，可以降级继续，但必须告诉用户降级到了哪一级、缺什么、补什么能到 `final`。

## 资产与字段约定

项目目录：

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

重要字段：

- `story.meta.questionnaire.aspect_ratio`：`横版16:9` 或 `竖版9:16`，决定图片、视频和网页比例。
- `story.meta.deliveryTier`：`prototype` 或 `final`。
- `story.meta.poster`：开场海报。
- `story.characters[].characterSheetPrompt`：角色定妆图提示词。
- `story.characters[].referenceImages` / `images`：角色一致性参考图。
- `story.nodes[].media.sceneImage`：节点主场景图。
- `story.nodes[].media.storyboardImage`：九宫格连续分镜图。
- `story.nodes[].media.videoRefImage`：视频生成参考图，默认优先用分镜图。
- `story.nodes[].media.endingImage`：结局图。
- `story.nodes[].media.video`：节点视频。

## 角色一致性规则

- 先做角色定妆图，再做节点图。
- 用户已有角色图时，优先使用本地角色图，不能擅自重新设计。
- 同一角色在不同节点必须沿用同一身份锚点。
- 一个角色存在重大造型变化时，要拆成多个状态参考，例如 `jiangchen_daily`、`jiangchen_battle`。
- 节点提示词必须引用角色参考图路径或参考说明。

## 提示词输出

生成角色提示词：

```bash
ip-game generate-character-prompts <project-dir>
```

写入：

- `story.json.characters[].characterSheetPrompt`
- `assets/prompts/characters/<角色ID>_sheet.txt`

生成节点提示词：

```bash
ip-game generate-node-prompts <project-dir>
```

写入：

- `story.json.nodes[].media.scenePrompt`
- `story.json.nodes[].media.storyboardPrompt`
- `assets/prompts/<节点ID>_scene.txt`
- `assets/prompts/<节点ID>_storyboard.txt`

提示词标准：

- 角色图：左侧脸部近景、中间全身三视图、右侧多表情头像，明亮清晰，无文字。
- 场景图：电影感主场景，角色全身或大半身，不裁头脚，身份一致。
- 分镜图：一张图内包含 3x3 连续关键帧，左侧保留角色/道具参考区，画面无文字、编号、水印。

## 视频来源

必须让用户选择：

1. 视频 API 生成：可参考 `providers/video.provider.json`。必须由用户明确确认，密钥只放环境变量，不进仓库。
2. 本地已有视频：用户提供 mp4，放入 `assets/videos/` 并写入 `story.json`。
3. 静态图合成视频：使用本地 `make-videos`，适合预览和测试，不代表最终画质。

本地合成：

```bash
ip-game make-videos <project-dir> --skip-existing
```

## 打包与验证

生成网页：

```bash
ip-game build-html <project-dir>
```

验证：

```bash
ip-game verify <project-dir>
```

最终交付前必须验证。若 `verify` 失败，先列出缺失/低质资产和修复建议，再决定是否继续交付原型。

## HTML 交付标准

`game.html` 应支持：

- 开场海报页和开始按钮。
- 首次进入引导弹窗。
- 节点视频播放，结束后显示选择。
- 结局页和结局图。
- 路线图/章节跳转。
- 重播当前节点、回到开场、重新开始。
- 声音/TTS 开关，避免和视频原声冲突。
- 纯本地相对路径，不给本地文件添加缓存参数。

## CLI 命令

```text
ip-game build-html <project-dir> [--story story.json] [--ui ui.json]
ip-game generate-character-prompts <project-dir> [--story story.json]
ip-game generate-node-prompts <project-dir> [--story story.json]
ip-game make-videos <project-dir> [--story story.json] [--only N0,E0] [--skip-existing] [--size 1280x720]
ip-game verify <project-dir> [--story story.json]
```

## 安全要求

- 不提交任何 token、API key、Cookie 或个人凭据。
- 视频 API provider 只能写配置结构和环境变量名。
- 不因为 API 失败而中断整个流程，可以降级，但必须透明说明。
- 不覆盖用户已有素材，除非用户明确要求。
