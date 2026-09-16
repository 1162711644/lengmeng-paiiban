#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冷檬排版 - 微信公众号 Markdown 排版引擎
复刻 https://markdown.gmlart.cn/ (WeChat-Markdown 公众号排版大师) 的渲染管线：

  1. Markdown 预处理（***/---/___ 分隔线归一、空加粗清理、粗体后标点处理）
  2. markdown-it 渲染（HTML 直通、链接识别、Mac 风格红绿灯代码块 + hljs 高亮）
  3. 主题内联样式应用（30 款主题，逐元素注入 CSS，纯内联、零外部样式表）
  4. 微信兼容处理（section 包裹、图片网格转表格、列表符号、li>p 转 span、
     容器字体/字号/颜色/行高继承、标点粘连修复、图片转 base64）

输出：
  preview.html         —— 自包含预览页：可切换 30 款风格、手机/平板/桌面三种
                          预览宽度、一键「复制到公众号」
  article-<id>.html    —— 所选主题的纯微信版 HTML（<section> 内联样式，可直接
                          复制粘贴到公众号后台，格式不丢失）

用法：
  python3 render.py --md 文章.md --theme mac --title "文章标题" --out 输出目录
  python3 render.py --list                        # 打印 30 款风格目录
  python3 render.py --md 文章.md --theme 全部     # 输出全部 30 款 article-<id>.html
