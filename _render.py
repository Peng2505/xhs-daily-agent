"""Render cover.html / points.html to 1080x1440 PNG using the dedicated Edge via CDP."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cdp import CDP, pick_page

OUT_DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-04"
OUT = os.path.join(r"D:\Hermes Project\xhs-daily\out", OUT_DATE)


def main():
    t = pick_page()
    c = CDP(ws_url=t["webSocketDebuggerUrl"])
    c.send("Page.enable")
    c.send("Emulation.setDeviceMetricsOverride", width=1080, height=1440,
           deviceScaleFactor=1, mobile=False)
    for name in ("cover", "points"):
        url = "file:///D:/Hermes%20Project/xhs-daily/out/{}/{}.html".format(OUT_DATE, name)
        c.navigate(url, wait=2.0)
        path = os.path.join(OUT, name + ".png")
        c.screenshot(path)
        print(name, os.path.getsize(path), "w/h:",
              c.js("window.innerWidth"), c.js("window.innerHeight"),
              "scroll:", c.js("document.documentElement.scrollHeight"))
    c.send("Emulation.clearDeviceMetricsOverride")
    print("cleared; dpr now", c.js("window.devicePixelRatio"))
    print(sorted(os.listdir(OUT)))
    c.close()


if __name__ == "__main__":
    main()
