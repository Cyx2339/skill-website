# skill-website

根据简历和个人情况生成独属于自己的个人网站。

把 PDF 简历、自我介绍或作品素材做成可编辑、可离线预览的个人网站。支持个人优势、主案例、项目详情和移动端布局。

## 安装

### 从 GitHub 安装

在终端运行以下命令，按提示选择 Codex 或 Claude Code。

```bash
npx skills add Cyx2339/skill-website
```

终端命令默认安装到当前项目。要在所有项目中使用，在命令末尾加 `-g`。只想查看仓库中可安装的 Skill，可以加 `--list`。[skills CLI 安装文档](https://github.com/vercel-labs/skills/blob/main/docs/commands.md#skills-add)

### 让 Codex 或 Claude Code 安装

把这句话发给能访问本机和 GitHub 的 Codex 或 Claude Code。

> 请帮我从 https://github.com/Cyx2339/skill-website 安装 skill-website，安装到当前客户端的个人 Skills 目录，并确认可以调用。

已有 ZIP 时，可以附上文件或提供本机路径，再发送下面这句话。

> 请从我提供的 ZIP 安装 skill-website。找到包含 SKILL.md 的完整文件夹，安装到当前客户端的个人 Skills 目录，并确认可以调用。

### 从本地 ZIP 安装

解压 ZIP，在解压后的文件夹旁边打开终端。假如解压出的文件夹叫 `skill-website`，运行以下命令。

```bash
npx skills add ./skill-website
```

通过 GitHub 的 **Download ZIP** 下载时，解压目录通常叫 `skill-website-main`，把命令里的目录名换成实际名称即可。也可以用引号包住文件夹的完整路径。

### 手动安装

找到包含 `SKILL.md` 的文件夹，将整个文件夹以 `skill-website` 为名复制到对应的 Skills 目录，保留里面的 `scripts/`、`assets/` 和 `references/`。

| 客户端 | 个人目录 | 项目目录 |
| --- | --- | --- |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills/` | `.agents/skills/` |
| [Claude Code](https://code.claude.com/docs/en/skills#choose-where-skills-load) | `~/.claude/skills/` | `.claude/skills/` |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/skill/skill-filesystem)（需启用文件系统 Skill） | `~/.dsh/skills/` | `.dsh/skills/` |

## 使用

上传简历或提供自我介绍，再发送「用 skill-website 帮我生成一个求职用的个人网站，我想突出 AI 项目」。也可以指明想展示的栏目、风格或参考页面。

Codex 可以用 `$skill-website` 点名，Claude Code 可以用 `/skill-website`，DeepSeek Harness 可以在对话中点名使用 `skill-website`。

默认生成脚本使用 Python 3 标准库。PDF 文本提取和扫描件识别取决于客户端可用的工具。生成的静态网站可直接在浏览器打开 `index.html` 预览。

[查看 Skill 文件](https://github.com/Cyx2339/skill-website/blob/main/SKILL.md)
