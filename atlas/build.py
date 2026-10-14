#!/usr/bin/env python3
"""build.py — the Open Classical Chinese Character Atlas, as a static site.

    python3 -m atlas.build                 # sibling checkouts if present, else GitHub
    python3 -m atlas.build --remote        # always fetch from GitHub (what CI does)
    python3 -m atlas.build --base /        # serve from the root, e.g. for a local preview

Reads one export per text (texts.json), merges them by character, and writes
site/: the atlas, a page for every character, an index and a page for every
glossary entry. **Nothing here is authored.** Every word of content comes from a
translation repository's export, so editing a glossary entry there and merging
is the whole of updating this site.
"""

import argparse
import hashlib
import html
import json
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from . import md

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"
CONTRACT = 1
FONTS = ("https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;"
         "0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500"
         "&family=Noto+Serif+TC:wght@400;500;600&display=swap")
# One glyph, in the Song face, for the browser tab.
FAVICON = ("data:image/svg+xml," + urllib.parse.quote(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
    "<rect width='64' height='64' rx='8' fill='#16171A'/>"
    "<text x='32' y='47' font-size='42' text-anchor='middle' fill='#F4F4F0' "
    "font-family='Songti SC,Noto Serif TC,serif'>字</text></svg>"))

e = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731


# ---------------------------------------------------------------- fetch

def fetch(cfg, remote):
    """{text id: export} — a sibling checkout's file, or the one on GitHub's main."""
    out = {}
    for t in cfg["texts"]:
        local = (ROOT / t["sibling"] / t["export"]).resolve()
        if not remote and local.exists():
            raw, where = local.read_text(encoding="utf-8"), str(local)
        else:
            url = f"https://raw.githubusercontent.com/{t['repo']}/main/{t['export']}"
            with urllib.request.urlopen(url, timeout=60) as r:
                raw, where = r.read().decode("utf-8"), url
        data = json.loads(raw)
        if data.get("contract") != CONTRACT:
            sys.exit(f"  {t['id']}: export contract {data.get('contract')}, "
                     f"this build reads {CONTRACT} — {where}")
        out[t["id"]] = data
        print(f"  {t['id']:<14} {len(data['chars'])} characters · "
              f"{len(data['entries'])} entries  ← {where}")
    return out


# ---------------------------------------------------------------- merge

SHARED = ("p", "sem", "pho", "hw", "rad", "kind", "fq", "def", "defen")


def plain(s):
    """A rendering with its Markdown emphasis removed, for places that show text."""
    import re
    return re.sub(r"\*+([^*]+)\*+", r"\1", s or "")
PER_TEXT = ("g", "r", "lock", "tier", "n", "chs", "cent", "fw", "entries")


def merge(exports):
    texts, chars, glyphs, built = [], {}, {}, {}
    lines, where, units, entries = {}, {}, {}, {}
    for tid, x in exports.items():
        texts.append({**x["text"], "id": tid})
        for c in x["chars"]:
            m = chars.setdefault(c["c"], {"c": c["c"], "t": {}})
            for k in SHARED:
                if not m.get(k) and c.get(k):
                    m[k] = c[k]
            # A character's pinyin is taken from its first token, which may open
            # a sentence; a dictionary reading is lowercase.
            if m.get("p"):
                m["p"] = m["p"].lower()
            m["t"][tid] = {k: c.get(k) for k in PER_TEXT}
            for k in ("g", "r"):
                m["t"][tid][k] = plain(m["t"][tid][k])
        for g, (pin, gloss) in x["glyphs"].items():
            if g not in glyphs or (gloss and not glyphs[g][1]):
                glyphs[g] = [pin, gloss]
        for comp, members in x["built"].items():
            have = built.setdefault(comp, [])
            for mem in members:
                if mem not in have:
                    have.append(mem)
        lines[tid], where[tid], units[tid] = x["lines"], x["where"], x["chapters"]
        entries[tid] = {en["slug"]: {"term": en["term"], "pinyin": en["pinyin"],
                                     "render": plain(en["render"]), "status": en["status"]}
                        for en in x["entries"]}
    for m in chars.values():
        for k in SHARED:
            m.setdefault(k, [] if k in ("sem", "pho") else None)
    return {"texts": texts, "chars": list(chars.values()), "glyphs": glyphs,
            "built": built, "lines": lines, "where": where, "units": units,
            "entries": entries}


