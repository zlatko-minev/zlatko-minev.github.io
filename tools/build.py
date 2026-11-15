#!/usr/bin/env python3
"""Build zlatko-minev.com into _site/ from data/*.json and the Notebook catalog.

Static HTML only (no framework). Same idiom as the Notebook's tools/build_site.py.

    python3 tools/build.py            # build
    python3 tools/build.py --serve    # build and preview on http://localhost:8001
    python3 tools/build.py --publish  # fail if any draft marker, TODO or old-host dependency remains
"""
import base64, datetime, hashlib, html, json, re, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
DATA = ROOT / "data"
STYLE_VERSION = hashlib.sha256((ROOT / "src/style.css").read_bytes()).hexdigest()[:12]
NOTEBOOK_REPO = ROOT.parent / "zlatko_minev_quantum_repository"
SITE_URL = "https://www.zlatko-minev.com/"  # canonical HTTPS hostname configured in GitHub Pages

load = lambda name: json.loads((DATA / name).read_text())
PROFILE, PAPERS, PRESS, EDU, EXTRAS = (load(n) for n in ("profile.json", "papers.json", "press.json", "education.json", "extras.json"))
NB = PROFILE["notebook_url"]
if "--notebook-url" in sys.argv:  # local preview against a locally served Notebook
    NB = sys.argv[sys.argv.index("--notebook-url") + 1]
PUBLISH = "--publish" in sys.argv


def load_catalog():
    """The Notebook's deck list. Locally, read the sibling checkout; on GitHub's build machine (no sibling),
    read the library.json the live Notebook publishes, so the two repos build independently."""
    local = NOTEBOOK_REPO / "catalog.json"
    if local.exists() and "--notebook-library" not in sys.argv:
        return json.loads(local.read_text())["items"]
    src = (sys.argv[sys.argv.index("--notebook-library") + 1] if "--notebook-library" in sys.argv
           else urllib.parse.urljoin(SITE_URL, NB) + "library.json")
    if src.startswith("http"):
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "zlatko-minev.com build"}), timeout=60) as r:
            return json.loads(r.read())["items"]
    return json.loads(Path(src).read_text())["items"]


CATALOG = load_catalog()
RAW_POSTS = [dict(p, source=src) for src in ("blog", "blog-int")
             for p in json.loads((DATA / "raw" / f"squarespace_{src}.json").read_text())]
GALLERY = json.loads((DATA / "raw" / "squarespace_talks-and-interviews-gallery.json").read_text())

PAPER_BY_ARXIV = {p["arxiv"]: p for p in PAPERS if p["arxiv"]}
LINK_LABEL = {"openlabs": "Open Labs at Yale", "scholar": "Google Scholar", "arxiv": "arXiv", "github": "GitHub", "linkedin": "LinkedIn", "x": "X",
              "bluesky": "Bluesky", "threads": "Threads", "orcid": "ORCID", "facebook": "Facebook"}
CAT_LABEL = {"pr_on_zkm": "Press", "Media_Appearances": "Media", "selected-projects": "Projects", "outreach": "Outreach",
             "tech-note": "Technical note", "non-tech": "Essay"}
TOPIC_LABEL = {"qec": "Error correction", "qem": "Error mitigation", "hardware": "Hardware", "em-design": "EM design",
               "measurement": "Measurement", "many-body": "Many-body", "topological": "Topological",
               "ml": "Machine learning", "dynamic-circuits": "Dynamic circuits", "learning": "Learning",
               "collab": "Collaboration experiment"}
THEMES = [
    ("qec", "Error correction meets error mitigation",
     "Error correction suppresses errors but does not remove them; the logical errors that remain bias the answer. An error-corrected circuit already records its syndromes, and we use that record to remove the bias in post-processing, at the cost of extra sampling.",
     ["qec"]),
    ("qem", "Quantum error mitigation",
     "How to get accurate answers from noisy processors: learn a noise model that scales to large devices (sparse Pauli–Lindblad), cancel or extrapolate the noise away, and use a circuit's information dynamics to tell which method suits it.",
     ["qem", "ml"]),
    ("hardware", "Superconducting hardware and electromagnetic design",
     "How to design, simulate and quantize superconducting chips: superinductances, multilayer cQED, the energy-participation ratio and Quantum Metal, and now the coupling of a simulated 100-qubit array to the modes of its package.",
     ["hardware", "em-design"]),
    ("measurement", "Quantum measurement and quantum jumps",
     "A quantum jump was long thought to be instantaneous. Continuously monitoring a superconducting artificial atom, we found that, although when a jump starts is random, a jump in progress follows a continuous, predictable flight that can be caught and reversed.",
     ["measurement"]),
    ("many-body", "Many-body physics on quantum processors",
     "Processors with more than a hundred qubits can serve as laboratories for many-body physics: local integrability, string-net condensation and Fibonacci anyons, and long-range entanglement made with dynamic circuits.",
     ["many-body", "topological", "dynamic-circuits"]),
    ("collab", "Contributions to large collaboration experiments",
     "Experiments by the Google Quantum AI team and collaborators, with hundreds of authors, to which I contributed.",
     ["collab"]),
]
# Research page: a few papers up top, and one figure per theme.
SELECTED = ("1803.00545", "2201.09866", "2510.19550", "2010.00620", "2309.17368", "2610.12400")
THEME_FIG = {"qec": "assets/img/research/vec-chip-isometric.webp", "qem": "assets/img/research/pec-with-without.webp",
             "hardware": "assets/img/research/epr-current-density-panel.webp", "measurement": "assets/img/research/jumps-mario.webp",
             "many-body": "assets/img/research/fibonacci-card.webp", "collab": "assets/img/research/nmr-otoc-card.webp"}
# Journal publication dates (arXiv dates are wrong for citation_publication_date of published papers).
JOURNAL_DATE = {(w.get("doi") or "").replace("https://doi.org/", "").lower(): w.get("publication_date")
                for w in json.loads((DATA / "raw" / "openalex.json").read_text())["results"]}
try:
    from PIL import Image
except ImportError:  # dimensions are optional; the page still renders
    Image = None
_DIMS = {}


def dims(src):
    if src not in _DIMS:
        _DIMS[src] = Image.open(ROOT / src).size if Image and (ROOT / src).exists() else None
    return _DIMS[src]

# Old Squarespace post slug -> paper (arXiv) when the post was about one paper.
POST_TO_PAPER = {
    "robust-and-efficient-quantum-property-learning": "2402.17911", "fibonacci-paper": "2406.12820",
    "dynamic-circuits": "2308.13065", "ml-qem": "2309.17368", "lioms-and-mbl-experiment": "2307.07552",
    "pec-talk": "2201.09866", "epr-manuscript": "2010.00620",
    "energy-participation-approach-to-the-design-of-quantum-josephson-circuits": "2010.00620",
    "catching-and-reversing-a-quantum-jump-mid-flight": "1803.00545", "multilayer-planar-25d-cqed": "1509.01619",
    "superinductances-for-quantum-circuits": "1206.2964",
}
VIDEO_COURSE = {}
for c in EDU["courses"]:
    for ed in c["editions"]:
        for v in ed["videos"]:
            VIDEO_COURSE[v] = c["id"]
VIDEO_PAPER = {v["youtube"]: ax for ax, vs in EXTRAS["paper_videos"].items() for v in vs}

MARK = ('<svg class="mark" viewBox="0 0 64 64" aria-hidden="true"><rect class="mk-t" width="64" height="64" rx="15"/>'
        '<path class="mk-d" d="M30 44h24M10 20h14"/><path class="mk-l" d="M10 44h14M40 20h14"/>'
        '<path class="mk-a" d="M24 44C34 44 30 20 40 20"/></svg>')
