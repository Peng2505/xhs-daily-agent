"""Careful note-manager acceptance check (skill pitfall 19).

Clicks each status tab, *confirms* which tab is active, then reads titles
(+y) and permission_msg elements (+y) so ownership can be judged by geometry.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cdp import CDP  # noqa: E402

TARGET = "10月8日AI速览：5件事"

READ = r"""(() => {
  const act = Array.from(document.querySelectorAll('.tab-item'))
    .filter(e => /active|selected/.test(e.className))
    .map(e => e.innerText.trim());
  const titles = Array.from(document.querySelectorAll('.note-card__title')).map(e => {
    const r = e.getBoundingClientRect();
    return {t: e.innerText.trim().slice(0, 40), y: Math.round(r.y)};
  });
  const perms = Array.from(document.querySelectorAll('[class*=permission]')).map(e => {
    const r = e.getBoundingClientRect();
    return {t: e.innerText.trim().slice(0, 24), y: Math.round(r.y)};
  });
  const empty = document.body.innerText.indexOf('暂无') >= 0;
  return JSON.stringify({active: act, titles: titles, perms: perms, hasEmpty: empty});
})()"""


def main():
    c = CDP(url_contains="creator.xiaohongshu.com")
    c.send("Page.enable")
    c.navigate("https://creator.xiaohongshu.com/new/note-manager", wait=7)
    print("url:", c.js("location.href"))
    tabs = c.js("Array.from(document.querySelectorAll('.tab-item')).map(e=>e.innerText.trim())")
    print("tabs:", tabs)
    for want in ("审核中", "已发布", "未通过", "全部"):
        ok = c.js("""(() => {
          const ts = Array.from(document.querySelectorAll('.tab-item'));
          const t = ts.find(e => e.innerText.trim().indexOf(%s) >= 0);
          if (t) { t.click(); return true; } return false; })()""" % json.dumps(want))
        time.sleep(4)
        raw = c.js(READ)
        print("\n=== %s (clicked=%s) ===" % (want, ok))
        print(raw)
        try:
            d = json.loads(raw)
        except Exception:
            continue
        hits = [t for t in d["titles"] if t["t"] == TARGET]
        if hits:
            hy = hits[0]["y"]
            near = [p for p in d["perms"] if abs(p["y"] - hy) <= 120]
            print("TARGET in '%s': y=%s | permission near card: %s"
                  % (want, hy, near if near else "NONE -> 公开可见"))
    c.close()


if __name__ == "__main__":
    main()
