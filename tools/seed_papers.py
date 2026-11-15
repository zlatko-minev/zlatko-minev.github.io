#!/usr/bin/env python3
"""Seed data/papers.json from raw arXiv + OpenAlex pulls (data/raw/).

Run once to create the file; afterwards data/papers.json is hand-curated and this
script only *adds* papers it has not seen (matched by arXiv id or DOI). Every seeded
entry carries "verified": false until the owner checks it.
"""
import json, re, difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "papers.json"

# Abstract-only, errata, duplicates and mirrors are not papers.
SKIP_VENUES = ("Bulletin of the American Physical Society", "APS", "viXra")


def norm(t):
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower().replace("–", " ").replace("-", " "))


def slug(title, year):
    words = [w for w in norm(title).split() if w not in {"a", "an", "the", "of", "on", "in", "for", "with", "and", "to", "via", "using"}]
    return f"{year}-" + "-".join(words[:6])


def main():
    ax = json.loads((RAW / "arxiv_merged.json").read_text())
    for v in ax.values():  # the arXiv author-page feed packs all names into one string
        if len(v["authors"]) == 1 and "," in v["authors"][0]:
            v["authors"] = [n.strip() for n in re.split(r",| and ", v["authors"][0]) if n.strip()]
    oa = json.loads((RAW / "openalex.json").read_text())["results"]
    existing = json.loads(OUT.read_text()) if OUT.exists() else []
    seen = {p.get("arxiv") for p in existing} | {p.get("doi") for p in existing}
    papers = list(existing)

    used_ax = set()
    for w in oa:
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        if w["type"] in ("erratum",) or any(src.startswith(s) for s in SKIP_VENUES) or not w.get("doi"):
            continue
        if w["type"] == "preprint" and "arxiv" not in (w["doi"] or ""):
            continue
        if (w.get("title") or "").startswith("Data for"):
            continue
        doi = w["doi"].replace("https://doi.org/", "")
        arxiv = doi.split("arxiv.")[-1] if "arxiv." in doi else None
        if not arxiv:  # match a journal article to its arXiv preprint
            best, score = None, 0
            for k, v in ax.items():
                if "thesis" in v["journal"].lower():
                    continue
                if v["doi"] and v["doi"].lower() == doi.lower():
                    best, score = k, 1.0
                    break
                s = difflib.SequenceMatcher(None, norm(v["title"]), norm(w["title"])).ratio()
                if s > score:
                    best, score = k, s
            arxiv = best if score > 0.8 else None
        if arxiv:
            used_ax.add(arxiv)
        is_journal = "arxiv" not in doi
        if (is_journal and doi in seen) or (arxiv and arxiv in seen and not is_journal):
            continue
        a = ax.get(arxiv, {})
        authors = a.get("authors") or [x["author"]["display_name"] for x in w["authorships"]]
        papers.append({
            "id": slug(a.get("title") or w["title"], w["publication_year"]),
            "title": a.get("title") or w["title"],
            "authors": authors,
            "year": w["publication_year"],
            "date": a.get("date") or w.get("publication_date"),
            "venue": src if is_journal else "arXiv preprint",
            "doi": doi if is_journal else None,
            "arxiv": arxiv,
            "kind": "journal" if is_journal else "preprint",
            "large_collab": len(authors) >= 50,
            "selected": False,
            "topics": [],
            "summary": None,
            "key_result": None,
            "figure": None,
            "links": [],
            "notebook": [],
            "videos": [],
            "campaign": None,
            "verified": False,
        })
        seen |= {doi, arxiv}

    for k, v in ax.items():  # arXiv-only items OpenAlex missed
        if k in used_ax or k in seen:
            continue
        year = int(v["date"][:4])
        papers.append({
            "id": slug(v["title"], year), "title": v["title"], "authors": v["authors"], "year": year,
            "date": v["date"], "venue": v["journal"] or "arXiv preprint", "doi": v["doi"] or None,
            "arxiv": k, "kind": "thesis" if "thesis" in v["journal"].lower() else ("journal" if v["journal"] else "preprint"),
            "large_collab": len(v["authors"]) >= 50, "selected": False, "topics": [], "summary": None,
            "key_result": None, "figure": None, "links": [], "notebook": [], "videos": [], "campaign": None,
            "verified": False,
        })

    papers.sort(key=lambda p: (p["date"] or str(p["year"])), reverse=True)
    OUT.write_text(json.dumps(papers, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(papers)} papers -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