NAV = [("About", "/#about"), ("Research", "/research/"), ("Quantum Notebook", None)]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def t(s):
    """Escape text and render any TODO-ZKM marker as a visible tag."""
    s = esc(s)
    return re.sub(r"TODO-ZKM:?([^.;)\]]*)", lambda m: f'<span class="todo">TODO: {m.group(1).strip()}</span>', s)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def authors_html(authors, limit=12):
    """Long lists are cut, but never so that Minev appears earlier in the list than he is."""
    names = [f"<b>{esc(a)}</b>" if "Minev" in a else esc(a) for a in authors]
    n = len(names)
    if n > limit:
        i = next((k for k, a in enumerate(authors) if "Minev" in a), None)
        if i is None or i < 6:
            return ", ".join(names[:6]) + f", and {n - 6} others"
        tail = ", …" if i + 3 < n else ""
        return ", ".join(names[:3]) + ", …, " + ", ".join(names[i:i + 3]) + tail
    return ", ".join(names)


def clip(s, n=155):
    """Meta description cut at a word boundary."""
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:s.rfind(" ", 0, n - 1)].rstrip(",;:") + "…"


def surname(name):
    """Family name, keeping particles such as 'van den' or 'de'."""
    w = name.split()
    i = len(w) - 1
    while i > 0 and w[i - 1].lower() in ("van", "von", "den", "der", "de", "da", "del", "di", "la", "le"):
        i -= 1
    return " ".join(w[i:])


def author_line(p):
    """Short 'with …' line for cards so a reader sees whose work it is."""
    a = p["authors"]
    if len(a) <= 1:
        return ""
    if p["large_collab"]:
        return f"Large collaboration ({len(a)} authors)" if len(a) > 1 else ""
    first = surname(a[0])
    lead = "First author" if "Minev" in a[0] else f"{first} et al."
    return f"{lead} · {len(a)} authors"


def paper_url(p):
    return f"/papers/{p['id']}/"


def nb_item(i):
    return f"{NB}items/{i['id']}/"


def nb_thumb(i):
    return f"{NB}thumbs/{i['id']}.jpg"


def mailto():
    addr = PROFILE["email"].replace(" [at] ", "@")
    return f"mailto:{addr}"


def yt_facade(vid, title):
    return (f'<a class="video-facade" href="https://www.youtube.com/watch?v={esc(vid)}" '
            f'style="background-image:url(https://i.ytimg.com/vi/{esc(vid)}/hqdefault.jpg)" '
            f'rel="noopener"><span>{esc(title)}</span></a>')


def page(path, title, body, desc="", head_extra="", current=None, image=None, canonical=True, og_type="website"):
    desc = clip(desc)
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{h}"{cur if current == h else ""}>{n}</a>' if h else
                  f'<a class="nav-cta" href="{NB}" title="My lectures, talks and notes">{n} <span aria-hidden="true">&#8599;</span></a>' for n, h in NAV)
    links = PROFILE["links"]
    canon = f'<link rel="canonical" href="{SITE_URL}{path.lstrip("/")}">' if canonical else ""
    share_image = image or PROFILE["og_image"]
    share_alt = title if image else PROFILE["og_image_alt"]
    share_dims = dims(share_image)
    share_size = (f'<meta property="og:image:width" content="{share_dims[0]}">\n'
                  f'<meta property="og:image:height" content="{share_dims[1]}">') if share_dims else ""
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{"" if PUBLISH and canonical else '<meta name="robots" content="noindex">'}
{canon}
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{SITE_URL}{path.lstrip('/')}">
<meta property="og:image" content="{SITE_URL}{share_image}">
<meta property="og:image:alt" content="{esc(share_alt)}">
{share_size}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE_URL}{share_image}">
<meta name="twitter:image:alt" content="{esc(share_alt)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="stylesheet" href="/style.css?v={STYLE_VERSION}">
{head_extra}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar"><div class="wrap topbar-inner">
  <a class="me" href="/">{MARK}<span>{esc(PROFILE['name'])}</span></a>
  <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav" aria-label="Menu">☰</button>
  <nav class="nav" id="nav" aria-label="Main">{nav}</nav>
</div></header>
<main id="main">
{body}
</main>
<footer class="site"><div class="wrap cols">
  <div><h2>Site</h2><ul>{''.join(f'<li><a href="{h or NB}">{n}</a></li>' for n, h in NAV)}<li><a href="/writing/">Writing</a></li></ul></div>
  <div><h2>Elsewhere</h2><ul>
    <li><a href="{links['scholar']}">Google Scholar</a></li><li><a href="{links['arxiv']}">arXiv</a></li>
    <li><a href="{links['github']}">GitHub</a></li><li><a href="{links['linkedin']}">LinkedIn</a></li>
    <li><a href="{links['x']}">X</a> · <a href="{links['bluesky']}">Bluesky</a></li></ul></div>
  <div><h2>Contact</h2><ul><li><a href="/#contact">Get in touch</a></li></ul></div>
  <div><h2>Reuse</h2><p style="margin:0">Slides and notes © Zlatko K. Minev, CC BY-NC-ND 4.0 unless marked otherwise. Paper figures belong to their publishers and authors.</p><p class="mono" style="font-size:12px"><a href="/papers.xml">papers feed</a></p></div>
