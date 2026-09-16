# 冷檬公众号排版

> Markdown 一键排版为微信公众号文章，内置 **30 款高定排版风格**，纯内联样式，复制粘贴到公众号后台格式不丢失。

灵感与样式数据复刻自 [markdown.gmlart.cn](https://markdown.gmlart.cn/)（WeChat-Markdown 公众号排版大师），在此致敬原作者。

## ✨ 特性

- **30 款排版风格**：经典 10 款 / 潮流 10 款 / 更多风格 10 款（Mac、Claude、微信原生、Notion、GitHub、Linear、Dracula、水墨、Cyberpunk……）
- **纯内联样式**：输出 HTML 全部为 inline style，无外部 CSS / class 依赖，微信粘贴后背景色、字体、间距、代码块、表格、图片完整保留
- **一键复制**：自包含预览页内置「复制到公众号」按钮，直接 Ctrl/Cmd+V 粘贴到公众号后台
- **代码块**：Mac 风格红绿灯控制台 + GitHub 浅色语法高亮（Pygments）
- **图片自动打包**：远程 / 本地图片自动转 base64 内嵌，避免「图片来自第三方」警告
- **微信兼容**：section 包裹、图片两两成网格自动转表格、嵌套列表不塌陷、标点粘连修复
- **多视图预览**：手机 / 平板 / 桌面三种宽度切换，30 款风格随时对比

## 🚀 快速开始

```bash
# 1. 安装依赖（Python 3.8+）
pip install markdown-it-py beautifulsoup4 pygments linkify-it-py

# 2. 查看全部 30 款风格
python3 scripts/render.py --list

# 3. 排版一篇文章（默认 Mac 风格，生成可切换全部 30 款的预览页）
python3 scripts/render.py --md 文章.md --theme mac --title "文章标题" --out output

# 4. 打开 output/preview.html，点「复制到公众号」，到后台 Ctrl/Cmd+V 粘贴即可
```

`--theme` 接受风格 id（`apple` / `linear` / `github`…）、英文名或中文名（`Mac` / `水墨`）；传 `全部` 则输出全部 30 款。

## 📁 目录结构

```
.
├── SKILL.md              # 技能使用说明（Agent 集成用）
├── scripts/
│   └── render.py         # 渲染引擎（CLI）
├── assets/
│   └── themes.json       # 30 款风格完整定义（逐元素内联 CSS）
└── references/
    └── themes.md         # 风格目录速查表
```

## 🎨 30 款风格

| 分类 | 风格 |
|------|------|
| 经典 | Mac、Claude、微信公众号原生、NYT、Medium、Stripe、飞书效率、Linear、Retro、Bloomberg |
| 潮流 | Notion、GitHub、少数派、Dracula、Nord、樱花、深海、薄荷、日落、Monokai |
| 更多风格 | Solarized、Cyberpunk、水墨、薰衣草、密林、冰川、咖啡、Bauhaus、赤铜、彩虹糖 |

完整风格列表见 [`references/themes.md`](references/themes.md)。

## 🧩 作为 Agent 技能使用

本仓库同时是一个可直接安装的 Agent Skill：把目录放入 `.user_skills/`，Agent 即可在收到文章后自动列出 30 款风格供选择，一键完成排版与交付。详见 [`SKILL.md`](SKILL.md)。

## 🙏 致谢

渲染管线与 30 款风格样式复刻自 [markdown.gmlart.cn](https://markdown.gmlart.cn/)，感谢原作者的开源分享。本项目为个人学习 / 玩票性质的本地复刻实现。

## 📄 License

[MIT](LICENSE)
