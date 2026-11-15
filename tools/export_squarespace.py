#!/usr/bin/env python3
"""Export the old Squarespace site (zlatko-minev.com) collections to data/raw/.

Uses Squarespace's public `?format=json` view; follows pagination. Writes one JSON
file per collection with title, date, old URL, categories, tags, media ids and the
post body as plain text plus raw HTML (for migrating posts to /writing/).
"""
import json, re, sys, time, urllib.request, html
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://www.zlatko-minev.com"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
COLLECTIONS = ["blog", "blog-int", "talks-and-interviews-gallery"]
YT = re.compile(r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})")


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []
    def handle_data(self, d): self.out.append(d)
    def handle_starttag(self, tag, a):
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4"): self.out.append("\n")


def text(h):
    t = Text(); t.feed(h or ""); return re.sub(r"\n\s*\n+", "\n\n", html.unescape("".join(t.out))).strip()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site export)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def export(col):
    items, url = [], f"{BASE}/{col}?format=json"
    while url:
        j = get(url)
        items += j.get("items", [])
        pg = j.get("pagination") or {}
        url = (BASE + pg["nextPageUrl"] + "&format=json") if pg.get("nextPage") else None
        time.sleep(0.5)
    rows = []
    for x in items:
        blob = json.dumps(x)
        rows.append({
            "title": x.get("title"),
            "date": time.strftime("%Y-%m-%d", time.gmtime((x.get("publishOn") or x.get("addedOn")) / 1000)),
            "old_url": x.get("fullUrl"),
            "categories": x.get("categories") or [],
            "tags": x.get("tags") or [],
            "youtube": (YT.search(blob) or [None, None])[1],
            "image": x.get("assetUrl"),
            "excerpt": text(x.get("excerpt")),
            "body_text": text(x.get("body")),
            "body_html": x.get("body") or "",
        })
    (OUT / f"squarespace_{col}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{col}: {len(rows)} items")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for c in (sys.argv[1:] or COLLECTIONS):
        export(c)