</div></footer>
<script>(()=>{{const o=()=>{{const d=location.hash&&document.querySelector(location.hash);if(d&&d.tagName==="DETAILS")d.open=true}};addEventListener("hashchange",o);o()}})();</script>
<script>console.log("%cHi! You found the console.","font:600 14px serif;color:#a2541f","\\nThis site is plain HTML and CSS, built by a small Python script.\\nIf you like poking at things like this, try Qiskit Metal.");</script>
<script src="/site.js" defer></script>
<script>(()=>{{const b=document.querySelector('.nav-toggle'),n=document.getElementById('nav');const set=o=>{{n.classList.toggle('open',o);b.setAttribute('aria-expanded',o)}};
b.addEventListener('click',()=>set(!n.classList.contains('open')));document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&n.classList.contains('open')){{set(false);b.focus()}}}});
document.addEventListener('click',e=>{{if(n.classList.contains('open')&&!e.target.closest('.nav,.nav-toggle'))set(false)}});n.addEventListener('click',e=>{{if(e.target.closest('a'))set(false)}})}})();
</script>
</body>
</html>
"""
    write(path, doc)


REHOST = json.loads((DATA / "rehost_map.json").read_text()) if (DATA / "rehost_map.json").exists() else {}
SQS = re.compile(r"https?://(?:images|static1)\.squarespace(?:-cdn)?\.com/[^\"'\s\\<>)]+")


def rehost(text):
    """Point every old Squarespace file at its local copy (made by tools/rehost_images.py)."""
    def sub(m):
        hit = REHOST.get(m.group(0).split("?")[0].replace("&amp;", "&"))
        return "/" + hit["path"] if hit else m.group(0)
    return SQS.sub(sub, text)


def write(path, text):
    text = rehost(text)
    # theopenlabs.org lapsed and now serves an unrelated gambling site: keep the words, drop the link.
    text = re.sub(r'<a\b[^>]*href="https?://(?:www\.)?theopenlabs\.org/?"[^>]*>(.*?)</a>', r"\1", text, flags=re.S)
    f = OUT / path.lstrip("/")
    if path.endswith("/"):
        f = f / "index.html"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


def redirect(old, new):
    """GitHub Pages has no server redirects: write a tiny forwarding page."""
    write(old if old.endswith("/") or old.endswith(".html") else old + "/",
          f'<!doctype html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{new if new.startswith("http") else SITE_URL + new.lstrip("/")}">'
          f'<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={esc(new)}">'
          f'<script>(()=>{{const u=new URL({json.dumps(new)},location.href);if(!u.search)u.search=location.search;if(!u.hash)u.hash=location.hash;location.replace(u.href)}})();</script>'
          f'<p>This page moved to <a href="{esc(new)}">{esc(new)}</a>.</p>')


# ---------------------------------------------------------------- components
def img_tag(src, alt="", lazy=True, cls=""):
    if not src:
        return ""
    lazy_attr = ' loading="lazy"' if lazy else ""
    d = dims(src)
    wh = f' width="{d[0]}" height="{d[1]}"' if d else ""
    c = f' class="{cls}"' if cls else ""
    return f'<img src="/{esc(src)}" alt="{esc(alt)}"{wh}{lazy_attr}{c}>'


def maybe_link(text, url):
    return f'<a href="{esc(url)}">{esc(text)}</a>' if url else t(text)


def recog_li(r, detail=False):
    head = f"{r['year'] or ''} · {esc(r['body'])}" if detail else f"{r['year'] or ''}"
    todo = ""
    return (f'<li>{img_tag(r.get("image"))}<div><span class="yr">{head}</span>'
            f'<strong>{maybe_link(r["title"], r.get("url"))}</strong>{todo}</div></li>')


def paper_card(p, fig=True):
    f = EXTRAS["paper_figures"].get(p["arxiv"]) if fig else None
    thumb = f'<div class="thumb">{img_tag(f["src"])}</div>' if f else ""
    chips = "".join(f'<span class="chip">{TOPIC_LABEL.get(x, x)}</span>' for x in p["topics"][:3])
    summ = p.get("summary") or ""
    if len(summ) > 190:
        summ = summ[:summ.rfind(" ", 0, 185)] + "…"
    return (f'<article class="card paper">{thumb}<div class="body"><div class="chips">{chips}</div>'
            f'<h3><a href="{paper_url(p)}">{esc(p["title"])}</a></h3><p>{esc(summ)}</p>'
            f'{"<p class=my-part>" + esc(p["my_part"]) + "</p>" if p.get("my_part") else ""}'
            f'<div class="meta">{ref_line(p)}</div></div></article>')


def cover_tile(p):
    """A journal-cover-like tile: a tall picture, the title over it, venue and year below."""
    f = EXTRAS["paper_figures"].get(p["arxiv"])
    pic = img_tag(f["src"]) if f else ""
    venue = "arXiv preprint" if p["kind"] == "preprint" else p["venue"]
    labels = {"1803.00545": "Catching a quantum jump", "2201.09866": "Canceling quantum noise", "2510.19550": "Quantum echoes and molecular geometry", "2010.00620": "From fields to Hamiltonians", "2309.17368": "Learning to mitigate errors", "2610.12400": "Mitigation after error correction"}
    label = labels.get(p["arxiv"], p["title"])
    return (f'<li><a class="cover" href="{paper_url(p)}" title="{esc(p["title"])}" aria-label="{esc(p["title"])}"><span class="cover-img">{pic}</span>'
            f'<span class="cover-text"><span class="cover-venue">{esc(venue)} · {p["year"]}</span><b>{esc(label)}</b><span class="cover-open">Read paper &rarr;</span></span></a></li>')


def ref_line(p):
    """Plain reference with links: 'Nature (2019) · arXiv · DOI'."""
    venue = "arXiv preprint" if p["kind"] == "preprint" else p["venue"]
    links = []
    if p.get("arxiv"):
        links.append(f'<a href="https://arxiv.org/abs/{p["arxiv"]}">arXiv</a>')
    if p.get("doi"):
        links.append(f'<a href="https://doi.org/{p["doi"]}">journal</a>')
    return f'{esc(venue)} ({p["year"]})' + "".join(" · " + l for l in links)


def bibtex(p):
    first = re.sub(r"[^A-Za-z]", "", (p["authors"][0].split()[-1] if p["authors"] else "anon"))
    word = next((w for w in re.findall(r"[A-Za-z]+", p["title"]) if len(w) > 3), "paper").lower()
    key = f"{first}{p['year']}{word}"
    auth = " and ".join(p["authors"][:30]) + (" and others" if len(p["authors"]) > 30 else "")
    fields = [f"  title = {{{{{p['title']}}}}}", f"  author = {{{auth}}}", f"  year = {{{p['year']}}}"]
    if p["kind"] == "journal":
        kind = "article"
        fields.append(f"  journal = {{{p['venue']}}}")
    elif p["kind"] == "thesis":
        kind = "phdthesis"
        fields.append("  school = {Yale University}")
    else:
        kind = "misc"
        fields.append("  primaryClass = {quant-ph}")
    if p.get("doi"):
        fields.append(f"  doi = {{{p['doi']}}}")
    if p.get("arxiv"):
        fields += [f"  eprint = {{{p['arxiv']}}}", "  archivePrefix = {arXiv}"]
    return f"@{kind}{{{key},\n" + ",\n".join(fields) + "\n}"


def sep(*parts):
    """Join non-empty parts with a middle dot (no stray separators)."""
    xs = [esc(x) for x in parts if x]
    return ("· " + " · ".join(xs)) if xs else ""


POST_TITLE = {p["old_url"].rstrip("/").split("/")[-1]: p["title"] for p in RAW_POSTS}


def related_decks(p):
    if not p.get("arxiv"):
        return []
    return [i for i in CATALOG if any(p["arxiv"] in (l.get("url") or "") for l in i.get("links") or [])]


# ---------------------------------------------------------------- pages
def build_home():
    pr = PROFILE
    now_items = "".join(
        f'<li><h3><a href="{paper_url(PAPER_BY_ARXIV[n["paper"]])}">{esc(n["label"])}</a></h3><p>{esc(n["text"])}</p></li>'
        for n in pr["now"])
    selected = [p for p in PAPERS if p["selected"]]
    body = f"""
<section class="hero wrap hero-waves"><canvas class="wave-canvas" aria-hidden="true"></canvas><div class="hero-grid">
  <div>
    <p class="hello">{esc(pr['greeting'])}</p>
    <h1>{esc(pr['name'])}</h1>
    <p class="role">{esc(pr['hero_line'])}</p>
    <p class="intro">{esc(pr['tagline'])}</p>
    <div class="btn-row"><a class="btn primary" href="#about">About me</a><a class="btn" href="/research/">Research</a><a class="btn" href="{NB}">Lectures &amp; talks</a></div>
    <div class="icon-row">{icon_links()}</div>
  </div>
  <figure class="portrait hero-portrait">{img_tag(pr['portrait'], "Portrait of Zlatko Minev", lazy=False)}</figure>
</div><button class="wave-toggle" type="button" aria-pressed="false" hidden>Pause background</button></section>

{teaching_section()}

<section class="band now stack-band" id="now"><div class="wrap now-grid">
  <figure class="now-figure"><svg id="chip-stack" viewBox="0 0 480 470" role="img" aria-label="Animated isometric drawing of a quantum processor coming apart into layers as you scroll: package and wiring, qubit chip, couplers and readout, surface code, and one logical qubit"></svg>
    <figcaption>A processor, from package to logical qubit. The flashes are stabilizer checks. No logical errors were detected in this animation.</figcaption><button type="button" class="reel-toggle" data-chip-toggle aria-pressed="false" hidden>Pause diagram</button></figure>
  <div><p class="eyebrow">Now</p><h2>What I'm working on these days</h2>
    <ul class="now-list">{now_items}</ul>
    <p style="margin-top:20px"><a class="more" href="/research/">All research themes</a></p></div>
</div></section>

