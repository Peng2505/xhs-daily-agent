#!/usr/bin/env python
"""Build the daily Xiaohongshu (小红书) 图文 assets from a content JSON spec.

Usage:
    python build_publish.py <spec.json>

Spec shape:
    {
      "date": "2026-09-14",
      "title": "9月14日AI速览：5件事",        # <= 20 chars (小红书 hard limit)
      "hook": "90秒看完，不废话",
      "bullets": ["...", "...", "...", "...", "..."],
      "tags": ["AI日报", "大模型", "人工智能"],
      "body_extra": "可选：结尾一句话",
      "sources": [                            # 可选但强烈建议：每条要点对应的已核实原文
        {"name": "Anthropic", "url": "https://www.anthropic.com/news/..."},
      ]
    }

sources 会在正文末尾渲染成一行「来源：名称 URL / …」；缺 url 的条目会告警，
全部缺 url 时不计入。没给 sources 就退回用 body_extra 里手写的那行（向后兼容）。

Writes to out/<date>/:
    cover.html   -> 1080x1440 cover card      (screenshot this with browser_exec)
    points.html  -> 1080x1440 5-bullet card   (screenshot this with browser_exec)
    body.txt     -> exact 标题/正文 to paste into the 小红书 editor
Also prints the body so the agent can copy it straight into the editor.
"""
import html
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
  html,body{{margin:0;padding:0;}}
  body{{width:1080px;height:1440px;box-sizing:border-box;
    background:linear-gradient(150deg,#0b1020 0%,#1b1f4b 55%,#3b1d5e 100%);
    font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#fff;
    padding:88px 80px;display:flex;flex-direction:column;justify-content:space-between;
    overflow:hidden;}}
  .tag{{display:inline-block;font-size:34px;letter-spacing:2px;
    border:3px solid rgba(255,255,255,.55);border-radius:999px;padding:14px 34px;opacity:.85;}}
  h1{{font-size:{h1size}px;line-height:1.22;margin:52px 0 0;font-weight:900;letter-spacing:2px;}}
  h1 em{{font-style:normal;background:linear-gradient(90deg,#7ef0d0,#7aa2ff);
    -webkit-background-clip:text;background-clip:text;color:transparent;}}
  .sub{{font-size:38px;line-height:1.5;opacity:.8;margin-top:40px;}}
  ul{{list-style:none;padding:0;margin:0;font-size:{lisize}px;line-height:1.6;}}
  li{{margin-bottom:{ligap}px;display:flex;gap:20px;align-items:flex-start;}}
  li b{{color:#7ef0d0;font-weight:900;flex:0 0 auto;}}
  li span{{flex:1 1 auto;}}
  .foot{{display:flex;justify-content:space-between;align-items:flex-end;font-size:30px;opacity:.55;}}
</style></head><body>
{content}
</body></html>
"""


def cover_html(spec):
    content = f"""  <div><span class="tag">AI 日报 · DAILY</span></div>
  <div>
    <h1>{html.escape(spec['title'])}</h1>
    <div class="sub">{html.escape(spec.get('hook', ''))}</div>
  </div>
  <div class="foot"><span>{html.escape(spec.get('handle', ''))}</span><span>{html.escape(spec['date'])}</span></div>"""
    return PAGE.format(h1size=92, lisize=36, ligap=18, content=content)


_LEAD = re.compile(r"^[0-9\u20e3\u2b50\ufe0f\u20e3\s\.\u3001]*")


def _strip_lead(text):
    """Drop a leading '1' / '1️⃣' / '1. ' marker — the card numbers the list itself."""
    return _LEAD.sub("", text).strip()


def points_html(spec):
    items = "".join(
        f'<li><b>{i}</b><span>{html.escape(_strip_lead(b))}</span></li>'
        for i, b in enumerate(spec["bullets"], 1)
    )
    content = f"""  <div><span class="tag">{html.escape(spec['date'])} · AI 速览</span></div>
  <ul>{items}</ul>
  <div class="foot"><span>{html.escape(spec.get('handle', ''))}</span><span>{(spec.get('tags') or [''])[0]}</span></div>"""
    return PAGE.format(h1size=80, lisize=40, ligap=34, content=content)


def source_line(spec):
    """Render {'sources': [{'name','url'}]} into one '来源：…' line.

    Entries without a url are dropped with a warning — a source name alone
    can't be re-verified later, which is exactly how the 2026-09-14 run lost
    its links. Returns '' when nothing usable is present.
    """
    parts = []
    for i, s in enumerate(spec.get("sources") or []):
        if isinstance(s, dict):
            name = str(s.get("name") or "").strip()
            url = str(s.get("url") or "").strip()
        else:
            name, url = str(s).strip(), ""
        if not url:
            print(f"WARN: sources[{i}] {name!r} 缺 url，已丢弃（来源名无法回溯核实）")
            continue
        if not url.startswith("http"):
            print(f"WARN: sources[{i}] url 不是 http(s)，已丢弃: {url}")
            continue
        parts.append(f"{name} {url}".strip())
    return "来源：" + " / ".join(parts) if parts else ""


def build_body(spec):
    bullets = "\n\n".join(spec["bullets"])
    tags = " ".join("#" + t.strip("#") + "#" for t in spec.get("tags", []))
    tail = spec.get("body_extra", "").strip()
    body = f"{bullets}"
    for extra in (tail, source_line(spec)):
        if extra:
            body += f"\n\n{extra}"
    if tags:
        body += f"\n\n{tags}"
    return body


def main():
    if len(sys.argv) < 2:
        print("usage: build_publish.py <spec.json>")
        return 2
    with open(sys.argv[1], encoding="utf-8") as fh:
        spec = json.load(fh)

    title = spec["title"].strip()
    if len(title) > 20:
        print(f"WARN: 标题 {len(title)} 字，超过小红书 20 字上限，已截断")
        title = title[:20]

    body = build_body(spec)
    if len(body) > 1000:
        print(f"WARN: 正文 {len(body)} 字，超过 1000 字上限")

    outdir = os.path.join(BASE, "out", spec["date"])
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "cover.html"), "w", encoding="utf-8") as fh:
        fh.write(cover_html(dict(spec, title=title)))
    with open(os.path.join(outdir, "points.html"), "w", encoding="utf-8") as fh:
        fh.write(points_html(spec))
    with open(os.path.join(outdir, "body.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"标题（{len(title)}字）: {title}\n\n{body}\n")

    print(f"title[{len(title)}]: {title}")
    print(f"body[{len(body)} chars]:")
    print(body)
    print(f"\nfiles -> {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