def rare_uncovered(site):
    """Rare characters the site shows that the HanaMin subset does not carry."""
    from .fonts import is_rare, used
    have = set((ASSETS / "fonts" / "rare-han.txt").read_text(encoding="utf-8").strip())
    return sorted(used(site) - have)


# ---------------------------------------------------------------- pages

class Site:
    def __init__(self, cfg, data, exports, base, out):
        self.cfg, self.data, self.exports = cfg, data, exports
        self.base, self.out = base, out
        self.title = cfg["site"]["title"]
        self.domain = cfg["site"].get("domain")
        self.chars = {c["c"]: c for c in data["chars"]}

    def char_url(self, c):
        return f"{self.base}{urllib.parse.quote(c)}/"

    def entry_url(self, tid, slug):
        return f"{self.base}{tid}/glossary/{urllib.parse.quote(slug)}/"

    def write(self, rel, text):
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def page(self, rel, title, desc, main, body_attrs="", current=""):
        canon = (f"https://{self.domain}/{rel.removesuffix('index.html')}"
                 if self.domain else "")
        nav = [f'<a href="{self.base}"{" aria-current=page" if current == "atlas" else ""}>Atlas</a>']
        for t in self.data["texts"]:
            cur = ' aria-current="page"' if current == t["id"] else ""
            nav.append(f'<a href="{self.base}{t["id"]}/glossary/"{cur}>'
                       f'{e(t["title"])} glossary</a>')
        self.write(rel, f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(self.title)}">
{f'<link rel="canonical" href="{e(canon)}"><meta property="og:url" content="{e(canon)}">' if canon else ''}
<meta name="theme-color" content="#E9E9E4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#141518" media="(prefers-color-scheme: dark)">
<meta name="atlas-base" content="{e(self.base)}">
<meta name="atlas-data" content="{e(self.data_url)}">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{self.css_url}">
<script src="{self.js_url}" defer></script>
</head>
<body{body_attrs}>
<div class="wrap">
<div class="bar"><a class="home" href="{self.base}">{e(self.title)}</a>
<nav aria-label="Site">{''.join(nav)}</nav></div>
{main}
{self.footer()}
</div>
</body>
</html>
""")

    def footer(self):
        repos = " · ".join(
            f'<a href="https://github.com/{e(t["repo"])}">{e(t["title"])}</a>'
            for t in self.data["texts"])
        return f"""<footer>
  <p><b>How to read this.</b> A Chinese character is usually built from parts, and
  the parts do two different jobs. A <em style="color:var(--sem);font-style:normal">semantic</em>
  part carries meaning. A <strong style="color:var(--pho);font-weight:400">phonetic</strong>
  part was borrowed for its sound alone and means nothing here, which is why the
  two are coloured differently and never merged.</p>
  <p><b>Where the analysis comes from.</b> <span class="zh">說文解字</span>
  (<i>Shuōwén Jiězì</i>), c. 100 CE, the earliest systematic account of how
  Chinese characters are built. It states each character's parts in its own
  words, so the semantic/phonetic split is the source's, not ours. A modern
  radical is a filing system; this is an analysis.</p>
  <p><b>What is ours, and what is not.</b> The Chinese is public domain by age.
  The English glosses, the translations, and the settled renderings are by Shalom
  Ormsby and are dedicated <b>CC0</b>: no rights reserved. <span class="zh">說文</span>'s
  definitions are never machine-rendered: an English line appears only where a
  glossary entry has researched the character and translated it by hand.</p>
  <p><b>Where it comes from.</b> Every word here is built from the translations'
  own repositories: {repos}. Edit a glossary entry there, and this site follows.
  The atlas itself: <a href="https://github.com/opencosmos-ai/chinese-atlas">opencosmos-ai/chinese-atlas</a>.</p>
