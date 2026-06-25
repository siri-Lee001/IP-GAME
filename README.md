# IP-GAME（跨平台便携版）

这个仓库提供一个**跨平台可调用**的“互动影游生成器”便携版：不依赖任何特定应用的 Skill 运行时。  
你可以在 Windows / macOS / Linux 上用同一套命令，把结构化剧本 `story.json` 打包成可离线试玩的 `game.html`，并可选用本地静态图合成节点视频（不调用任何视频 API）。

如果你的平台需要一个“技能入口说明”（Codex 标准 Skill 包），请直接看：
- `SKILL.md`

如果你需要“对话式流程 + 问用户的问题模板”，请看：
- `INTERACTION.md`

---

## 安装

要求：Python `>= 3.10`

```bash
pip install -U pip
pip install .
```

或开发模式：

```bash
pip install -e .
```

---

## 快速开始

### 1) 准备一个项目目录

项目目录里至少需要：

```text
<project>/
  story.json
  ui.json            # 可选（没有会用默认值）
  assets/
    images/
    videos/
```

### 2) 打包生成 `game.html`

```bash
ip-game build-html <project-dir>
```

### 3) 用静态图合成视频（不调用任何 API）

会按“scene still + storyboard still”的策略生成节点 mp4：

```bash
ip-game make-videos <project-dir>
```

可指定轻量测试分辨率（默认会按 16:9/9:16 自动取 1920x1080/1080x1920）：

```bash
ip-game make-videos <project-dir> --size 1280x720
```

### 4) 资产自检

```bash
ip-game verify <project-dir>
```

---

## 作为 Skill 调用（给其它平台）

很多平台不会自动识别 `.trae/skills/` 结构，而更喜欢一个**仓库根目录的技能说明入口**。本仓库已提供 `SKILL.md`，你可以将其中“调用提示词”复制到平台的 Skill 配置里。

---

## 命令一览

```text
ip-game build-html <project-dir> [--story story.json] [--ui ui.json]
ip-game make-videos <project-dir> [--story story.json] [--only N0,E0] [--skip-existing] [--size 1280x720]
ip-game verify <project-dir> [--story story.json]
ip-game generate-node-prompts <project-dir> [--story story.json]
ip-game generate-character-prompts <project-dir> [--story story.json]
```

---

## 安全与密钥

- 本仓库**不包含任何密钥**。
- 如需接入第三方视频 API，请在你自己的环境里通过环境变量/私密配置管理，不要把密钥提交到 GitHub。

---

## 协议

MIT