<section class="band wrap" id="stories"><div class="band-head"><div><p class="eyebrow">Highlights</p><h2>A few stories along the way</h2></div></div>
  <div class="stories">{highlights()}</div>
  <p style="margin-top:8px"><a class="more" href="/research/">Selected papers and all research</a></p>
</section>

{software_band()}

{about_section()}


{press_section()}
"""
    page("/", f"{pr['name']} — quantum physicist", body,
         "Zlatko K. Minev: quantum error mitigation and correction, superconducting quantum hardware and its design, and teaching the physics of real quantum computers.",
         head_extra=person_jsonld() + '<script src="/chip.js" defer></script><script src="/hero-waves.js" defer></script>')


UPDATE_NOTE = ('This list is updated occasionally. For everything, see <a href="https://scholar.google.com/citations?user=NaxMJzQAAAAJ">Google Scholar</a> '
               'and <a href="https://arxiv.org/a/minev_z_1.html">arXiv</a>.')


def highlights():
    out = ""
    for h in PROFILE["highlights"]:
        links = " · ".join(f'<a href="{paper_url(PAPER_BY_ARXIV[h["paper"]]) if u == "@paper" else NB if u == "@NB" else paper_url(PAPER_BY_ARXIV[u[1:]]) if u.startswith("@") else esc(u)}">{esc(l)}</a>' for l, u in h["links"])
        pic = img_tag(h["image"], h.get("alt") or h["title"])
        if h.get("image_link"):
            pic = f'<a href="{esc(h["image_link"])}">{pic}</a>'
        aside = f'<p class="aside">{esc(h["aside"])}</p>' if h.get("aside") else ""
        years = f'<span class="level">{esc(h["years"])}</span>' if h.get("years") else ""
        if h.get("bullets"):
            aside = f'<ul class="story-points">{"".join(f"<li>{about_html(b)}</li>" for b in h["bullets"])}</ul>' + aside
        out += (f'<article class="story" id="story-{h["id"]}"><div class="story-img">{pic}</div><div>'
                f'{years}<h3>{esc(h["title"])}</h3><p>{about_html(h["text"])}</p>{aside}<div class="meta">{links}</div></div></article>')
    return out


def teaching_section():
    """The Notebook band: counts, newest covers and one big link; the lectures themselves live in the Notebook."""
    shelves = {}
    for i in CATALOG:
        shelves[i["shelf"]] = shelves.get(i["shelf"], 0) + 1
    slides = sum(i.get("pages") or 0 for i in CATALOG if i["shelf"] != "notes")
    pages = sum(i.get("pages") or 0 for i in CATALOG)
    stats = (f'<ul class="nb-stats"><li><b>{len(CATALOG)}</b> decks and notes</li><li><b>{slides:,}</b> slides</li>'
             f'<li><b>{pages:,}</b> PDF pages in all</li></ul>')
    course_links = " · ".join(f'<a href="{NB}courses/{c["id"]}/">{esc(c["title"])}</a>' for c in EDU["courses"])
    newest = sorted(CATALOG, key=lambda i: (i["year"] or 0), reverse=True)[:6]
    fan = "".join(f'<a href="{nb_item(i)}" title="{esc(i["title"])}"><img src="{nb_thumb(i)}" alt="{esc(i["title"])}" loading="lazy" width="360" height="225"></a>' for i in newest)
    return (f'<section class="band notebook-band" id="teaching"><div class="wrap">'
            f'<div class="nb-grid"><div><p class="eyebrow">Lectures · talks · notes</p><h2>Zlatko\'s Quantum Notebook</h2>'
            f'<p class="nb-lede">A free online library of my lecture slides, research talks and technical notes since 2011: '
            f'{shelves.get("lectures", 0)} lectures and tutorials, {shelves.get("research", 0)} research talks and {shelves.get("notes", 0)} technical notes, '
            f'each with a short summary and a citation.</p>{stats}'
            f'<a class="btn primary big" href="{NB}">Open the Notebook &rarr;</a>'
            f'<h3 class="nb-course-heading">Courses and learning paths</h3>'
            f'<p class="nb-course-entry"><a class="more" href="{NB}courses/">Take a course: slides, videos, notes and labs</a></p>'
            f'<p class="nb-courses"><b>Courses:</b> {course_links}</p></div>'
            f'<div class="nb-fan">{fan}</div></div>'
            f'</div></section>')


def press_section():
    """Recognition, coverage, interviews and a short bio, kept compact on the home page."""
    pr = PRESS
    rec = "".join(f'<li><span class="y">{r["year"] or ""}</span>{maybe_link(r["title"], r.get("url"))}</li>' for r in visible_recognition())
    def cov_li(x):
        when = " · ".join(v for v in (x.get("by"), x.get("date")) if v)
        return f'<li><span class="o">{esc(x["outlet"])}</span> {maybe_link(x["title"], x.get("url"))}{f" <span class=when>{esc(when)}</span>" if when else ""}</li>'
    top = "".join(cov_li(x) for x in pr["coverage_list"] if x.get("featured"))
    more = "".join(cov_li(x) for x in pr["coverage_list"] if not x.get("featured"))
    cov = f'<ul class="cov">{top}</ul>' + (f'<details class="older"><summary>More coverage</summary><ul class="cov">{more}</ul></details>' if more else "")
    media = "".join((yt_facade(m["youtube"], f'{m["title"]} ({m["year"]})' if m.get("year") else m["title"]) if m.get("youtube") else
                     f'<a class="card" href="{esc(m["url"])}" style="text-decoration:none;color:inherit"><div class="body"><span class="chip">{esc(m["kind"])}</span><h3 style="font-size:16px">{esc(m["title"])}</h3></div></a>')
                    for m in sorted((m for m in pr["media"] if not m.get("hidden")), key=lambda m: -(m.get("year") or 0)))
    return f"""<section class="band wrap" id="press"><div class="band-head"><div><p class="eyebrow">Press</p><h2>News, media and coverage</h2>
  <p>A few selected highlights.</p></div></div>
  <details class="fold"><summary>Selected recognition</summary><ul class="recog-list">{rec}</ul></details>
  <details class="fold"><summary>Selected articles and coverage</summary>{cov}</details>
  <details class="fold"><summary>Interviews, radio, podcasts and public talks</summary><div class="video-grid" style="margin-top:12px">{media}</div></details>
