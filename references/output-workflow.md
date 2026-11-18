# 输出目录与交付

所有新任务先创建一个版本目录。默认位置为当前项目的 `output/websites/站点名称/北京时间日期时间-vNN/`。用户指定位置时使用 `--root` 替换默认的 `output/websites` 根目录；不要修改用户原始资料，不把成果写进技能安装目录。

```sh
python3 -S /path/to/skill-website/scripts/site_workflow.py init --name 个人网站 --workspace /path/to/project
```

从输出 JSON 读取本次绝对路径，后续使用该路径，不自行猜测时间戳。

| 内容 | 位置 |
| --- | --- |
| 提取、整理、素材清单、视觉选择及网站数据 | `work/` |
| 可公开的网站 HTML、样式、脚本、选定图片 | `site/` |
| 实际浏览器截图与检查报告 | `review/` |
| 时间、版本、状态和路径 | `run.json` |
| 成果入口和实际验证范围 | `交付说明.md` |

初始化不创建 `site/`，避免与生成器“不覆盖现有目录”的约束冲突。内容完成后使用：

```sh
python3 -S /path/to/skill-website/scripts/site_workflow.py build --run /absolute/run --data /absolute/run/work/site-data.json
```

有定制样式时追加 `--styles /absolute/run/work/custom.css`。继续修改同一个站点时创建新版本，并在新版本复制需要的工作数据；只修改指定的版本，也不能悄悄覆盖已经交付的网站。开发中可在 `work/` 下用临时预览目录检查，完成后再正式 build。

按 [设计验收](design-review.md) 查看页面，将真实检查结果写入 `review/visual-checks.json`，包含 `status`、`checks`、`screenshots`、`limitations`。只有全部约定范围验证完成才标 `passed`；有缺项标 `partial`，没打开浏览器标 `not_run`。截图不能证明未操作的交互可用。

```sh
python3 -S /path/to/skill-website/scripts/site_workflow.py deliver --run /absolute/run
```

交付工具检查本地 HTML 资源与锚点，输出 `review/structural-checks.json`。检查通过后只打包 `site/`，生成 `website.zip` 和交付说明。它不会上传或发布网站，不会把底稿和源简历一起放入压缩包；也不会替代目视检查。已有压缩包不会被覆盖。

每次结束给用户三个绝对路径链接：网站首页、版本文件夹、网站压缩包，并说明仍缺少的照片/资料或未验证范围。使用本地服务预览时同时给出有效预览 URL；离线首页仍应可用。