"""

import argparse
import base64
import html as html_mod
import json
import os
import re
import sys
import urllib.request

from bs4 import BeautifulSoup, NavigableString
from markdown_it import MarkdownIt

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES_DIR = os.path.join(SKILL_DIR, "assets", "themes")

# 经典 / 潮流 / 更多风格 的固定展示顺序
_THEME_ORDER = [
    "apple", "claude", "wechat", "media", "medium", "stripe", "workspace",
    "linear", "retro", "bloomberg",
    "notion", "github", "sspai", "dracula", "nord", "sakura", "ocean",
    "mint", "sunset", "monokai",
    "solarized", "cyberpunk", "ink", "lavender", "forest", "glacier",
    "coffee", "bauhaus", "copper", "pastel",
]

# ---------------------------------------------------------------------------
# 主题加载
# ---------------------------------------------------------------------------
def load_themes():
    themes = []
    for name in sorted(os.listdir(THEMES_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(THEMES_DIR, name), encoding="utf-8") as f:
                themes.append(json.load(f))
    order = {tid: i for i, tid in enumerate(_THEME_ORDER)}
    themes.sort(key=lambda t: order.get(t["id"], 999))
    return themes

THEMES = load_themes()
THEME_BY_ID = {t["id"]: t for t in THEMES}


def find_theme(theme_id):
    """支持按 id、英文名或中文名查找主题"""
    if theme_id is None:
        return None
    theme = THEME_BY_ID.get(theme_id)
    if theme is None:
        key = theme_id.strip().lower().replace(" ", "")
        for t in THEMES:
            if t["name"].lower().replace(" ", "") == key or t["id"].lower() == key:
                theme = t
                break
    if theme is None:
        raise SystemExit(
            f"未知排版风格: {theme_id}。可用风格见 --list 输出，或直接输入风格名称（如 Mac / Linear / 水墨）。"
        )
    return theme


# ---------------------------------------------------------------------------
# 第 1 步：Markdown 预处理（复刻原站 Y6）
# ---------------------------------------------------------------------------
def preprocess(md):
    md = re.sub(r"^[ ]{0,3}(\*[ ]*\*[ ]*\*[\* ]*)[ \t]*$", "***", md, flags=re.M)
    md = re.sub(r"^[ ]{0,3}(-[ ]*-[ ]*-[- ]*)[ \t]*$", "---", md, flags=re.M)
    md = re.sub(r"^[ ]{0,3}(_[ ]*_[ ]*_[_ ]*)[ \t]*$", "___", md, flags=re.M)
    md = md.replace("** **", " ")
    md = re.sub(r"\*{4,}", "", md)
    # 粗体后紧跟标点：插入零宽空格，避免微信端换行把标点甩到下一行
    md = re.sub(
        r"([^\s])\*\*([+\-＋－%％~～!！?？,，.。:：;；、\\/|@#￥$^&*_=（）()【】\[\]《》〈〉「」『』“\"'\u0060…·][^\n*]*?)\*\*",
        lambda m: m.group(1) + "**" + "\u200b" + m.group(2) + "**",
        md,
    )
    return md


# ---------------------------------------------------------------------------
# 代码高亮：Mac 风格红绿灯 + hljs 类名（复刻原站 markdown-it highlight）
# ---------------------------------------------------------------------------
from pygments import highlight as pyg_highlight
from pygments.formatter import Formatter
from pygments.lexers import get_lexer_by_name
from pygments.token import Token

_TRAFFIC_DOTS = (
    '<div style="margin-bottom: 12px; white-space: nowrap;">'
    '<span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; '
    'background: #ff5f56; margin-right: 6px;"></span>'
    '<span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; '
    'background: #ffbd2e; margin-right: 6px;"></span>'
    '<span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; '
    'background: #27c93f;"></span></div>'
)


def _hljs_class(ttype):
    """pygments token -> hljs class（只输出原站配色映射用到的类）"""
    if ttype in Token.Comment:
        return "hljs-comment"
    if ttype in Token.Keyword:
        return "hljs-keyword"
    if ttype in Token.String:
        return "hljs-string"
    if ttype in Token.Number:
        return "hljs-number"
    if ttype in Token.Literal:
        return "hljs-literal"
    if ttype in Token.Name.Tag:
        return "hljs-tag"
    if ttype in Token.Name.Attribute:
        return "hljs-attr"
    if ttype in Token.Name.Builtin:
        return "hljs-built_in"
    if ttype in Token.Name.Class or ttype in Token.Name.Function or ttype in Token.Name.Exception \
            or ttype in Token.Name.Decorator or ttype in Token.Name.Namespace:
        return "hljs-title"
    if ttype in Token.Name.Variable or ttype in Token.Name.Constant:
        return "hljs-variable"
    return ""


class _HljsFormatter(Formatter):
    def format(self, tokensource, outfile):
        for ttype, value in tokensource:
            cls = _hljs_class(ttype)
            text = html_mod.escape(value, quote=False)
            if cls:
                outfile.write('<span class="%s">%s</span>' % (cls, text))
            else:
                outfile.write(text)


def _highlight_code(code, lang, attrs=None):
    escaped = html_mod.escape(code, quote=False)
    try:
        if lang:
            lexer = get_lexer_by_name(lang)
            highlighted = pyg_highlight(code, lexer, _HljsFormatter())
        else:
            highlighted = escaped
    except Exception:
        highlighted = escaped
    return "<pre>%s<code class=\"hljs\">%s</code></pre>" % (_TRAFFIC_DOTS, highlighted)


def build_markdown_it():
    return MarkdownIt("default", {
        "html": True,
        "linkify": True,
        "typographer": False,
        "highlight": _highlight_code,
    })


MD = build_markdown_it()


# ---------------------------------------------------------------------------
# 第 2 步：主题内联样式应用（复刻原站 K6）
# ---------------------------------------------------------------------------
# 标题内 strong/em/a/code 继承色覆盖（原站 c 映射）
_HEADING_INLINE_OVERRIDES = {
    "strong": "font-weight: 700; color: inherit !important; background-color: transparent !important;",
    "em": "font-style: italic; color: inherit !important; background-color: transparent !important;",
    "a": "color: inherit !important; text-decoration: none !important; border-bottom: 1px solid currentColor !important; background-color: transparent !important;",
    "code": "color: inherit !important; background-color: transparent !important; border: none !important; padding: 0 !important;",
}

# hljs 配色（原站 u 映射，GitHub 浅色系）
_HLJS_COLORS = {
    "hljs-comment": "color: #6a737d; font-style: normal;",
    "hljs-quote": "color: #6a737d; font-style: normal;",
    "hljs-keyword": "color: #d73a49; font-weight: 600;",
    "hljs-selector-tag": "color: #d73a49; font-weight: 600;",
    "hljs-string": "color: #032f62;",
    "hljs-title": "color: #6f42c1; font-weight: 600;",
    "hljs-section": "color: #6f42c1; font-weight: 600;",
    "hljs-type": "color: #005cc5; font-weight: 600;",
    "hljs-number": "color: #005cc5;",
    "hljs-literal": "color: #005cc5;",
    "hljs-built_in": "color: #005cc5;",
    "hljs-variable": "color: #e36209;",
    "hljs-template-variable": "color: #e36209;",
    "hljs-tag": "color: #22863a;",
    "hljs-name": "color: #22863a;",
    "hljs-attr": "color: #6f42c1;",
}

_IMG_STYLE_FULL = (
    "display:block; width:100%; max-width:100%; height:auto; margin:30px auto !important; "
    "padding:8px !important; border-radius:14px !important; box-sizing:border-box; "
    "box-shadow:0 16px 34px rgba(15,23,42,0.22), 0 4px 10px rgba(15,23,42,0.12); "
    "border:1px solid rgba(15,23,42,0.12);"
)
_IMG_STYLE_GRID = (
    "display:block; max-width:100%; height:auto; margin:0 !important; padding:8px !important; "
    "border-radius:14px !important; box-sizing:border-box; "
    "box-shadow:0 12px 28px rgba(15,23,42,0.18), 0 2px 8px rgba(15,23,42,0.12); "
    "border:1px solid rgba(255,255,255,0.75);"
)


def _is_whitespace(node):
    return isinstance(node, NavigableString) and not (node.string or "").strip()


def _single_image_child(p):
    """p 的唯一非空白子节点是否为 img（或包着单个 img 的 a）"""
    kids = [c for c in p.children if not _is_whitespace(c) and getattr(c, "name", None) != "br"]
    if len(kids) != 1:
        return None
    c = kids[0]
    if getattr(c, "name", None) == "img":
        return c
    if getattr(c, "name", None) == "a":
        grandchildren = [g for g in c.children if not _is_whitespace(g)]
        if len(grandchildren) == 1 and getattr(grandchildren[0], "name", None) == "img":
            return grandchildren[0]
    return None


def apply_theme(rendered_html, theme):
    """对 markdown-it 渲染结果应用主题内联样式，返回预览 HTML 片段"""
    r = theme["styles"]
    soup = BeautifulSoup(rendered_html, "html.parser")

    # --- 图片网格：连续的单图段落两两成行（复刻原站 K6 第一步） ---
    for parent in list(soup.find_all(["body", "div", "section", "blockquote", "li", "td"])):
        kids = [k for k in parent.children if getattr(k, "name", None)]
        i = 0
        while i < len(kids):
            if kids[i].name == "p" and _single_image_child(kids[i]):
                run = [kids[i]]
                j = i + 1
                while j < len(kids) and kids[j].name == "p" and _single_image_child(kids[j]):
                    run.append(kids[j])
                    j += 1
                for a, b in zip(run[0::2], run[1::2]):
                    grid = soup.new_tag("p")
                    grid["class"] = "image-grid"
                    grid["style"] = "display: flex; justify-content: center; gap: 8px; margin: 24px 0; align-items: flex-start;"
                    imga = _single_image_child(a)
                    imgb = _single_image_child(b)
                    imga.extract()
                    imgb.extract()
                    grid.append(imga)
                    grid.append(imgb)
                    a.replace_with(grid)
                    b.decompose()
                i = j
            else:
                i += 1

    # --- 段落内多图也按网格处理，并给网格内图片分配宽度 ---
    for p in list(soup.find_all("p")):
        if p.find_parent(class_="image-grid") is not None:
            continue
        kids = [c for c in p.children if not _is_whitespace(c)]
        if len(kids) < 2:
            continue
        if not all(getattr(k, "name", None) == "img" or
                   (getattr(k, "name", None) == "a" and k.find("img")) for k in kids):
            continue
        p["class"] = p.get("class", []) + ["image-grid"]
        p["style"] = "display: flex; justify-content: center; gap: 8px; margin: 24px 0; align-items: flex-start;"
        imgs = p.find_all("img")
        n = len(imgs)
        for img in imgs:
            img["style"] = "width: calc(%s%% - %spx); margin: 0; border-radius: 8px; height: auto;" % (
                round(100.0 / n, 4), round(8 * (n - 1) / n, 4))

    # --- 逐元素注入主题样式（跳过 container 与 pre 内的 code） ---
    for key, css in r.items():
        if key == "container" or key == "pre code":
            continue
        for el in soup.find_all(key):
            if key == "code" and getattr(el.parent, "name", None) == "pre":
                continue
            if el.name == "img" and el.find_parent(class_="image-grid") is not None:
                continue
            el["style"] = (el.get("style", "") + "; " + css).strip("; ")

    # --- 列表符号：ul→disc / ul ul→circle / ul ul ul→square / ol→decimal ---
    for ul in soup.find_all("ul"):
        ul["style"] = (ul.get("style", "") + "; list-style-type: disc !important; list-style-position: outside;").strip("; ")
        for sub in ul.find_all("ul", recursive=False):
            sub["style"] = (sub.get("style", "") + "; list-style-type: circle !important;").strip("; ")
            for subsub in sub.find_all("ul", recursive=False):
                subsub["style"] = (subsub.get("style", "") + "; list-style-type: square !important;").strip("; ")
    for ol in soup.find_all("ol"):
        ol["style"] = (ol.get("style", "") + "; list-style-type: decimal !important; list-style-position: outside;").strip("; ")

    # --- 代码高亮配色 ---
    for span in soup.select(".hljs span"):
        style = span.get("style", "")
        if style and not style.endswith(";"):
            style += "; "
        for cls in span.get("class", []):
            if cls in _HLJS_COLORS:
                style += _HLJS_COLORS[cls] + "; "
        if style:
            span["style"] = style

    # --- pre / 代码块内联细节 ---
    for pre in soup.find_all("pre"):
        pre["style"] = (pre.get("style", "") + "; font-variant-ligatures: none; tab-size: 2;").strip("; ")
    block_code_style = ("display: block; font-size: inherit !important; line-height: inherit !important; "
                        "font-style: normal !important; white-space: pre; word-break: normal; overflow-wrap: normal;")
    for el in soup.select("pre code, pre .hljs, .hljs"):
        el["style"] = (el.get("style", "") + "; " + block_code_style).strip("; ")

    # --- 标题内 strong/em/a/code 继承覆盖 ---
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        for tag, css in _HEADING_INLINE_OVERRIDES.items():
            for el in h.find_all(tag):
                el["style"] = (el.get("style", "") + "; " + css).strip("; ")

    # --- 图片最终样式 ---
    for img in soup.find_all("img"):
        in_grid = img.find_parent(class_="image-grid") is not None
        suffix = _IMG_STYLE_GRID if in_grid else _IMG_STYLE_FULL
        img["style"] = (img.get("style", "") + "; " + suffix).strip("; ")

    return soup


# ---------------------------------------------------------------------------
# 第 3 步：微信兼容处理（复刻原站 q6）
# ---------------------------------------------------------------------------
_IMG_CACHE = {}  # src -> data URL，跨主题复用，避免重复下载


def _to_data_url(src):
    """把本地文件 / 远程图片转为 base64 data URL；失败返回 None（保留原 URL）"""
    if src in _IMG_CACHE:
        return _IMG_CACHE[src]
    result = None
    try:
        if os.path.isfile(src):
            with open(src, "rb") as f:
                raw = f.read()
            ext = os.path.splitext(src)[1].lstrip(".").lower() or "png"
            mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
                    "webp": "webp", "svg": "svg+xml"}.get(ext, ext)
            result = "data:image/%s;base64,%s" % (mime, base64.b64encode(raw).decode())
        elif src.startswith(("http://", "https://")):
            req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw = resp.read()
            ctype = resp.headers.get("Content-Type", "image/png")
            result = "data:%s;base64,%s" % (ctype, base64.b64encode(raw).decode())
    except Exception:
        result = None
    _IMG_CACHE[src] = result
    return result


def wechat_compat(styled_soup, theme, img_map=None):
    """生成可直接粘贴到公众号后台的 HTML：section 包裹 + 微信兼容修复。

    img_map: {图片URL: base64 dataURL}，跨主题共享、按 URL 去重；
    返回的 HTML 中图片 src 保持原 URL，预览页/落盘时再替换为 base64，
    避免 30 款主题重复内嵌同一批 base64 导致文件臃肿。
    """
    if img_map is None:
        img_map = {}
    container = theme["styles"]["container"]
    soup = BeautifulSoup(str(styled_soup), "html.parser")
    body = soup.body or soup

    section = soup.new_tag("section")
    section["style"] = container

    children = [c for c in body.children if not _is_whitespace(c)]
    if len(children) == 1 and getattr(children[0], "name", None) == "div":
        for c in list(children[0].children):
            section.append(c.extract())
        children[0].decompose()
    else:
        for c in list(body.children):
            section.append(c.extract())
    body.append(section)

    # --- 图片网格 / flex 布局 → 表格（微信不塌陷） ---
    for el in list(soup.select("div.image-grid, p.image-grid")):
        style = el.get("style", "")
        is_flex = "display: flex" in style or "display:flex" in style
        if not (is_flex or "image-grid" in el.get("class", [])):
            continue
        v = [c for c in el.children if getattr(c, "name", None)]
        if v and all(k.name == "img" or k.find("img") for k in v):
            table = soup.new_tag("table")
            table["style"] = "width: 100%; border-collapse: collapse; margin: 16px 0; border: none !important;"
            tbody = soup.new_tag("tbody")
            tr = soup.new_tag("tr")
            tr["style"] = "border: none !important; background: transparent !important;"
            for se in v:
                td = soup.new_tag("td")
                td["style"] = "padding: 0 4px; vertical-align: top; border: none !important; background: transparent !important;"
                td.append(se.extract())
                if se.name == "img":
                    style_se = se.get("style", "")
                    se["style"] = re.sub(r"width:\s*[^;]+;?", "", style_se) + " width: 100% !important; display: block; margin: 0 auto;"
                tr.append(td)
            tbody.append(tr)
            table.append(tbody)
            el.replace_with(table)
        elif is_flex:
            el["style"] = re.sub(r"display:\s*flex;?", "display: block;", style)
        else:
            el["style"] = re.sub(r"display:\s*flex;?", "display: block;", style)

    # --- 其余 flex div → block ---
    for el in list(soup.find_all("div")):
        if el.find_parent("pre") is not None:
            continue
        style = el.get("style", "")
        if "display: flex" in style or "display:flex" in style:
            el["style"] = re.sub(r"display:\s*flex;?", "display: block;", style)

    # --- li 内块级子元素中的 p → span（微信列表不塌陷） ---
    for li in soup.find_all("li"):
        kids = [c for c in li.children if getattr(c, "name", None)]
        if any(k.name in ("p", "div", "ul", "ol", "blockquote") for k in kids):
            for p in li.find_all("p"):
                span = soup.new_tag("span")
                style = p.get("style")
                for c in list(p.children):
                    span.append(c.extract())
                if style:
                    span["style"] = style
                p.replace_with(span)

    # --- 容器字体/字号/颜色/行高继承到正文元素 ---
    fm = re.search(r"font-family:\s*([^;]+);", container)
    fs = re.search(r"font-size:\s*([^;]+);", container)
    col = re.search(r"color:\s*([^;]+);", container)
    lh = re.search(r"line-height:\s*([^;]+);", container)
    for el in soup.select("p, li, h1, h2, h3, h4, h5, h6, blockquote, span"):
        if el.name == "span" and el.find_parent(["pre", "code"]) is not None:
            continue
        style = el.get("style", "") or ""
        add = []
        if fm and "font-family:" not in style:
            add.append(" font-family: %s;" % fm.group(1))
        if lh and "line-height:" not in style:
            add.append(" line-height: %s;" % lh.group(1))
        if fs and "font-size:" not in style and el.name in ("p", "li", "blockquote", "span"):
            add.append(" font-size: %s;" % fs.group(1))
        if col and "color:" not in style:
            add.append(" color: %s;" % col.group(1))
        if add:
            el["style"] = (style + "".join(add)).strip()

    # --- 标点粘连：行尾行首标点不孤立（插入连接符） ---
    body_html = str(soup)
    body_html = re.sub(
        r"(</(?:strong|b|em|span|a|code)>)\s*([：；，。！？、])",
        lambda m: m.group(1) + "\u2060" + m.group(2),
        body_html,
    )

    # --- 图片转 base64（尽力而为，失败保留原 URL；成功则登记到 img_map） ---
    soup2 = BeautifulSoup(body_html, "html.parser")
    for img in soup2.find_all("img"):
        src = img.get("src", "")
        if src and not src.startswith("data:"):
            new_src = _to_data_url(src)
            if new_src:
                img_map[src] = new_src

    return str(soup2.section), img_map


# ---------------------------------------------------------------------------
# 完整管线
# ---------------------------------------------------------------------------
def render_article(md_text, theme_id, img_map=None):
    theme = find_theme(theme_id)
    rendered = MD.render(preprocess(md_text))
    styled = apply_theme(rendered, theme)
    wechat_html, img_map = wechat_compat(styled, theme, img_map)
    return theme, str(styled), wechat_html, img_map


def swap_images(html, img_map):
    """把 img_map 中的 URL 替换为 base64 dataURL（用于落盘的纯微信版 HTML）"""
    for url, data in img_map.items():
        html = html.replace('src="%s"' % url.replace("&", "&amp;"), 'src="%s"' % data)
    return html


# ---------------------------------------------------------------------------
# 预览页生成
# ---------------------------------------------------------------------------
def generate_preview(article_title, renders, img_map):
    """
    renders: list of (theme, styled_html, wechat_html)
    img_map: {占位符: base64 dataURL}，复制时替换，避免文件臃肿
    预览页内嵌全部渲染结果，支持切换风格 / 切换预览宽度 / 一键复制到公众号。
    """
    def _js_str(s):
        # JSON 文本本身就是合法 JS 表达式；只需防 </script> 提前闭合
        return s.replace("</script", "<\\/script")

    theme_options = "".join(
        '<option value="%s"%s>%s</option>' % (t["id"], " selected" if i == 0 else "", t["name"])
        for i, (t, _, _) in enumerate(renders)
    )
    article_divs = ""
    theme_data = []
    for i, (t, styled_html, wechat_html) in enumerate(renders):
        article_divs += (
            '<div class="article-wrap" data-theme="%s" style="%s">%s</div>\n'
            % (t["id"], t["styles"]["container"], styled_html)
        )
        theme_data.append({"id": t["id"], "name": t["name"], "desc": t["description"],
                           "category": t["category"], "html": wechat_html})
    theme_json = _js_str(json.dumps(theme_data, ensure_ascii=False))
    img_json = _js_str(json.dumps(img_map, ensure_ascii=False))

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>冷檬排版 · <!--TITLE--> · 公众号预览</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; background: #f2f3f5; color: #1d1d1f; }
  .topbar { position: sticky; top: 0; z-index: 50; background: rgba(255,255,255,.92); backdrop-filter: blur(12px); border-bottom: 1px solid #e5e7eb; padding: 12px 20px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .brand { font-weight: 700; font-size: 15px; color: #111; white-space: nowrap; }
  .brand span { color: #999; font-weight: 400; margin-left: 6px; font-size: 12px; }
  .title { font-size: 13px; color: #555; flex: 1; min-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ctl { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  select, button { font-size: 13px; border-radius: 8px; border: 1px solid #d1d5db; background: #fff; padding: 7px 12px; cursor: pointer; }
  select:focus, button:focus { outline: 2px solid #0066cc55; }
  .seg { display: flex; background: #ececee; border-radius: 10px; padding: 3px; }
  .seg button { border: none; background: transparent; padding: 6px 12px; border-radius: 8px; color: #666; }
  .seg button.on { background: #fff; color: #111; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .copy-btn { background: #07c160; border-color: #07c160; color: #fff; font-weight: 600; }
  .copy-btn:hover { background: #06ad56; }
  .copy-btn.done { background: #111; }
  .desc { width: 100%; font-size: 12px; color: #999; }
  .stage { padding: 28px 16px 60px; }
  .frame { margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,.08); overflow: hidden; transition: max-width .25s ease; max-width: 480px; }
  .frame.tablet { max-width: 768px; }
  .frame.pc { max-width: 1080px; }
  .article-wrap { display: none; }
  .article-wrap.on { display: block; }
  .toast { position: fixed; left: 50%; bottom: 48px; transform: translateX(-50%); background: rgba(0,0,0,.8); color: #fff; font-size: 13px; padding: 10px 18px; border-radius: 10px; opacity: 0; pointer-events: none; transition: opacity .25s; z-index: 99; }
  .toast.show { opacity: 1; }
  .tip { max-width: 640px; margin: 0 auto 18px; font-size: 12px; color: #888; line-height: 1.7; }
  .tip b { color: #07c160; }
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">冷檬排版<span>复刻 markdown.gmlart.cn</span></div>
  <div class="title" id="pageTitle"><!--TITLE--></div>
  <div class="ctl">
    <select id="themeSelect" title="切换排版风格"><!--THEME_OPTIONS--></select>
    <div class="seg" id="deviceSeg">
      <button data-device="mobile" class="on" title="手机视图 480px">手机</button>
      <button data-device="tablet" title="平板视图 768px">平板</button>
      <button data-device="pc" title="桌面视图">桌面</button>
    </div>
    <button class="copy-btn" id="copyBtn">复制到公众号</button>
  </div>
  <div class="desc" id="descBar"></div>
</div>
<div class="stage">
  <div class="tip">提示：点击「<b>复制到公众号</b>」后，直接到公众号后台编辑器 <b>Ctrl/Cmd + V</b> 粘贴，排版格式完整保留（背景色、字体、间距、代码块、表格、图片均内联）。切换风格后重新复制即可。</div>
  <div class="frame" id="frame">
<!--ARTICLE_DIVS-->
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
var THEMES = <!--THEME_JSON-->;
var IMG_MAP = <!--IMG_JSON-->;
var activeTheme = THEMES[0].id;

function showToast(msg) {
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(function(){ t.classList.remove('show'); }, 2000);
}

function renderTheme() {
  document.querySelectorAll('.article-wrap').forEach(function(w){ w.classList.toggle('on', w.getAttribute('data-theme') === activeTheme); });
  var td = THEMES.find(function(x){ return x.id === activeTheme; });
  document.getElementById('descBar').textContent = td ? ('当前风格：' + td.name + ' · ' + td.desc) : '';
  document.getElementById('themeSelect').value = activeTheme;
}

function copyHtml() {
  var td = THEMES.find(function(x){ return x.id === activeTheme; });
  if (!td) return;
  var html = td.html;
  for (var k in IMG_MAP) {
    html = html.split('src="' + k.replace(/&/g, '&amp;') + '"').join('src="' + IMG_MAP[k] + '"');
  }
  var holder = document.createElement('div');
  holder.innerHTML = html;
  var node = holder.firstElementChild;
  html = node ? node.outerHTML : html;
  var text = holder.innerText || holder.textContent;
  var done = function(){ showToast('已复制！请到公众号后台 Ctrl/Cmd + V 粘贴'); var b = document.getElementById('copyBtn'); b.classList.add('done'); b.textContent = '已复制 ✓'; setTimeout(function(){ b.classList.remove('done'); b.textContent = '复制到公众号'; }, 2000); };
  try {
    if (navigator.clipboard && window.ClipboardItem) {
      navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], {type: 'text/html'}),
          'text/plain': new Blob([text], {type: 'text/plain'})
        })
      ]).then(done).catch(function(){ legacyCopy(html); done(); });
      return;
    }
  } catch(e) {}
  legacyCopy(html); done();
}

function legacyCopy(html) {
  var c = document.createElement('div');
  c.contentEditable = 'true';
  c.style.position = 'fixed';
  c.style.left = '-9999px';
  c.innerHTML = html;
  document.body.appendChild(c);
  var sel = window.getSelection();
  sel.removeAllRanges();
  var range = document.createRange();
  range.selectNodeContents(c);
  sel.addRange(range);
  try { document.execCommand('copy'); } catch(e) {}
  document.body.removeChild(c);
}

document.getElementById('copyBtn').addEventListener('click', copyHtml);
document.getElementById('themeSelect').addEventListener('change', function(e){ activeTheme = e.target.value; renderTheme(); });
document.getElementById('deviceSeg').addEventListener('click', function(e){
  var b = e.target.closest('button'); if (!b) return;
  document.querySelectorAll('#deviceSeg button').forEach(function(x){ x.classList.remove('on'); });
  b.classList.add('on');
  var f = document.getElementById('frame');
  f.className = 'frame' + (b.getAttribute('data-device') !== 'mobile' ? ' ' + b.getAttribute('data-device') : '');
});
renderTheme();
</script>
</body>
</html>
"""
    page = (page
            .replace("<!--TITLE-->", html_mod.escape(article_title))
            .replace("<!--THEME_OPTIONS-->", theme_options)
            .replace("<!--ARTICLE_DIVS-->", article_divs)
            .replace("<!--THEME_JSON-->", theme_json)
            .replace("<!--IMG_JSON-->", img_json))
    return page


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_catalog():
    print("冷檬排版 · 30 款排版风格")
    print("=" * 60)
    for cat in ("经典", "潮流", "更多风格"):
        print("\n【%s】" % cat)
        for t in [x for x in THEMES if x["category"] == cat]:
            print("  %-4s %-12s %s" % (t["id"], t["name"], t["description"]))