</section>"""


def stats_strip():
    """Every number on the site comes from profile.json "numbers" with its source and date."""
    cells = ""
    for n in PROFILE["numbers"]:
        val = f"{len(CATALOG)} decks" if n["value"] == "@catalog" else n["value"]
        asof = t(n["as_of"]) if "TODO" in str(n["as_of"]) else f"as of {esc(n['as_of'])}"
        cells += f'<div><dt>{esc(n["label"])} <span class="asof">{asof}</span></dt><dd>{esc(val)}</dd></div>'
    return f'<dl class="stats">{cells}</dl>'


def visible_recognition():
    return sorted([r for r in PRESS["recognition"] if not r.get("hidden")], key=lambda r: -(r["year"] or 0))


def tool_cards(research=False):
    pr = PROFILE
    cards = ""
    for o in pr["open_source"]:
        if o.get("research_only") and not research:
            continue
        stats = " · ".join(f"{v:,} {k}" for k, v in (o.get("stats") or {}).items())
        stats = f'<div class="meta">{esc(stats)} · as of {esc(pr["open_source_asof"])}</div>' if stats else ""
        featured = " featured" if not research and o == pr["open_source"][0] else ""
        image = img_tag(o["image"], o["name"])
        if o.get("analysis_image"):
            image = ('<span class="tool-art">'
                     + img_tag(o["image"], "Quantum Metal chip layout", cls="tool-chip")
                     + img_tag(o["analysis_image"], "Capacitive, eigenmode, scattering and Hamiltonian analyses", cls="tool-analysis")
                     + '</span>')
        elif o.get("image_crop"):
            x, y, w, h = o["image_crop"]
            iw, ih = dims(o["image"])
            crop_id = f'tool-crop-{slugify(o["name"])}'
            image = (f'<svg class="tool-field" viewBox="{x} {y} {w} {h}" role="img" aria-label="Simulated current density near a Josephson junction">'
                     f'<defs><clipPath id="{crop_id}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath></defs>'
                     f'<image href="/{o["image"]}" width="{iw}" height="{ih}" clip-path="url(#{crop_id})"/></svg>')
        links = (f'<div class="tool-links"><a href="{o["docs_url"]}">Documentation ↗</a><a href="{o["url"]}">GitHub ↗</a></div>'
                 if o.get("docs_url") else "")
        cards += (f'<article class="card tool{featured}"><a class="thumb" href="{o["url"]}">{image}</a><div class="body">'
                  f'<span class="level">{esc(o["role"])}</span><h3><a href="{o["url"]}">{esc(o["name"])}</a></h3><p>{esc(o["text"])}</p>{links}{stats}</div></article>')
    return cards


def software_band():
    pr = PROFILE
    cards = tool_cards()
    devs = "".join(f'<li><img src="/assets/img/metal/{n}.webp" alt="{esc(c)}" loading="lazy" width="240" height="180"><span><b>{esc(c)}</b><br>{esc(who)}</span></li>'
                   for n, c, who in pr["metal_devices"])
    comps = "".join(f'<li class="comp"><img src="/assets/img/metal/{n}.webp" alt="{esc(label)}" loading="lazy" width="180" height="180"><span>{esc(label)}</span></li>'
                    for n, label in METAL_REEL)
    echo = (devs + comps).replace("<li>", '<li aria-hidden="true">').replace('<li class="comp">', '<li class="comp" aria-hidden="true">')  # second copy so the reel loops
    reel = (f'<div class="reel-wrap"><p class="reel-cap"><b>Built with Metal.</b> Chips designed with Quantum Metal by groups in several countries, '
            f'followed by a few of the components in its library, drawn by Metal itself. (Yes, there is a smiley face.)</p>'
            f'<button type="button" class="reel-toggle" data-reel-toggle aria-controls="metal-reel" aria-pressed="false" hidden>Pause showcase</button>'
            f'<ul class="reel" id="metal-reel" aria-label="Devices and components designed with Quantum Metal">{devs}{comps}{echo}</ul></div>')
    return (f'<section class="band wrap" id="tools"><div class="band-head"><div><p class="eyebrow">Open source</p><h2>Tools I started</h2>'
            f'<p>Free to use; issues and pull requests are welcome.</p></div><a class="more" href="/research/#software">More</a></div>'
            f'<div class="grid">{cards}</div>{reel}</section>')


METAL_REEL = [("TransmonPocket", "Transmon pocket"), ("TransmonCross", "Xmon-style cross"), ("StarQubit", "Star qubit"),
              ("TransmonConcentric", "Concentric transmon"), ("TransmonInterdigitated", "Interdigitated transmon"),
              ("TransmonPocket6", "Six-port pocket"), ("TunableCoupler01", "Tunable coupler"), ("SNAIL", "SNAIL"),
              ("SQUID_LOOP", "SQUID loop"), ("CapNInterdigital", "Interdigital capacitor"), ("ResonatorCoilRect", "Coil resonator"),
              ("RouteMeander", "Meander route"), ("RouteMixed", "Mixed route"), ("LaunchpadWirebond", "Launch pad"),
              ("NSquareSpiral", "Square spiral"), ("Airbridge", "Airbridge"), ("SmileyFace", "Smiley face")]


def person_jsonld():
    pr = PROFILE
    d = {"@context": "https://schema.org", "@type": "Person", "name": pr["name"], "url": SITE_URL,
         "affiliation": {"@type": "Organization", "name": pr["affiliation"]}, "image": SITE_URL + pr["portrait"],
         "alumniOf": ["Yale University", "University of California, Berkeley"],
         "sameAs": [v for v in pr["links"].values() if v]}
    return f'<script type="application/ld+json">{json.dumps(d)}</script>'


DRAFT_FLAG = ""  # summaries awaiting sign-off are tracked in data (summary_draft), not shown


def build_papers():
    """Paper pages only; the list of papers lives on the Research page."""
    redirect("/papers/", "/research/")
    for p in PAPERS:
        build_paper(p)


def build_paper(p):
    f = EXTRAS["paper_figures"].get(p["arxiv"])
    decks = related_decks(p)
    vids = EXTRAS["paper_videos"].get(p["arxiv"], [])
    posts = EXTRAS["paper_posts"].get(p["arxiv"], [])
    lead = EXTRAS.get("paper_campaign_lead", {}).get(p["arxiv"])
    old_posts = [s for s, ax in POST_TO_PAPER.items() if ax == p["arxiv"]]
    venue = p["venue"] if p["kind"] != "preprint" else "Preprint"
    links = []
    if p["arxiv"]:
        links += [f'<li><a href="https://arxiv.org/abs/{p["arxiv"]}">arXiv:{p["arxiv"]}</a></li>',
                  f'<li><a href="https://arxiv.org/pdf/{p["arxiv"]}">PDF (arXiv)</a></li>']
    if p.get("doi"):
        links.append(f'<li><a href="https://doi.org/{p["doi"]}">Journal version (DOI)</a></li>')
    links += [f'<li><a href="/writing/{s}/">Blog post: {esc(POST_TITLE.get(s, s))}</a></li>' for s in old_posts]
    links += [f'<li><a href="{esc(c["url"])}">Code: {esc(c["label"])}</a></li>' for c in p.get("code") or []]
    summary = (f'<p class="summary">{esc(p["summary"])}{DRAFT_FLAG if p.get("summary_draft") else ""}</p>'
               if p.get("summary") else '<p class="muted">Plain-language summary <span class="todo">TODO: write</span>. The abstract is below.</p>')
    if p.get("scope"):
        summary += f'<p class="scope"><b>Scope.</b> {esc(p["scope"])}</p>'
    if p.get("my_part"):
        summary += f'<p class="my-part">{esc(p["my_part"])}</p>'
    if p.get("authors_note"):
        summary += f'<p class="callout">{t(p["authors_note"])}</p>'
    fig = (f'<figure class="fig">{img_tag(f["src"], clip(f["caption"], 120))}<figcaption>{esc(f["caption"])}</figcaption></figure>'
           if f else "")
    abstract = f'<details class="abstract"{" open" if not p.get("summary") else ""}><summary>Abstract</summary><p>{esc(p.get("abstract"))}</p></details>' if p.get("abstract") else ""
    talks = ""
    if decks or vids:
        talks = '<section><h2>Related talks</h2>'
        if vids:
            talks += '<div class="video-grid">' + "".join(yt_facade(v["youtube"], v["title"]) for v in vids) + "</div>"
        if decks:
            talks += '<ul class="decks">' + "".join(f'<li><span class="y">{i["year"]}</span><a href="{nb_item(i)}">{esc(i["title"])}</a> <span class="muted">{sep(i.get("venue"), "slides in the Notebook")}</span></li>' for i in decks) + "</ul>"
        talks += "</section>"
    convo = ""
    if posts or lead:
        convo = '<section><h2>The conversation</h2><p class="muted">The explainer posts I wrote about this paper, in order.</p>'
        if lead:
            convo += f'<blockquote class="lead-post">{esc(lead)}<cite>Announcement post, {esc(posts[0]["date"]) if posts else ""}</cite></blockquote>'
        convo += '<ul class="posts">' + "".join(f'<li><span class="mono muted">{esc(x["date"])}</span><a href="{esc(x["url"])}">{esc(x["title"])}</a></li>' for x in posts) + "</ul></section>"
    note = f'<p class="callout">{t(p["note"])}</p>' if p.get("note") else ""
    bid = f"bib-{p['id']}"
    pubdate = JOURNAL_DATE.get((p.get("doi") or "").lower()) if p["kind"] == "journal" else None
    pubdate = pubdate or p["date"] or str(p["year"])
    meta = [f'<meta name="citation_title" content="{esc(p["title"])}">'] + \
           [f'<meta name="citation_author" content="{esc(a)}">' for a in p["authors"]] + \
           [f'<meta name="citation_publication_date" content="{esc(pubdate.replace("-", "/"))}">']
    if p["kind"] == "journal":
        meta.append(f'<meta name="citation_journal_title" content="{esc(p["venue"])}">')
    if p["kind"] == "thesis":
        meta.append('<meta name="citation_dissertation_institution" content="Yale University">')
    if p["arxiv"]:
        meta.append(f'<meta name="citation_pdf_url" content="https://arxiv.org/pdf/{esc(p["arxiv"])}">')
    ld = {"@context": "https://schema.org", "@type": "ScholarlyArticle", "headline": p["title"], "datePublished": pubdate,
          "author": [{"@type": "Person", "name": a} for a in p["authors"][:100]],
          "sameAs": [u for u in (f"https://doi.org/{p['doi']}" if p.get("doi") else None,
                                 f"https://arxiv.org/abs/{p['arxiv']}" if p["arxiv"] else None) if u]}
    if p["kind"] == "journal":
        ld["isPartOf"] = {"@type": "Periodical", "name": p["venue"]}
    meta.append(f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')
    if p.get("doi"):
        meta.append(f'<meta name="citation_doi" content="{esc(p["doi"])}">')
    if p["arxiv"]:
        meta.append(f'<meta name="citation_arxiv_id" content="{esc(p["arxiv"])}">')
    body = f"""
