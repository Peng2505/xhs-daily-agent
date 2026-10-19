#!/usr/bin/env python
"""Temp research helper: Bing search + page fetch over DIRECT connections.

Why: Windows system proxy 127.0.0.1:2023 refuses connections, which breaks
Hermes' firecrawl-backed web_search/web_extract. We fetch directly instead.
"""
import html
import re
import sys
import urllib.parse
import urllib.request

OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0")


def fetch(url, timeout=20, as_bytes=False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with OP.open(req, timeout=timeout) as r:
        raw = r.read()
    return raw if as_bytes else raw.decode("utf-8", "replace")


def strip_tags(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def bing(q, n=12):
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(q)
    try:
        page = fetch(url)
    except Exception as e:
        return [("ERR", type(e).__name__, str(e)[:120])]
    out = []
    for block in re.findall(r'(?is)<li class="b_algo".*?</li>', page):
        m = re.search(r'(?is)<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block)
        if not m:
            continue
        href, title = m.group(1), strip_tags(m.group(2))
        cap = re.search(r'(?is)<p[^>]*>(.*?)</p>', block)
        snip = strip_tags(cap.group(1)) if cap else ""
        out.append((title, href, snip[:300]))
        if len(out) >= n:
            break
    return out


def main():
    mode = sys.argv[1]
    if mode == "search":
        for q in sys.argv[2:]:
            print("=" * 20, "QUERY:", q)
            for t, u, s in bing(q):
                print("-", t)
                print("  ", u)
                print("  ", s)
    elif mode == "get":
        for u in sys.argv[2:]:
            print("=" * 20, u)
            try:
                txt = strip_tags(fetch(u))
            except Exception as e:
                print("ERR", type(e).__name__, str(e)[:150])
                continue
            print("LEN", len(txt))
            print(txt[:4000])


if __name__ == "__main__":
    main()
