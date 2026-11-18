# 一次准备，重复使用

只在安装或环境异常时读，不是每次建站的必经步骤。核心需Python 3.9+；PDF解析随包提供。备用浏览器检查另需已有Node 22+与Chromium，不自动安装。

## OCR执行权限

一些分发方式保留文件内容但丢失执行位。先运行 `python3 -S /absolute/skill-website/scripts/skill_setup.py`。仅在输出not_executable且安装来源可信时，在已有授权下运行一次：

```sh
python3 -S /absolute/skill-website/scripts/skill_setup.py --repair-ocr-mode
```

仅对scripts/bin/checksums.json中哈希匹配的随包文件恢复所有者执行位，不递归chmod、不执行下载文件、不改客户端设置。哈希不匹配、缺文件或软链接会报告，不强修。随后doctor/prepare验证运行支持。其他平台/架构没有对应程序时，权限修复不能使它得到支持。

维护者分发时ZIP保留Unix mode，Git中的二进制记录为100755；安装后自检并不意味着每次处理文档都要安装依赖。

## 图像与浏览器能力

prepare输出的宿主看图和浏览器能力默认unknown，这不能通过Python判断。助手根据现有工具与一次实际尝试确定，可传 `--image-viewing available|unavailable` 和 `--browser-control host|unavailable` 记录已知结果。

`node /absolute/skill-website/scripts/browser_check.mjs --probe` 只检查有限的常见安装位置，不搜缓存、不安装软件、不启动浏览器。其他已知位置可传 `--browser /absolute/browser-executable`。没有可用浏览器则继续结构检查并记录限制。客户端规定使用其浏览器接口时，不得用备用脚本绕过规定。

## Claude Code权限建议（不自动写设置）

技能决定尝试做什么，客户端权限决定是否允许。先在 `/permissions` 查看规则及来源，只为可信项目设置必要范围。

- 指定简历目录和网站输出目录，不把整个主目录作为写入授权范围。
- 需要时用acceptEdits接受工作范围内普通编辑；它不等于所有命令免确认。
- 对已审阅的固定脚本及固定输入/输出命令保存允许规则。统一准备入口替代五种零散命令，更方便复用授权。
- 不建议Bash(python3 *)、Bash(node *)或Bash(*)等宽泛规则，不全局开启bypassPermissions。

具体语法按当前客户端核对；单次批准、长期命令授权与自动编辑范围不同。不要为了减少弹窗扩大到未授权的操作。本技能不生成或写入.claude/settings*.json。

官方说明：https://code.claude.com/docs/en/permissions （2026-11-18核对）。