<div class="wrap page-head paper-head"><p class="venue">{esc(venue)} · {p['year']}{' · large collaboration' if p['large_collab'] else ''}</p>
<h1 style="font-size:clamp(30px,4.4vw,48px)">{esc(p['title'])}</h1>
<p class="authors">{authors_html(p['authors'])}</p></div>
<div class="wrap layout-2" style="padding-bottom:48px">
 <article>{note}{summary}{fig}{abstract}
  <div style="display:grid;gap:36px;margin-top:24px">{talks}{convo}</div>
 </article>
 <aside class="side">
  <div><h2>Read</h2><ul>{''.join(links)}</ul></div>
  <div><h2>Share</h2><p class="mono" style="margin:0;font-size:13px">zlatko-minev.com/p/{esc(p['arxiv'] or p['id'])}</p></div>
  <div class="cite-box"><h2>Cite</h2><pre id="{bid}">{esc(bibtex(p))}</pre><button class="btn copy" type="button" data-copy="{bid}">Copy</button></div>
  <div><h2>Topics</h2><div class="chips">{''.join(f'<span class="chip">{TOPIC_LABEL.get(x, x)}</span>' for x in p['topics'])}</div></div>
 </aside>
</div>"""
    page(paper_url(p), f"{p['title']} — Zlatko K. Minev", body, p.get("summary") or p.get("abstract") or p["title"],
         head_extra="\n".join(meta), current="/research/", image=f["src"] if f else None, og_type="article")
    redirect(f"/p/{p['arxiv'] or p['id']}/", paper_url(p))


def cite_li(p):
    v = f'<em>{esc(p["venue"])}</em>' if p["kind"] == "journal" else esc(p["venue"])
    ax = f' · <a href="https://arxiv.org/abs/{p["arxiv"]}">arXiv</a>' if p.get("arxiv") else ""
    return f'<li><a class="t" href="{paper_url(p)}">{esc(p["title"])}</a><div class="v">{v} ({p["year"]}){ax}</div></li>'


def build_research():
    secs, placed = [], set()
    for key, title, blurb, topics in THEMES:
        ps = [p for p in PAPERS if (p["large_collab"] if key == "collab" else set(p["topics"]) & set(topics))
              and p["kind"] != "thesis" and p["id"] not in placed]
        if key != "collab":
            ps = [p for p in ps if not p["large_collab"]]
        ps.sort(key=lambda p: -(p["year"] or 0))
        placed.update(p["id"] for p in ps)
        if ps:
            fig = THEME_FIG.get(key)
            fig = f'<figure class="theme-fig">{img_tag(fig)}</figure>' if fig else ""
            secs.append(f'<section class="band wrap" id="{key}"><div class="hero-grid" style="align-items:start"><div><h2>{esc(title)}</h2><p class="prose">{esc(blurb)}</p>{fig}</div>'
                        f'<ul class="cites">{"".join(cite_li(p) for p in ps)}</ul></div></section>')
    rest = [p for p in PAPERS if p["id"] not in placed and p["kind"] != "thesis"]
    if rest:
        secs.append(f'<section class="band wrap" id="other"><div class="hero-grid" style="align-items:start"><div><h2>Other papers</h2></div>'
                    f'<ul class="cites">{"".join(cite_li(p) for p in sorted(rest, key=lambda p: -(p["year"] or 0)))}</ul></div></section>')
    theses = [p for p in PAPERS if p["kind"] == "thesis"]
    pat_li = lambda x: f'<li><span class="t" style="font-weight:600">{maybe_link(x["title"], x.get("url"))}</span><div class="a">{esc(x["inventors"])}</div><div class="v mono" style="font-size:13px">{esc(x["number"])} · {x["year"]}</div></li>'
    all_pats = "".join(pat_li(x) for x in sorted(EXTRAS["patents"], key=lambda x: -x["year"]))
    pats = "".join(f'<li><span class="t" style="font-weight:600">{maybe_link(x["title"], x.get("url"))}</span><div class="a">{esc(x["inventors"])}</div><div class="v mono" style="font-size:13px">{esc(x["number"])} · {x["year"]}</div></li>' for x in sorted((x for x in EXTRAS["patents"] if x.get("selected")), key=lambda x: -x["year"]))
    body = f"""
<div class="wrap page-head"><p class="eyebrow">Research</p><h1>Research and papers</h1>
<p class="lede">I work where quantum hardware meets the noise that limits it: I design and model superconducting circuits, learn and mitigate their errors, and now combine error mitigation with error correction.</p>
<p class="muted" style="font-size:14px">{UPDATE_NOTE}</p>
<nav class="filters" aria-label="Themes"><a class="btn" href="#selected">Favorites</a>{''.join(f'<a class="btn" href="#{k}">{esc(ti)}</a>' for k, ti, _, _ in THEMES)}<a class="btn" href="#software">Software</a><a class="btn" href="#patents">Patents</a></nav></div>
<section class="band wrap" id="selected"><div class="favorites-head"><h2>Some personal favorites</h2><div class="ribbon-controls" hidden><button type="button" data-ribbon-step="-1" aria-label="Previous favorite papers" aria-controls="favorite-papers">&larr;</button><button type="button" data-ribbon-step="1" aria-label="Next favorite papers" aria-controls="favorite-papers">&rarr;</button></div></div><ul class="covers" id="favorite-papers" tabindex="0" aria-label="Favorite papers, scroll left or right">{''.join(cover_tile(PAPER_BY_ARXIV[a]) for a in SELECTED)}</ul></section>
{''.join(secs)}
<section class="band wrap" id="thesis"><div class="hero-grid" style="align-items:start"><div><h2>Ph.D. thesis</h2></div><ul class="cites">{''.join(cite_li(x) for x in theses)}</ul></div></section>
<section class="band wrap" id="software"><div class="band-head"><h2>Open-source software</h2><a class="more" href="https://github.com/zlatko-minev">All my code on GitHub</a></div><div class="grid tools-grid" style="margin-top:16px">{tool_cards(research=True)}</div></section>
<section class="band wrap" id="patents"><h2>Selected patents</h2><ul class="cites">{pats}</ul>
<details class="fold"><summary>All {len(EXTRAS["patents"])} patents and applications</summary><ul class="cites">{all_pats}</ul></details></section>"""
    page("/research/", "Research — Zlatko K. Minev", body, "Research and papers of Zlatko K. Minev: quantum error mitigation and correction, superconducting hardware design, quantum measurement.", current="/research/")


def course_extras(c):
    """Videos and code, folded so the page stays short."""
    vids = [(x, (e.get("video_titles") or {}).get(x) or f"{c['title']}, part {k + 1}") for e in c["editions"] for k, x in enumerate(e["videos"])]
    out = ""
    if vids:
        out += f'<details class="older"><summary>{len(vids)} video{"s" if len(vids) > 1 else ""}</summary><div class="video-grid">{"".join(yt_facade(v, ti) for v, ti in vids)}</div></details>'
    code = "".join(f'<a class="btn" href="{esc(x["url"])}">{esc(x["label"])}</a>' for x in c.get("code") or [])
    if code:
        out += f'<div class="btn-row" style="margin-top:8px">{code}</div>'
    return out


def about_html(s):
    """About lines are trusted HTML from profile.json; href="@<arxiv>" points at that paper's page."""
    return re.sub(r'href="@([\d.]+)"', lambda m: f'href="{paper_url(PAPER_BY_ARXIV[m.group(1)])}"', s)


ICON_GROUPS = (("linkedin", "scholar"), ("arxiv", "github", "orcid", "x", "bluesky"))  # primary profiles, then publications/code/social


def icon_links():
    """Brand icons (Simple Icons, CC0) inlined so they take the text color."""
    out = ""
    for n, k in enumerate(k for g in ICON_GROUPS for k in g):
        if n == len(ICON_GROUPS[0]):
            out += '<span class="icon-sep" aria-hidden="true"></span>'
        svg = (ROOT / "src" / "icons" / f"{k}.svg").read_text()
        svg = re.sub(r"<title>.*?</title>", "", svg).replace('role="img"', 'aria-hidden="true" focusable="false" fill="currentColor"')
        label = LINK_LABEL.get(k, k.title())
        out += f'<a href="{PROFILE["links"][k]}" aria-label="{label}" title="{label}">{svg}</a>'
    mail = ('<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>')
    return out + f'<a href="/#contact" aria-label="Get in touch" title="Get in touch">{mail}</a>'


def about_section():
    pr = PROFILE
    ed = "".join(f'<li><b>{esc(e["degree"])}</b>, {esc(e["school"])}{" (%s)" % e["year"] if e.get("year") else ""} — {esc(e["detail"])}</li>' for e in pr["education"])
    roles = "".join(f'<li><b>{esc(r["org"])}</b> {t(r["years"])} — {esc(r["text"])}</li>' for r in pr["past_roles"])
    svc = "".join(f"<li>{about_html(s)}</li>" for s in pr["service"])
    return f"""<section class="band wrap" id="about"><div class="band-head"><div><p class="eyebrow">About</p><h2>A little about me</h2></div></div>
  <div class="prose about-copy">
    <p class="intro-about">{about_html(pr['intro'])}</p>
    <p class="about-motto">{esc(pr['motto'])}</p>
    <p>{about_html(pr['intro_people'])}</p>
    <figure class="wgmr">{img_tag(pr['open_labs_photo']['src'], pr['open_labs_photo']['alt'])}<figcaption>{esc(pr['open_labs_photo']['caption'])}</figcaption></figure>
  </div>
  <div class="contact-quiet" id="contact"><button type="button" class="contact-reveal" data-contact="{base64.b64encode(pr['email'].encode()).decode()}" aria-expanded="false" aria-controls="contact-address">Get in touch</button><span id="contact-address" aria-live="polite"></span><noscript><p>Email: {esc(pr['email'].replace('@', ' [at] ').replace('.', ' [dot] '))}</p></noscript></div>
  <details class="fold"><summary>The formal version: education, positions and service</summary>
    <h3>Education</h3><ul>{ed}</ul>
    <h3>Positions</h3><ul><li><b>{esc(pr['affiliation'])}</b> {pr['role_since']}–present — {esc(pr['role'])}</li>{roles}</ul>
    <h3>Service and outreach</h3><ul>{svc}</ul></details>
</section>"""


def clean_html(h):
    """Strip Squarespace residue from archived posts and keep one h1 per page."""
    h = re.sub(r"<script.*?</script>", "", h or "", flags=re.S | re.I)
    h = re.sub(r'<img([^>]*?)data-src="([^"]+)"', r'<img\1src="\2"', h)
    h = re.sub(r'\s(?:data-[\w-]+|style|id)="[^"]*"', "", h)
    h = re.sub(r'\sclass="[^"]*"', "", h)
    for n in (5, 4, 3, 2, 1):
        h = re.sub(rf"<(/?)h{n}\b", rf"<\1h{n + 1}", h)
    h = re.sub(r"<img(?![^>]*\balt=)", '<img alt=""', h)
    h = re.sub(r"<div>\s*</div>", "", h)
    h = re.sub(r'href="/?blog/([\w-]+)/?"', r'href="/writing/\1/"', h)
    h = re.sub(r'href="/talks-and-interviews-gallery\?tag=[^"]*"', 'href="/#press"', h)  # old gallery tag filters
    return h


def build_writing():
    rows, exported = [], {}
    moved = {k: v for k, v in EXTRAS.get("posts_to_notebook", {}).items() if not k.startswith("_")}
    for p in sorted(RAW_POSTS, key=lambda p: p["date"], reverse=True):
        slug = p["old_url"].rstrip("/").split("/")[-1]
        cat = " · ".join(dict.fromkeys(CAT_LABEL.get(c, c.replace("-", " ").capitalize()) for c in p["categories"])) or "Post"
        ax = POST_TO_PAPER.get(slug)
        callout = (f'<p class="callout">Archived from the previous site ({esc(p["date"])}). The paper now has its own page: '
                   f'<a href="{paper_url(PAPER_BY_ARXIV[ax])}">{esc(PAPER_BY_ARXIV[ax]["title"])}</a>.</p>') if ax in PAPER_BY_ARXIV else \
                  f'<p class="callout">Archived from the previous site ({esc(p["date"])}).</p>'
        if slug in moved:  # this post now lives on its deck's Notebook page
            deck = f"{NB}items/{moved[slug][0]}/"
            exported[slug] = {"title": p["title"], "date": p["date"], "html": rehost(clean_html(p["body_html"])), "decks": moved[slug]}
            redirect(f"/writing/{slug}/", deck)
            redirect(p["old_url"], deck)
            rows.append(f'<li><span class="when">{esc(p["date"][:7])}</span><div><div class="kind">{esc(cat)} · in the Notebook</div><a href="{deck}">{esc(p["title"])}</a></div></li>')
            continue
        body = (f'<div class="wrap page-head"><p class="eyebrow"><a href="/writing/">Writing</a> · {esc(cat)}</p><h1 style="font-size:clamp(30px,4.4vw,48px)">{esc(p["title"])}</h1>'
                f'<p class="mono muted">{esc(p["date"])}</p></div><div class="wrap" style="padding-bottom:40px">{callout}<div class="post-body">{clean_html(p["body_html"])}</div></div>')
        page(f"/writing/{slug}/", f"{p['title']} — Zlatko K. Minev", body, p.get("excerpt") or p.get("body_text") or p["title"], og_type="article")
        rows.append(f'<li><span class="when">{esc(p["date"][:7])}</span><div><div class="kind">{esc(cat)}</div><a href="/writing/{slug}/">{esc(p["title"])}</a></div></li>')
        redirect(p["old_url"], paper_url(PAPER_BY_ARXIV[ax]) if ax in PAPER_BY_ARXIV else f"/writing/{slug}/")
    body = (f'<div class="wrap page-head"><p class="eyebrow">Writing</p><h1>Writing</h1><p class="lede">Essays, announcements and older posts from the previous site. '
            f'New technical notes live in the <a href="{NB}">Notebook</a>; papers have their own pages.</p></div>'
            f'<section class="wrap" style="padding-bottom:40px"><ul class="feed">{"".join(rows)}</ul></section>')
    page("/writing/", "Writing — Zlatko K. Minev", body, "Essays and archived posts.")
    if "--export-posts" in sys.argv:  # hand the moved posts to the Notebook repo
        (NOTEBOOK_REPO / "blog_posts.json").write_text(json.dumps(exported, indent=1, ensure_ascii=False) + "\n")
        print(f"Exported {len(exported)} posts to {NOTEBOOK_REPO.name}/blog_posts.json")


