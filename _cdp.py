"""Minimal synchronous CDP client for the dedicated Edge instance (port 9222).

Used because the browser_exec helper CLI exits 1 without output on this host.
Everything here is CSS-pixel space (DOM.getBoxModel / Input.dispatchMouseEvent),
matching skill rules: no DPR guessing.
"""
import json
import os
import urllib.request

# The Windows system proxy (127.0.0.1:2023) is frequently down; urllib *and*
# websockets pick it up, then fail on plain localhost with a bogus
# ConnectionRefused. Neutralise it process-wide before any connection is made.
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

from websockets.sync.client import connect  # noqa: E402

PORT = 9222

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def targets():
    with OPENER.open(f"http://127.0.0.1:{PORT}/json/list", timeout=5) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def pick_page(url_contains=None):
    pages = [t for t in targets() if t.get("type") == "page"]
    if url_contains:
        for t in pages:
            if url_contains in t.get("url", ""):
                return t
    return pages[0] if pages else None


class CDP:
    def __init__(self, ws_url=None, url_contains=None, timeout=30):
        if ws_url is None:
            t = pick_page(url_contains)
            if not t:
                raise RuntimeError("no page target")
            ws_url = t["webSocketDebuggerUrl"]
        self.ws = connect(ws_url, max_size=None, open_timeout=timeout)
        self.i = 0

    def send(self, method, timeout=30, **params):
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv(timeout=timeout))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr, timeout=30):
        r = self.send("Runtime.evaluate", timeout=timeout, expression=expr,
                      returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def navigate(self, url, wait=2.5, timeout=30):
        self.send("Page.navigate", url=url, timeout=timeout)
        import time
        time.sleep(wait)

    def screenshot(self, path, timeout=60, quality=None):
        params = {"format": "png"}
        r = self.send("Page.captureScreenshot", timeout=timeout, **params)
        import base64
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))
        return path

    def node_id(self, selector):
        doc = self.send("DOM.getDocument", depth=-1)
        n = self.send("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
        return n.get("nodeId")

    def box(self, backend_node_id):
        m = self.send("DOM.getBoxModel", backendNodeId=backend_node_id)["model"]["content"]
        xs, ys = m[0::2], m[1::2]
        return round(sum(xs) / 4), round(sum(ys) / 4)

    def click_xy(self, x, y):
        for t in ("mousePressed", "mouseReleased"):
            self.send("Input.dispatchMouseEvent", type=t, x=x, y=y,
                      button="left", clickCount=1)

    def ax_buttons(self, name):
        nodes = self.send("Accessibility.getFullAXTree")["nodes"]
        out = []
        for n in nodes:
            nm = (n.get("name") or {}).get("value")
            role = (n.get("role") or {}).get("value")
            if nm == name and role == "button" and n.get("backendDOMNodeId"):
                out.append(n)
        return out

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass
