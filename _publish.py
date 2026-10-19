"""Xiaohongshu publish driver (raw CDP, staged).

Usage: python _publish.py <stage>
  upload  - open publish page, switch to image+text tab, attach the 2 PNGs
  fill    - type title + body (tiptap setContent -> real paragraphs)
  publish - click the 发布 button via the documented fallback chain
  draft   - click 暂存离开 (save to drafts) as the fallback
  verify  - inspect note-manager tabs + permission_msg ownership
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cdp import CDP, OPENER  # noqa: E402

OUT_DATE = sys.argv[2] if len(sys.argv) > 2 else "2026-10-04"
OUT = os.path.join(r"D:\Hermes Project\xhs-daily\out", OUT_DATE)
PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"


def body_lines():
    lines = []
    with open(os.path.join(OUT, "body.txt"), encoding="utf-8") as f:
        for i, ln in enumerate(f.read().splitlines()):
            if i == 0:
                continue  # title line, goes into the title field
            ln = ln.strip()
            if ln:
                lines.append(ln)
    return lines


def read_title():
    with open(os.path.join(OUT, "body.txt"), encoding="utf-8") as f:
        first = f.readline().strip()
    return first.split(":", 1)[1].strip() if ":" in first else first


TITLE = read_title()


def conn():
    c = CDP(url_contains="creator.xiaohongshu.com")
    c.send("Page.enable")
    return c


def state(c, tag):
    print("[%s] url=%s" % (tag, c.js("location.href")))
    print("[%s] title=%s" % (tag, c.js("document.title")))
    txt = c.js("document.body ? document.body.innerText.replace(/\\n+/g,' | ').slice(0,600) : ''")
    print("[%s] text=%s" % (tag, txt))
    return txt


def stage_upload():
    c = conn()
    c.navigate(PUBLISH_URL, wait=6)
    state(c, "after-nav")
    r = c.js("""(() => {
      const vis = Array.from(document.querySelectorAll('.creator-tab'))
        .filter(e => { const r = e.getBoundingClientRect(); return r.width>0 && r.x>-100; });
      const t = vis.find(e => (e.innerText||'').includes('\u4e0a\u4f20\u56fe\u6587'));
      if (t) { t.click(); return 'clicked'; } return 'no tab';
    })()""")
    print("tab:", r)
    time.sleep(4)
    sel = c.node_id("input[type=file]")
    print("file input nodeId:", sel)
    files = [os.path.join(OUT, "cover.png"), os.path.join(OUT, "points.png")]
    c.send("DOM.setFileInputFiles", nodeId=sel, files=files)
    time.sleep(12)
    print("img editor:", c.js("(() => { const m=document.body.innerText.match(/\\u56fe\\u7247\\u7f16\\u8f91\\s*\\d+\\/\\d+/); return m?m[0]:'none'; })()"))
    print("thumbs:", c.js("document.querySelectorAll('img').length"))
    state(c, "upload-done")
    c.close()


def stage_fill():
    c = conn()
    # title: focus via JS then insert text through the CDP Input domain
    ok = c.js("""(() => {
      const el = document.querySelector('input[placeholder*="\u586b\u5199\u6807\u9898"], input[placeholder*="\u6807\u9898"]');
      if (!el) return 'no input';
      el.focus(); el.click();
      return document.activeElement === el ? 'focused' : 'focus-failed:' + document.activeElement.tagName;
    })()""")
    print("title focus:", ok)
    c.send("Input.insertText", text=TITLE)
    time.sleep(1)
    print("title value:", c.js("(() => { const el=document.querySelector('input[placeholder*=\"\\u6807\\u9898\"]'); return el ? el.value : 'none'; })()"))

    lines = body_lines()
    payload = "".join("<p>%s</p>" % ln for ln in lines)
    r = c.js("""(() => {
      const ed = document.querySelector('div[contenteditable=true].ProseMirror');
      if (!ed) return 'no editor';
      const inst = ed.editor;
      if (inst && inst.commands) {
        inst.commands.setContent(%s, true);
        return 'setContent:' + ed.innerText.length;
      }
      return 'no instance';
    })()""" % json.dumps(payload))
    print("body write:", r)
    time.sleep(1)
    print("body readback len:", c.js("document.querySelector('div.ProseMirror').innerText.length"))
    print("body paragraphs:", c.js("document.querySelector('div.ProseMirror').children.length"))
    print("body head:", c.js("document.querySelector('div.ProseMirror').innerText.slice(0,160).replace(/\\n/g,' | ')"))
    print("title now:", c.js("(() => { const el=document.querySelector('input[placeholder*=\"\\u6807\\u9898\"]'); return el ? el.value : 'none'; })()"))
    c.close()


def click_by_ax(c, name):
    btns = c.ax_buttons(name)
    print("ax buttons named", name, ":", len(btns))
    if not btns:
        return False
    b = btns[-1]
    try:
        x, y = c.box(b["backendDOMNodeId"])
        print("clicking at", x, y)
        c.click_xy(x, y)
        return True
    except Exception as e:
        print("box model failed:", str(e)[:120])
        return False


def click_by_dom(c, name):
    nodes = c.ax_buttons(name)
    if not nodes:
        return "no node"
    nid = nodes[-1]["backendDOMNodeId"]
    r = c.send("DOM.resolveNode", backendNodeId=nid)
    obj = r["object"]["objectId"]
    res = c.send("Runtime.callFunctionOn", objectId=obj,
                 functionDeclaration="function(){ this.click(); return 'clicked'; }",
                 returnByValue=True)
    return res.get("result", {}).get("value")


def stage_publish():
    c = conn()
    state(c, "pre-publish")
    if not click_by_ax(c, "\u53d1\u5e03"):
        print("fallback dom click:", click_by_dom(c, "\u53d1\u5e03"))
    time.sleep(6)
    state(c, "post-publish")
    # any confirm dialog?
    print("dialog text:", c.js("(() => { const d=document.querySelector('.d-modal, .modal, [role=dialog]'); return d? d.innerText.slice(0,200) : 'none'; })()"))
    c.close()


def stage_draft():
    c = conn()
    if not click_by_ax(c, "\u6682\u5b58\u79bb\u5f00"):
        print("fallback dom click:", click_by_dom(c, "\u6682\u5b58\u79bb\u5f00"))
    time.sleep(5)
    state(c, "post-draft")
    c.close()


def stage_publish_dom():
    c = conn()
    state(c, "pre-dom-publish")
    print("dom click:", click_by_dom(c, "\u53d1\u5e03"))
    time.sleep(8)
    state(c, "post-dom-publish")
    print("dialog text:", c.js("(() => { const d=document.querySelector('.d-modal, .modal, [role=dialog]'); return d? d.innerText.slice(0,300) : 'none'; })()"))
    c.close()


def stage_verify():
    c = conn()
    c.navigate("https://creator.xiaohongshu.com/new/note-manager", wait=6)
    tabs = c.js("Array.from(document.querySelectorAll('.tab-item')).map(e=>e.innerText.trim())")
    print("tabs:", tabs)
    for want in ("\u5ba1\u6838\u4e2d", "\u5df2\u53d1\u5e03"):
        c.js("""(() => { const ts=Array.from(document.querySelectorAll('.tab-item'));
          const t=ts.find(e=>e.innerText.trim().indexOf(%s)>=0); if(t) t.click(); return !!t; })()""" % json.dumps(want))
        time.sleep(4)
        info = c.js("""(() => {
          const cards = Array.from(document.querySelectorAll('.note-card__title, .note-card'));
          const titles = Array.from(document.querySelectorAll('.note-card__title')).map(e => {
            const r = e.getBoundingClientRect();
            return {t: e.innerText.trim().slice(0,40), y: Math.round(r.y)};
          });
          const perms = Array.from(document.querySelectorAll('[class*=permission]')).map(e => {
            const r = e.getBoundingClientRect();
            return {t: e.innerText.trim().slice(0,20), y: Math.round(r.y)};
          });
          return JSON.stringify({titles: titles.slice(0,6), perms: perms.slice(0,6)});
        })()""")
        print(want, "->", info)
    print("body head:", c.js("document.body.innerText.slice(0,400).replace(/\\n+/g,' | ')"))
    c.close()


if __name__ == "__main__":
    {"upload": stage_upload, "fill": stage_fill, "publish": stage_publish,
     "publish_dom": stage_publish_dom,
     "draft": stage_draft, "verify": stage_verify}[sys.argv[1]]()
