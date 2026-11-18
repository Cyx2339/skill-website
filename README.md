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

文档工具需要 Python 3.9+，已打包 PDF 解析器，无需在使用时下载或安装解析库。支持 Markdown、TXT、DOCX 和文字型 PDF；Apple Silicon、macOS 14+ 随包提供离线扫描 PDF 识别程序，实际能力以 `doctor` 检查为准。其他平台可读取文字文档，但扫描件需要已有的兼容识别能力。旧版 `.doc` 暂不支持。

读取时保留原文、页码或段落位置，并报告未读内容。内容整理会输出分类底稿、数字及贡献描述候选、来源引用和覆盖核对清单。助手完成语义核对后才把内容映射到网站，不会自动把底稿当成发布稿。

- [文档工具：支持格式、调用方式与读取限制](references/document-tools.md)
- [内容整理：来源追溯、核对流程与文件格式](references/content-preparation.md)

这两个模块可通过 `scripts/document_tools.py` 独立调用，也可以跟随网站技能一起使用。生成网站仍由原有 `scripts/render_site.py` 负责，静态网站可直接在浏览器打开 `index.html` 预览。

[查看 Skill 文件](https://github.com/Cyx2339/skill-website/blob/main/SKILL.md)


## 图片、设计与输出管理

新增 `media_tools.py`：提取 PDF / DOCX 图片、盘点本地素材、记录选图依据与角色。本人照片默认作为左上角圆形头像，可悬浮预览、点击完整查看；手机支持点击，弹窗支持 Escape 和焦点恢复。首屏氛围图与头像分开配置。

新增 `site_workflow.py`：按北京时间创建 `output/websites/站点名称/日期时间-vNN/`，将底稿、网站和检查分开，交付时只打包网站。用户指定根目录优先，已有版本不覆盖。

设计参考库整理了摄影杂志、温暖插画、东方艺术和自然摄影四种方向。根据人物和内容选取，不把同一配色或布局套给所有人。附带参考截图供本地视觉研究，不作为用户作品放入网站；使用与分享原设计需遵循来源授权。

- [图片与头像处理](references/media-selection.md)
- [输出目录与交付](references/output-workflow.md)
- [视觉方向与案例](references/visual-direction.md)
- [设计验收](references/design-review.md)

离线核心仍只需要 Python 3.9+ 和随包解析库。图库搜索/API/MCP 可选，没有连接也能使用本地资料，不在网站里存放 API Key。
