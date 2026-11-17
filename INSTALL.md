# 安装 skill-website

## 把安装交给 Codex 或 Claude Code

把 `skill-website.zip` 放在客户端能读取的位置，附上文件或写出本机路径，再发送这一句。

> 请把我提供的 skill-website.zip 解压，将完整的 skill-website 文件夹安装到当前客户端的个人 Skills 目录，并确认能找到这个 Skill。

## 用终端从本地安装

解压 ZIP，在包含 `skill-website` 文件夹的目录打开终端。以下命令默认安装到当前目录所属的项目。

```bash
npx skills add ./skill-website --skill skill-website --agent codex claude-code --copy
```

仅用一个客户端时，`--agent` 后保留对应名字。要在所有项目里使用，追加 `-g`。

## 从 GitHub 仓库安装

公开发布后，可以把 `skill-website` 文件夹放在 GitHub 仓库的 `skills/` 目录下，再用以下形式安装。把 `YOUR_GITHUB_USERNAME` 替换为发布者的账号名。

```bash
npx skills add YOUR_GITHUB_USERNAME/skill-website --skill skill-website
```

## 手动安装

解压并移动整个 `skill-website` 文件夹，保留 `SKILL.md`、`scripts/` 和 `assets/` 的相对位置。

| 工具 | 放置位置与调用 |
| --- | --- |
| Codex | 把目录放进 `~/.agents/skills/`，在对话中输入 `$skill-website`。项目内使用时也可放在项目的 `.agents/skills/`。 |
| Claude Code | 把目录放进 `~/.claude/skills/` 或项目的 `.claude/skills/`，在 Claude Code 中输入 `/skill-website`。 |
| DeepSeek Harness | 默认文件系统 Skill 已启用时，把目录放进 `~/.dsh/skills/` 或项目的 `.dsh/skills/`，在对话中点名使用 `skill-website`。 |

示例请求：用 skill-website 把我上传的简历生成一个中文个人网站，用于求职。我想突出 AI 相关项目，风格用默认方案。

用户也可以直接提供简介、项目说明和作品图。默认模板使用 Python 3 标准库生成，可在浏览器直接打开站点的 `index.html`。PDF 提取及扫描件识别使用所选工具当前可用的能力。

[Codex](https://learn.chatgpt.com/docs/build-skills) · [Claude Code](https://code.claude.com/docs/en/skills#choose-where-skills-load) · [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/skill/skill-filesystem)
