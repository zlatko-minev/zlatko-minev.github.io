"""Warn when the design shared with the Notebook drifts: color tokens, the logo mark, and the top-bar links.

The two sites live in two repos (D9) but should look like one. Run from this repo with the Notebook checked out
next to it:  python3 tools/check_shared.py   (exit code 1 on any difference).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT.parent / "zlatko_minev_quantum_repository"
TOKENS = ("--surface", "--ink", "--muted", "--line", "--accent", "--accent-ink", "--accent-soft", "--chip", "--metal", "--bar",
          "--f-display", "--f-body", "--f-mono")


def tokens(css):
    root = re.search(r":root\s*\{(.*?)\}", css, re.S).group(1)
    return {k: v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root) if k in TOKENS}


def mark(src):
    m = re.search(r'<svg class="mark".*?</svg>', src.replace("'", '"').replace('" "', ""), re.S)
    return re.sub(r"\s+", " ", m.group(0)) if m else None


def main():
    if not NB.exists():
        print(f"Notebook checkout not found at {NB}; nothing to compare.")
        return 0
    problems = []
    a, b = tokens((ROOT / "src" / "style.css").read_text()), tokens((NB / "site" / "style.css").read_text())
    for k in TOKENS:
        if a.get(k) != b.get(k):
            problems.append(f"token {k}: site {a.get(k)!r} vs notebook {b.get(k)!r}")
    if mark((ROOT / "tools" / "build.py").read_text()) != mark((NB / "tools" / "site_pages.py").read_text()):
        problems.append("logo mark SVG differs between tools/build.py MARK and the Notebook's site_pages._MARK")
    nav = re.findall(r'\("([^"]+)", (?:"[^"]*"|None)\)', re.search(r"NAV = \[(.*?)\]", (ROOT / "tools" / "build.py").read_text()).group(1))
    nb_nav = re.findall(r">([A-Z][\w ]+)</a>", re.search(r'<nav class="nav".*?</nav>', (NB / "tools" / "site_pages.py").read_text(), re.S).group(0))
    if nav != nb_nav:
        problems.append(f"top-bar links: site {nav} vs notebook {nb_nav}")
    for p in problems:
        print("DRIFT", p)
    print("Shared design: in sync" if not problems else f"Shared design: {len(problems)} difference(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