def main():
    ap = argparse.ArgumentParser(description="冷檬排版 - 公众号 Markdown 排版引擎")
    ap.add_argument("--md", help="Markdown 文章文件路径")
    ap.add_argument("--theme", default="apple", help="排版风格 id（默认 apple/Mac；传 '全部' 输出全部 30 款）")
    ap.add_argument("--title", default="", help="文章标题（用于预览页）")
    ap.add_argument("--out", default=".", help="输出目录")
    ap.add_argument("--list", action="store_true", help="列出全部排版风格")
    args = ap.parse_args()

    if args.list or not args.md:
        print_catalog()
        if not args.md:
            return

    with open(args.md, encoding="utf-8") as f:
        md_text = f.read()

    os.makedirs(args.out, exist_ok=True)
    title = args.title or os.path.splitext(os.path.basename(args.md))[0]

    # 预览页始终内嵌全部 30 款（可切换对比）；选中的主题排在最前作为默认展示
    selected = "全部" if args.theme == "全部" else find_theme(args.theme)["id"]
    theme_ids = [selected] + [t["id"] for t in THEMES if t["id"] != selected] if selected != "全部" \
        else [t["id"] for t in THEMES]

    renders = []
    shared_img_map = {}
    for tid in theme_ids:
        theme, styled_html, wechat_html, img_map = render_article(md_text, tid, shared_img_map)
        renders.append((theme, styled_html, wechat_html))

    # article-<id>.html：默认只输出选中的主题；--theme 全部 时输出全部 30 款
    dump_ids = theme_ids if selected == "全部" else [selected]
    for tid in dump_ids:
        wechat_html = next(r[2] for r in renders if r[0]["id"] == tid)
        wechat_path = os.path.join(args.out, "article-%s.html" % tid)
        with open(wechat_path, "w", encoding="utf-8") as f:
            f.write(swap_images(wechat_html, shared_img_map))
        print("已生成: %s (主题 %s · %s)" % (wechat_path, THEME_BY_ID[tid]["id"], THEME_BY_ID[tid]["name"]))

    preview_path = os.path.join(args.out, "preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(generate_preview(title, renders, shared_img_map))
    print("已生成: %s" % preview_path)
    print("打开 preview.html 预览效果并一键复制到公众号；article-<id>.html 为纯微信版 HTML。")


if __name__ == "__main__":
    main()