def build_redirects():
    for g in GALLERY:
        v = g.get("youtube")
        if v in VIDEO_COURSE:
            new = NB  # the courses now live in the Notebook
        elif v in VIDEO_PAPER:
            new = paper_url(PAPER_BY_ARXIV[VIDEO_PAPER[v]])
        else:
            new = "/#press"
        redirect(g["old_url"], new)
    for old, new in {"/blog": "/writing/", "/blog-int": "/writing/", "/talks-and-interviews": "/#press",
                     "/talks-and-interviews-gallery": "/#press", "/other": "/research/", "/hiring": "/#about",
                     "/home": "/", "/blog/category/tutorial": NB, "/blog/category/tech-note": NB,
                     "/blog/blog/twirling": f"{NB}courses/pauli-twirling/",
                     "/blog/catching-and-reversing-a-quantum-jump-mid-flight": paper_url(PAPER_BY_ARXIV["1803.00545"])}.items():
        redirect(old, new)


def build_misc():
    urls = sorted(str(p.relative_to(OUT).parent) for p in OUT.rglob("index.html")
                  if 'http-equiv="refresh"' not in p.read_text()[:600])
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                                     "".join(f"  <url><loc>{SITE_URL}{'' if u == '.' else u + '/'}</loc></url>\n" for u in urls) + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")
    feed_items = "".join(
        f"<entry><title>{esc(p['title'])}</title><link href=\"{SITE_URL}{paper_url(p).lstrip('/')}\"/><id>{SITE_URL}{paper_url(p).lstrip('/')}</id>"
        f"<updated>{p['date'] or p['year']}T00:00:00Z</updated><summary>{esc(p.get('summary') or p.get('abstract') or '')}</summary></entry>"
        for p in PAPERS[:20])
    (OUT / "papers.xml").write_text(f'<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Zlatko K. Minev — papers</title>'
                                    f'<link href="{SITE_URL}papers/"/><id>{SITE_URL}papers.xml</id><updated>{datetime.date.today()}T00:00:00Z</updated>{feed_items}</feed>')
    page("/404.html", "Not found — Zlatko K. Minev",
         '<div class="wrap page-head"><p class="eyebrow">404</p><h1>This page has decohered.</h1><p class="lede">It was here a moment ago, or it moved when the site was rebuilt. Measure again from one of these:</p>'
         '<div class="btn-row"><a class="btn primary" href="/">Home</a><a class="btn" href="/research/">Research</a><a class="btn" href="/writing/">Archived posts</a></div></div>'
         # The Notebook repo was renamed (D13): send old /zlatko-minev-quantum-repository/... links to /notebook/...
         '<script>(()=>{const o="/zlatko-minev-quantum-repository",p=location.pathname;'
         'if(p===o||p.startsWith(o+"/"))location.replace("/notebook"+p.slice(o.length)+location.search+location.hash)})();</script>',
         "Page not found.", canonical=False)


def publish_gate():
    """Before going live: no TODO/draft markers, no old-host images, no oversized images, no missing alts."""
    problems = []
    drafts = sum(1 for p in PAPERS if p.get("summary_draft"))
    if drafts:
        problems.append(f"data/papers.json: {drafts} summaries not yet signed off (summary_draft)")
    for f in OUT.rglob("*.html"):
        h = f.read_text()
        rel = f.relative_to(OUT)
        for pat, what in (('class="todo"', "TODO tag"), ('class="draft-flag"', "draft flag"), ('class="draft-banner"', "draft banner"),
                          ("squarespace", "file on the old Squarespace host"), ('name="robots" content="noindex"', "noindex")):
            if pat in h and not (what == "noindex" and ('http-equiv="refresh"' in h or f.name == "404.html")):
                problems.append(f"{rel}: {what}")
        if re.search(r"<img(?![^>]*\balt=)", h):
            problems.append(f"{rel}: image without alt")
    for f in (OUT / "assets").rglob("*"):
        if f.suffix in (".webp", ".jpg", ".png") and f.stat().st_size > 300_000:
            problems.append(f"{f.relative_to(OUT)}: image over 300 KB")
    # Size hygiene for GitHub Pages (1 GB site limit, 100 MB file limit): stay far below both.
    total = 0
    for f in OUT.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
            if f.stat().st_size > 25_000_000:
                problems.append(f"{f.relative_to(OUT)}: file over 25 MB")
    if total > 300_000_000:
        problems.append(f"_site: total {total / 1e6:.0f} MB, over the 300 MB budget")
    print(f"Site size: {total / 1e6:.1f} MB")
    for n in PROFILE["numbers"]:
        if "TODO" in str(n["as_of"]):
            problems.append(f"data/profile.json: number without a source date")
    kinds = {}
    for p_ in problems:
        kinds[p_.split(": ", 1)[1]] = kinds.get(p_.split(": ", 1)[1], 0) + 1
    print("Publish gate:", "clean" if not problems else f"{len(problems)} problems")
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d} × {k}")
    return 1 if problems else 0


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    for f in (ROOT / "src").iterdir():
        (shutil.copytree if f.is_dir() else shutil.copy)(f, OUT / f.name)
    shutil.copytree(ROOT / "assets", OUT / "assets")
    shutil.copytree(ROOT / "assets" / "s", OUT / "s")  # old Squarespace /s/<file>.pdf links keep working
    build_home(); build_papers(); build_research(); build_writing(); build_redirects(); build_misc()
    redirect("/about/", "/#about")
    # Teaching and press now live on the home page; the Notebook is its own site at /notebook/.
    redirect("/education/", "/#teaching")
    redirect("/press/", "/#press")
    for c in EDU["courses"]:
        redirect(f"/education/{c['id']}/", f"{NB}courses/{c['id']}/")
    n = sum(1 for _ in OUT.rglob("index.html"))
    print(f"Built {OUT.relative_to(ROOT)}/ — {n} pages, {len(PAPERS)} papers")
    if "--publish" in sys.argv:
        sys.exit(publish_gate())
    if "--serve" in sys.argv:
        import http.server, functools
        port = 8001
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print(f"Serving http://localhost:{port}/")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), h).serve_forever()


if __name__ == "__main__":
    main()
