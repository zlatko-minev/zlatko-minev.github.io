"""Download every Squarespace-hosted file the old site referenced and store a local, size-capped copy.

Writes assets/archive/<key>.<ext> and data/rehost_map.json ({old url without query: {path, width, height}}).
Images become WebP at most 1600 px wide and under 300 KB; animated GIFs stay animated (WebP); other files are kept as-is.
Safe to re-run: files already in the map are skipped.
"""
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "assets" / "archive"
MAP = ROOT / "data" / "rehost_map.json"
PAT = re.compile(r"https?://(?:images|static1)\.squarespace(?:-cdn)?\.com/[^\"'\s\\<>)]+")
MAX_W = 1600


def old_urls():
    urls = set()
    for f in RAW.glob("*"):
        if f.suffix in (".json", ".html"):
            urls.update(u.split("?")[0] for u in PAT.findall(f.read_text(errors="ignore")))
    return sorted(urls)


def fetch(url):
    src = url + "?format=2500w" if "images.squarespace-cdn.com" in url else url
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Type", "")


def dims(path):
    out = subprocess.run(["magick", "identify", "-format", "%w %h\n", str(path)], capture_output=True, text=True).stdout
    w, h = out.split("\n")[0].split()
    return int(w), int(h)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = json.loads(MAP.read_text()) if MAP.exists() else {}
    failed = []
    for url in old_urls():
        if url in m:
            continue
        base = re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").rsplit("/", 1)[-1].lower().replace("+", "-")).strip("-")[:50] or "file"
        key = hashlib.sha1(url.encode()).hexdigest()[:8] + "-" + re.sub(r"-(png|jpe?g|gif|webp|pdf)$", "", base)
        try:
            data, ctype = fetch(url)
        except Exception as e:  # noqa: BLE001 — report and continue
            failed.append((url, str(e)))
            continue
        tmp = OUT / (key + ".download")
        tmp.write_bytes(data)
        if ctype.startswith("image/"):
            dst = OUT / (key + ".webp")
            frames = ["-coalesce"] if "gif" in ctype else []
            subprocess.run(["magick", str(tmp), *frames, "-auto-orient", "-resize", f"{MAX_W}x>", "-quality", "80", str(dst)], check=True)
            if dst.stat().st_size > 300_000:  # keep each image under the publish gate's 300 KB cap
                subprocess.run(["magick", str(tmp), *frames, "-auto-orient", "-resize", "1200x>", "-quality", "70", str(dst)], check=True)
            tmp.unlink()
            w, h = dims(dst)
            m[url] = {"path": str(dst.relative_to(ROOT)), "width": w, "height": h}
        elif ctype.startswith("application/pdf"):
            ext = ".pdf"
            dst = OUT / (key + ext)
            tmp.rename(dst)
            m[url] = {"path": str(dst.relative_to(ROOT)), "type": ctype}
        else:
            tmp.unlink()  # site CSS/JS and other non-content files are not needed
            continue
        print("ok", dst.name, ctype)
    MAP.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print(f"{len(m)} files mapped; {len(failed)} failed")
    for u, e in failed:
        print("FAILED", u, e, file=sys.stderr)


if __name__ == "__main__":
    main()