</footer>"""

    # -- the atlas --------------------------------------------------------
    def atlas_main(self, char=None):
        texts = self.data["texts"]
        # How each text is named on the masthead comes from texts.json, which
        # knows the project's name; the export only knows the book's.
        names = " and ".join(
            f'the <a href="https://github.com/{e(c["repo"])}">'
            f'{e(c.get("name") or t["title"])}</a>'
            for t in texts for c in self.cfg["texts"] if c["id"] == t["id"])
        tf = ""
        if len(texts) > 1:
            tf = ('<button data-text="all" aria-pressed="true">All texts</button>' +
                  "".join(f'<button data-text="{e(t["id"])}" aria-pressed="false">'
                          f'{e(t["title"])}</button>' for t in texts))
        noscript = ""
        if char:
            c = self.chars[char]
            rows = "".join(
                f'<p><b>{e(t["title"])}:</b> {e(c["t"][t["id"]]["g"] or "not yet glossed")}</p>'
                for t in texts if t["id"] in c["t"])
            noscript = (f'<noscript><div class="card"><div class="card-in"><div class="hero">'
                        f'<div class="big">{e(char)}</div><div class="meta"><div class="pin">'
                        f'{e(c["p"])}</div>{rows}</div></div>'
                        f'{"<div class=swz>" + e(c["def"]) + "</div>" if c.get("def") else ""}'
                        f'</div></div></noscript>')
        return f"""<header class="top">
  <div class="mast">
    <div>
      <h1>{e(self.title)}</h1>
      <p>Every character in the classical Chinese texts OpenCosmos translates,
      taken apart into the pieces it is built from, with what each piece means,
      where the character appears, and how each translation renders it. No
      Chinese required.</p>
      <p class="texts">Now serving {names}.</p>
    </div>
    <div class="counts">
      <div><span id="k-ch">—</span><div class="lab">characters</div></div>
      <div><span id="k-oc">—</span><div class="lab">occurrences</div></div>
      <div><span id="k-pt">—</span><div class="lab">parts</div></div>
    </div>
  </div>
</header>
<div class="controls">
  <input type="search" id="q" placeholder="Search a character, sound, or meaning"
         aria-label="Search characters">
  {tf}
  <button id="f-lock" aria-pressed="false">Settled terms</button>
  <button id="f-real" aria-pressed="true">Hide grammar</button>
  <button id="s-freq" aria-pressed="true">By frequency</button>
  <button id="s-cent" aria-pressed="false">By reach</button>
  <span class="spacer"></span>
  <button id="clear" hidden>Clear filter</button>
</div>
<div class="room">
  <div>
    <div class="lab" id="status" style="padding-bottom:8px"></div>
    <div class="grid" id="grid"></div>
  </div>
  <aside class="card" aria-label="Character"><div class="card-in" id="card"></div>{noscript}</aside>
</div>"""

    # -- entries ----------------------------------------------------------
    def md_ctx(self, tid):
        x = self.exports[tid]
        slugs = {en["slug"] for en in x["entries"]}
        repo = x["text"]["repo"]
        return md.Context(
            char_url=self.char_url,
            entry_url=lambda s: self.entry_url(tid, s) if s in slugs else None,
            repo_url=lambda p: f"https://github.com/{repo}/blob/main/{urllib.parse.quote(p)}",
            known_chars=frozenset(self.chars))

    def entry_page(self, tid, en):
        t = next(t for t in self.data["texts"] if t["id"] == tid)
        body = md.render(en["body"], self.md_ctx(tid))
        # The entry's own title line is the page's one h1.
        if body.startswith("<h2>"):
            body = "<h1>" + body[4:].replace("</h2>", "</h1>", 1)
        chars = "".join(dict.fromkeys(en["chars"] + en["covers"]))
        repo = t["repo"]
        main = f"""<nav class="crumbs" aria-label="Breadcrumb" style="margin-top:22px">
  <a href="{self.base}">Atlas</a> /
  <a href="{self.base}{tid}/glossary/">{e(t["title"])} glossary</a> /
  <span class="zh">{e(en["term"])}</span></nav>
<div class="entry-room" style="margin-top:0">
<article>
  <div class="prose">{body}</div>
  <p class="source">This page is <a href="https://github.com/{e(repo)}/blob/main/{e(en["path"])}"><code>{e(en["path"])}</code></a>
  in <a href="https://github.com/{e(repo)}">{e(repo)}</a>, rendered as written.
  Edit it there, and this page follows.</p>
</article>
<aside class="card" aria-label="The character, taken apart">
  <div class="card-in"><div class="chips" id="chips"></div><div id="card"></div></div>
