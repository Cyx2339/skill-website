# 站点数据与生成方式

使用 UTF-8 JSON。`name` 是必填项，其余字段按资料选用。所有文字使用纯文本。图片对象用用户允许展示的本地文件路径，支持 JPG、PNG、WebP、AVIF、GIF。路径相对数据文件解析，也可使用绝对路径。

| 字段 | 结构 |
| --- | --- |
| `name`、`headline` | 展示用姓名及职位或定位。首页以姓名为主标题。 |
| `language` | 语言标签，默认 `zh-CN`。内置中文和英文标签，其余语言可覆盖。 |
| `intro` | 一段介绍，或由多段文字组成的数组。 |
| `portrait` | 可选本人照片对象（默认显示于左上角头像，点击查看完整图） `{"file":"photo.jpg","alt":"照片内容"}`。 |
| `strengths` | 个人优势数组，各项含 `title` 和 `summary`。从原资料提取标题及经历证据。 |
| `metrics` | 可选数组，元素为 `{"value":"3 年+","label":"软件开发经验"}`。仍可读取旧数据并以短列表展示。新站优先将数字写在对应的介绍或经历里。 |
| `projects` | 按网站重点排序，首项作为主案例。结构见下。 |
| `section_order` | 可选数组，调整区块顺序。支持 `projects`、`strengths`、`experience`、`skills`、`education`、`honors`、`contact`。例如 `["experience", "projects"]` 把经历提到作品前。 |
| `experience`、`education`、`honors` | 各项用 `title`、`subtitle`、`period`、`location`、`summary`。 |
| `skill_groups`、`skills` | 可用分组数组展示技能，每组含 `title` 和 `summary`。短列表可沿用 `skills` 字符串数组。 |
| `links` | 各项为 `{"label":"GitHub","url":"https://github.com/example"}`。接受 http、https、mailto、tel。 |
| `resume` | 用户明确同意公开的 PDF 本地路径。 |
| `labels` | 支持覆盖导航及区块用语。键包括 `home`、`nav`、`top`、`projects`、`strengths`、`experience`、`education`、`honors`、`skills`、`contact`、`view_projects`、`featured_detail`、`row_detail`、`detail`、`status`、`flow`、`back`、`skip`、`resume`。 |

项目用 `title`、`summary`，以及可选的 `id`、`role`、`period`、`tags` 字符串数组、`cover` 图片对象、`status` 和 `url`。简述使用单段文字。`url` 可链接到用户允许公开的外部作品。`id` 使用小写英文、数字和连字符，可生成稳定的详情路径。

带有实际 `sections`、`gallery` 或 `process` 时可生成详情页。`process` 适合资料支持的真实技术、创作或业务流程，每步填写 `title` 和可选的 `summary`。可用 `process_title` 改写流程标题。主项目有流程时在首页展示步骤图，只有封面时使用封面。项目状态用 `status`，详情会展示它。需要补充较长的状态背景时可写入案例小节。

```json
{
  "name": "林知宁",
  "headline": "独立摄影师",
  "intro": "拍摄城市中的日常与公共空间。",
  "strengths": [
    {"title": "纪实摄影", "summary": "长期记录河岸步道与公共交通沿线的日常。"}
  ],
  "projects": [
    {
      "id": "riverside",
      "title": "河岸散步",
      "summary": "沿城郊河道拍摄的一组照片。",
      "cover": {"file": "./riverside.jpg", "alt": "阴天里的城市河岸"},
      "tags": ["纪实摄影"],
      "sections": [
        {"title": "关于这个系列", "body": "从老码头出发，记录河道两侧的日常生活。"}
      ],
      "gallery": [
        {"file": "./pier.jpg", "alt": "空荡的旧码头", "caption": "老码头，清晨"}
      ]
    }
  ]
}
```

`sections.body` 及个人优势、技能组和经历的 `summary` 可用一个段落或段落数组。小节可用 `sections.image` 插图。缺少相关内容时直接省略相应区块和导航。

## 生成和调整

脚本适用于 Python 3.8+，只使用标准库。使用绝对脚本路径和新输出目录。

```bash
python3 /path/to/skill-website/scripts/render_site.py /path/to/site-data.json /path/to/site-output
```

可追加 `--styles /path/to/custom.css`，该样式会随站点交付。常用样式变量包括页面底色 `--surface`、流程底色 `--paper`、文字色 `--ink`、次要文字 `--muted`、分隔线 `--line`、强调色 `--accent`、正文字体 `--font-body`、标题字体 `--font-display` 及姓名字体 `--font-name`。流程图支持 `--feature-surface`、`--feature-ink`、`--feature-muted`、`--feature-rule`。如果当前环境没有 Python，可用相同设计规则直接写独立 HTML 和 CSS。

默认模板可离线打开。含主案例步骤图时生成少量原生 JS 处理单次淡入，关闭 JS 时内容直接呈现。检查首页和案例页在桌面与手机上的排版、页内滚动、返回链接和减少动态效果。若用户要求打包网站，打包生成的站点目录。

统一字号与间距、背景克制和尊重减少动态效果等做法参考 [Elaya 网页设计规则](https://github.com/elayadesign/ai-design-skills/blob/main/skills/landing-page-design/SKILL.md#part-b--visual-system)。


## 本人照片、首屏图片与视觉方向

图片字段均为本地文件，渲染时复制到网站内部；原件不变。常用可选字段：`position: [50, 35]` 指定缩略图的横纵焦点百分比，`caption` 展示图片说明，`credit` 与 `source_url` 展示来源署名。个人主页的氛围图默认省略这三个展示字段，来源只存入 `work/` 素材清单；仅在用户要求、有意义的作品图注或必须公开署名时填写。不要把选图工具返回的来源字段直接带入页面。`alt` 按实际内容填写。完整照片弹窗不裁切。

- `portrait`：本人照片，不接收未知身份的图库人物。默认左上角圆形头像。
- `portrait_placement`：`header`（默认）、`hero` 或 `both`。
- `hero_image`：独立首屏图，可为已选定的相关氛围图；不会覆盖导航头像。
- `design.theme`：`base` 或 `editorial`。前者是基础结构，后者为可选图文方向，不是所有网站的新默认。其他风格用定制样式/模板落实。
- `design.eyebrow`：可选首屏辅助文字，必须有明确用途，不自动加入装饰性英文。

以 `site_workflow.py build` 管理正式版本；直接调用 `render_site.py` 仍兼容，用于临时预览或其他工作流。标准目录和交付步骤见 [输出规则](output-workflow.md)。

## 按需调整组件

先改字段、区块顺序与custom.css。荣誉放在honors数组，每条保留名称、时间与原文支持的说明，不压成一句总数；教育、技能、荣誉有内容时均可导航到对应区块。

| 需求 | 现有入口 |
| --- | --- |
| 首屏图文布局 | `.hero`、`.hero-intro`、`.hero-image`；新结构才查看Site.hero |
| 主案例与其他项目 | `.featured-project`、`.featured-copy`、`.project-row`；新结构查看Site.project |
| 经历、教育、荣誉 | `.fact-row`、`.entry-summary`；字段已支持，无需重写生成器 |
| 头像与完整照片 | `.portrait-trigger`、`.portrait-dialog`；复用现有site.js键盘与焦点处理 |
| 项目详情 | `.detail-block`；新结构查看Site.detail |

全新结构可在本次work/里写定制渲染入口、复用或继承Site对应方法；不要直接改已安装技能。自定义输出同样需要内容核对与交付检查，不能以统一模板限制设计。
