---
name: lengmeng-paiiban
description: 冷檬排版 —— 复刻自 markdown.gmlart.cn（WeChat-Markdown 公众号排版大师）的微信公众号 Markdown 排版技能，内置 30 款排版风格（经典 / 潮流 / 更多风格）。当用户发送文章（Markdown 文本、md/txt 文件、Word/飞书富文本、在线文档链接）并要求"排版""公众号排版""排版风格""冷檬""做成公众号样式""换个风格排版""美化排版"时使用。流程：列出 30 款排版风格供用户选择 → 按所选风格自动排版 → 交付可预览、可一键复制到公众号后台的 HTML（格式内联、不丢失）。
---

# 冷檬排版

复刻 markdown.gmlart.cn 的公众号 Markdown 排版引擎。30 款风格、纯内联样式、微信粘贴格式不丢失。

## 何时使用

- 用户发来文章正文（消息文本 / 上传文件 / 在线链接）并要求公众号排版
- 用户提到"排版""排版风格""冷檬""公众号样式""做成推文""像 markdown.gmlart.cn 那样排"
- 用户要求给已排好的文章更换风格 / 用另一种风格重排

## 工作流程

### 第 1 步：读取文章

- 文章来源可能是：消息里的 Markdown/纯文本、上传的 .md/.txt/.docx 文件、飞书/豆包文档链接
- 富文本/Word 内容先转成 Markdown；文中的图片（本地路径或网络 URL）保留引用
- 若文章过长、内容不完整或来源不明确，先和用户确认范围再继续

### 第 2 步：列出排版风格供选择

- 读取 `assets/themes/` 目录下的 30 个独立 JSON（每个含 id / name / description / category / styles）
- 按「经典 / 潮流 / 更多风格」三段列出：名称 + 一句话描述 + 适合内容建议，请用户选择一款
- 用户未指定 → 默认推荐「Mac」；用户说"随便 / 你定" → 按文章主题推荐一款并说明理由
- 用户直接点名（如"用 Linear"或"水墨"）→ 跳过列表示，直接进入渲染

### 第 3 步：自动排版

把文章写入临时 .md 文件（或直接用用户上传的文件），运行：

```bash
python3 scripts/render.py --md <文章.md> --theme <风格id或名称> --title "<文章标题>" --out <输出目录>
```

- `--theme` 接受 id（apple/claude/wechat/...）、英文名或中文名；传 `全部` 可输出全部 30 款 article 文件
- 渲染引擎复刻原站完整管线：Markdown 预处理 → markdown-it 渲染（Mac 风格红绿灯代码块 + 语法高亮）→ 逐元素注入主题内联样式 → 微信兼容处理（section 包裹、图片网格转表格、列表符号、字体继承、标点粘连修复、图片转 base64）
- 输出物：
  - `preview.html` —— 自包含预览页：默认展示所选风格，可切换全部 30 款风格、手机/平板/桌面三种预览宽度、一键「复制到公众号」
  - `article-<id>.html` —— 所选风格的纯微信版 HTML（图片已 base64 内嵌，可直接复制粘贴）

### 第 4 步：交付

- 用 `present_files` 交付 `preview.html`（主交付物）和 `article-<id>.html`
- 告诉用户：浏览器打开 preview.html → 顶部切换风格（如需对比）→ 点「复制到公众号」→ 到公众号后台 Ctrl/Cmd+V，格式完整保留
- 若文章有外链图片且转换失败：提示该图片在微信中可能提示"图片来自第三方"，建议在公众号后台重新上传
- 用户反馈"换个风格"→ 直接重跑渲染（可只换 --theme），无需重列风格

## 关键约定

- **微信兼容优先**：输出只含内联样式，无外部样式表/class 依赖（代码高亮色也逐 span 内联）
- **图片**：优先转 base64 内嵌；远程图片尽力抓取，失败保留 URL 并提示用户
- **代码块**：保留原站 Mac 红绿灯控制台样式 + GitHub 浅色语法配色
- 渲染脚本依赖 Python 3 + markdown_it / BeautifulSoup4 / Pygments（环境已装）；如缺失先 `pip install markdown-it-py beautifulsoup4 pygments linkify-it-py`
- 全量 30 款风格定义以 `assets/themes/*.json` 为唯一权威来源，不要手写 CSS 覆盖；需要改样式先改对应 JSON

## 资源

- `scripts/render.py` —— 渲染引擎（CLI：--md / --theme / --title / --out / --list）
- `assets/themes/*.json` —— 30 款风格的完整定义（每款一个独立 JSON，内联 CSS）
- `references/themes.md` —— 风格目录速查表（列风格时参考）