</aside>
</div>"""
        title = f"{en['term']} {en['pinyin']} — {plain(en['render'])} · {t['title']} glossary"
        desc = (f"How the {t['title']} renders {en['term']} ({en['pinyin']}): "
                f"{plain(en['render'])}. The research, the oldest forms, and what is set aside.")
        self.page(f"{tid}/glossary/{en['slug']}/index.html", title, desc, main,
                  f' data-page="entry" data-chars="{e(chars)}"', tid)

    def glossary_index(self, tid):
        t = next(t for t in self.data["texts"] if t["id"] == tid)
        items = []
        for en in sorted(self.exports[tid]["entries"], key=lambda x: x["slug"]):
            status = ('<span class="tag lock">settled</span>' if en["status"] == "locked"
                      else f'<span class="tag">{e(en["status"])}</span>')
            items.append(f"""<a href="{self.entry_url(tid, en['slug'])}">
  <span class="term">{e(en["term"])}</span>
  <span><span class="py">{e(en["pinyin"])}</span>
  <span class="r" style="display:block">{md.inline(en["render"], md.Context())}</span>
  <span class="tags">{status}</span></span></a>""")
        main = f"""<header class="top"><div class="mast"><div>
  <h1>{e(t["title"])} glossary <span class="zh">{e(t["title_zh"])}</span></h1>
  <p>Each entry is the argument behind one ruling: what the character is, its
  oldest forms, how the text uses it, and why the English reads as it does.
  {len(items)} entries, each rendered from the translation's repository.</p>
</div></div></header>
<div class="gx">{''.join(items)}</div>"""
        self.page(f"{tid}/glossary/index.html", f"{t['title']} glossary · {self.title}",
                  f"Every glossary entry of the OpenCosmos {t['title']} translation.",
                  main, ' data-page="index"', tid)

    def check_rare(self):
        # A warning, not a failure: a glossary edit must never be blocked from
        # publishing by a font. The character still shows, in a system face.
        missing = rare_uncovered(self.out)
        if missing:
            print(f"::warning::{len(missing)} rare character(s) not in the font subset: "
                  f"{''.join(missing)} — run python3 -m atlas.fonts (see its docstring)")

    # -- everything -------------------------------------------------------
    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "assets").mkdir(parents=True)
        blob = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        v = hashlib.sha256(blob.encode()).hexdigest()[:10]
        (self.out / "assets" / "data.json").write_text(blob, encoding="utf-8")
        for name in ("atlas.css", "atlas.js"):
            shutil.copy(ASSETS / name, self.out / "assets" / name)
        shutil.copytree(ASSETS / "fonts", self.out / "assets" / "fonts")
        h = hashlib.sha256((ASSETS / "atlas.css").read_bytes() +
                           (ASSETS / "atlas.js").read_bytes()).hexdigest()[:10]
        self.data_url = f"{self.base}assets/data.json?v={v}"
        self.css_url = f"{self.base}assets/atlas.css?v={h}"
        self.js_url = f"{self.base}assets/atlas.js?v={h}"

        desc = ("Every character in the classical Chinese texts OpenCosmos translates, "
                "taken apart: its parts, its oldest analysis, every line it stands in, "
                "and how each translation renders it.")
        self.page("index.html", self.title, desc, self.atlas_main(),
                  ' data-page="atlas"', "atlas")
        for c, rec in self.chars.items():
            gl = next((r["g"] for r in rec["t"].values() if r.get("g")), "")
            title = f"{c} {rec['p'] or ''} — {gl or 'not yet glossed'} · {self.title}"
            d = (f"{c} ({rec['p'] or ''}): what it is built from, its 說文 analysis, "
                 f"and every line it appears in.")
            self.page(f"{c}/index.html", title, d, self.atlas_main(c),
                      f' data-page="atlas" data-char="{e(c)}"', "atlas")
        n_entries = 0
        for tid, x in self.exports.items():
            self.glossary_index(tid)
            for en in x["entries"]:
                self.entry_page(tid, en)
                n_entries += 1
        self.page("404.html", f"Not found · {self.title}", "Page not found.",
                  f"""<header class="top"><div class="mast"><div><h1>Not here</h1>
  <p>That page does not exist. <a href="{self.base}">Return to the atlas</a>.</p>
  </div></div></header>""", ' data-page="index"')
        (self.out / ".nojekyll").write_text("")
        if self.domain:
            (self.out / "CNAME").write_text(self.domain + "\n")
        self.check_rare()
        print(f"  {len(self.chars)} character pages · {n_entries} entry pages"
              f" · data {len(blob) / 1024:.0f} KB\n  → {self.out}  (base {self.base})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--remote", action="store_true", help="fetch every export from GitHub")
    ap.add_argument("--base", help="URL path the site is served from")
    ap.add_argument("-o", "--out", default=str(ROOT / "site"))
    args = ap.parse_args(argv)
    cfg = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))
    base = args.base or ("/" if cfg["site"].get("domain") else cfg["site"]["project_base"])
    exports = fetch(cfg, args.remote)
    Site(cfg, merge(exports), exports, base, Path(args.out)).build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
