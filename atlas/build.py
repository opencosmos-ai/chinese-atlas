#!/usr/bin/env python3
"""build.py — the Open Classical Chinese Character Atlas & Glossary, as a static site.

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
# The light/dark switch's two icons (Lucide's sun and moon, as @opencosmos/ui uses).
THEME_ICONS = ('<svg class="i-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>'
               '<svg class="i-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>')

# @opencosmos/ui's GitHubIcon, verbatim: the mark the family uses everywhere.
GITHUB_MARK = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" '
               'viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 '
               '6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23'
               '-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07'
               '-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 '
               '0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 '
               '1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 '
               '1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8"/></svg>')
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


def merge(exports, cfg=None):
    readers = {t["id"]: t["reader"] for t in (cfg or {}).get("texts", []) if t.get("reader")}
    texts, chars, glyphs, built = [], {}, {}, {}
    lines, where, units, entries = {}, {}, {}, {}
    for tid, x in exports.items():
        texts.append({**x["text"], "id": tid,
                      **({"reader": readers[tid]} if tid in readers else {})})
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
        # Each line also carries the English line that renders it, so a citation
        # can open the translation's reader there. The reader numbers its English
        # lines, the atlas cites Chinese ones, and the export's alignment joins
        # them; 0 where a line has no pairing.
        align = x.get("align") or {}
        lines[tid] = {k: v + [align[k][0][0] if align.get(k) else 0]
                      for k, v in x["lines"].items()}
        where[tid], units[tid] = x["where"], x["chapters"]
        # A character's English names its ruling's chapter-scoped flexions after
        # the primary, so a card shows every English the verse prints for it:
        # 勤 reads "strain · labor".
        for en in x["entries"]:
            extra = []
            for f in en.get("flexions") or []:
                if f["english"] not in extra:
                    extra.append(f["english"])
            for ch in en["term"].replace(" ", "").split("&"):
                r = chars.get(ch, {}).get("t", {}).get(tid)
                if extra and r and r["g"] and r["g"] == r["r"]:
                    r["g"] = r["r"] = " · ".join([r["g"]] + [plain(e) for e in extra])
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
        self.family = cfg["site"]["family"]
        self.repo_url = f'https://github.com/{cfg["site"]["repo"]}'
        self.chars = {c["c"]: c for c in data["chars"]}

    def char_url(self, c):
        return f"{self.base}{urllib.parse.quote(c)}/"

    def entry_url(self, tid, slug):
        return f"{self.base}glossary/{tid}/{urllib.parse.quote(slug)}/"

    def write(self, rel, text):
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    # "Suggest an edit": the prompt a reader pastes into an AI assistant. One
    # template for every page that offers it, and the same words as the
    # "With an AI assistant" section of the text's CONTRIBUTING.md. A text
    # offers it when texts.json names its skill (site.serving[].suggest).
    def suggest_data(self):
        texts = {}
        for sv in self.cfg["site"].get("serving", []):
            if not sv.get("suggest") or sv["id"] not in self.exports:
                continue
            repo = sv["repo"]
            # One line per sentence, unwrapped: the card is narrow, and an
            # assistant reads it the same either way.
            texts[sv["id"]] = {"repo": repo, "name": sv["name"], "prompt": "\n".join([
                "I'd like to suggest an edit to a Chinese character on the OpenCosmos "
                "Character Atlas.",
                "",
                "Character: %SUBJECT%",
                "My suggestion: [what's wrong or missing, and what you'd put instead, "
                "in your own words]",
                "",
                "Please help me contribute it to the translation it comes from:",
                f"1. Fork and clone https://github.com/{repo} "
                f"(gh repo fork {repo} --clone).",
                f"2. Read CONTRIBUTING.md and {sv['suggest']}, and follow "
                "the skill step by step.",
                "3. Check my suggestion against every line the character stands in, "
                "and tell me what you find before you change anything.",
                "4. Show me the exact change and the pull request or issue text, "
                "and ask me before you push, open, or post anything."])}
            # The general prompt carries no context at all, so it works pasted
            # anywhere — the footer here, a landing page, a Substack post. The
            # same words as CONTRIBUTING.md's "From anywhere".
            if sv.get("contribute"):
                texts[sv["id"]]["general"] = "\n".join([
                    f"I'd like to suggest an edit to the {sv['name']}, the OpenCosmos "
                    f"translation of the {sv['tab']}.",
                    "",
                    "My suggestion: [what struck you — a line that reads wrong, a word "
                    "you'd change, a typo, anything — in your own words. Mention the "
                    "chapter if you know it.]",
                    "",
                    "Please help me contribute it:",
                    f"1. Clone https://github.com/{repo}. If it becomes a pull "
                    "request, fork it then.",
                    f"2. Read CONTRIBUTING.md and {sv['contribute']}, and follow "
                    "the skill step by step.",
                    "3. Find where my suggestion belongs, check it against the book, "
                    "and tell me what you find before you change anything.",
                    "4. Show me the exact change and the pull request or issue text, "
                    "and ask me before you push, open, or post anything."])
        site = f"https://{self.domain}/" if self.domain else ""
        blob = json.dumps({"site": site, "texts": texts, "mark": GITHUB_MARK},
                          ensure_ascii=False)
        return blob.replace("</", "<\\/")

    def page(self, rel, title, desc, main, body_attrs="", current="", head=""):
        canon = (f"https://{self.domain}/{rel.removesuffix('index.html')}"
                 if self.domain else "")
        nav = [f'<a href="{self.base}"{" aria-current=page" if current == "atlas" else ""}>Atlas</a>',
               f'<a href="{self.base}glossary/"{" aria-current=page" if current == "glossary" else ""}>Glossary</a>']
        # The site's name heads every page. It is the page's one h1 unless the
        # page brings its own (an entry's term, the 404), then it keeps the look
        # and steps out of the outline.
        tag = "p" if "<h1" in main else "h1"
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
<meta name="theme-color" content="#0B0C0E" media="(prefers-color-scheme: dark)">
<meta name="atlas-base" content="{e(self.base)}">
<meta name="atlas-data" content="{e(self.data_url)}">
<meta name="atlas-glossary" content="{e(self.glossary_url)}">
<link rel="icon" href="{FAVICON}">
{head}<script>/* The reader's light/dark choice, applied before the page paints. */
try {{ var t = localStorage.getItem("atlas-theme");
  if (t === "dark" || t === "light") document.documentElement.dataset.theme = t; }} catch (e) {{}}</script>
<script type="application/json" id="suggest-data">{self.suggest_data()}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{self.css_url}">
<script src="{self.js_url}" defer></script>
</head>
<body{body_attrs}>
<a class="skip" href="#main">Skip to content</a>
<div class="wrap">
{self.family_bar()}
<main id="main">
<div class="sitehead"><{tag} class="sitename">{e(self.title)}</{tag}>
<nav aria-label="Site">{''.join(nav)}</nav></div>
{main}
</main>
{self.footer()}
{self.family_foot()}
</div>
</body>
</html>
""")

    # The OpenCosmos family. Drawn the way @opencosmos/ui's Header and Footer
    # draw it on opencosmos.ai; the links come from texts.json, so a change to
    # that site's navigation is a data edit here.
    def family_bar(self):
        f = self.family
        links = "".join(f'<a href="{e(n["href"])}">{e(n["label"])}</a>' for n in f["nav"])
        return f"""<header class="family">
  <a class="mark" href="{e(f["url"])}">{e(f["name"])}</a>
  <nav aria-label="{e(f["name"])}">{links}</nav>
  <a class="gh" href="{e(self.repo_url)}" target="_blank" rel="noopener noreferrer"
     aria-label="GitHub (opens in a new tab)">{GITHUB_MARK}<span>GitHub</span></a>
</header>"""

    def family_foot(self):
        f = self.family
        return (f'<aside class="family-foot" aria-label="{e(f["name"])}"><p>Part of <a href="{e(f["url"])}">{e(f["name"])}</a>. '
                f'{e(f["about"])}</p>'
                f'<button type="button" class="theme">{THEME_ICONS}'
                f'<span class="theme-lab">Dark mode</span></button></aside>')

    def footer(self):
        repos = " · ".join(
            f'<a href="https://github.com/{e(t["repo"])}">{e(t["title"])}</a>'
            for t in self.data["texts"])
        return f"""<footer>
  <p><b>How to read this.</b> A Chinese character is usually built from parts, and
  the parts do two different jobs. A <em style="color:var(--accent);font-style:normal">semantic</em>
  part carries meaning. A <strong style="color:var(--pho);font-weight:400">phonetic</strong>
  part was borrowed for its sound alone and means nothing here, which is why the
  two are coloured differently and never merged.</p>
  <p><b>Where the analysis comes from.</b> <span class="zh" lang="zh-Hant">說文解字</span>
  (<i>Shuōwén Jiězì</i>), c. 100 CE, the earliest systematic account of how
  Chinese characters are built. It states each character's parts in its own
  words, so the semantic/phonetic split is the source's, not ours. A modern
  radical is a filing system; this is an analysis.</p>
  <p><b>What is ours, and what is not.</b> The Chinese is public domain by age.
  The English glosses, the translations, and the settled renderings are by Shalom
  Ormsby and are dedicated <b>CC0</b>: no rights reserved.</p>
  <p><b>Where it comes from.</b> Every word here is built from the translations'
  own repositories: {repos}. Edit a glossary entry there, and this site follows.
  The atlas itself: <a href="{e(self.repo_url)}">{e(self.cfg["site"]["repo"])}</a>.</p>
  <div class="suggest-general"></div>
</footer>"""

    def tabs(self):
        """One tab per project served, for the atlas and the glossary alike. A
        tab whose text has no export yet still appears, and opens on a note
        saying the translation is on its way."""
        tabs = ['<button role="tab" id="tab-all" data-text="all" aria-selected="true">All texts</button>']
        soon = []
        for sv in self.cfg["site"].get("serving", []):
            ready = sv["id"] in self.exports
            mark = "" if ready else '<span class="soonmark">in progress</span>'
            tabs.append(f'<button role="tab" id="tab-{e(sv["id"])}" data-text="{e(sv["id"])}" '
                        f'aria-selected="false" tabindex="-1">{e(sv["tab"])}{mark}</button>')
            if not ready:
                soon.append(f"""<section class="soon" id="soon-{e(sv["id"])}" hidden>
  <h2>{e(sv["tab"])} <span class="zh" lang="zh-Hant">{e(sv.get("title_zh", ""))}</span></h2>
  <p>{e(sv.get("soon", "This translation is in progress."))}</p>
  <p><a href="https://github.com/{e(sv["repo"])}">Follow the translation on GitHub</a></p>
</section>""")
        return tabs, soon

    def serving_names(self):
        """"the Open Tao Te Ching and the I Ching", each linked to its repo."""
        return " and ".join(
            f'the <a href="https://github.com/{e(p["repo"])}">{e(p["name"])}</a>'
            for p in self.cfg["site"].get("serving", []))

    def project_name(self, tid):
        """A text's project name ("Open Tao Te Ching"), from texts.json."""
        t = next((t for t in self.data["texts"] if t["id"] == tid), {})
        return next((sv["name"] for sv in self.cfg["site"].get("serving", [])
                     if sv["id"] == tid), t.get("title", tid))

    # -- the atlas --------------------------------------------------------
    def atlas_main(self, char=None):
        texts = self.data["texts"]
        # The projects this atlas serves, named as the projects name themselves
        # (texts.json site.serving). A project can be listed before its export
        # joins "texts", so the masthead can name it while its data is on the way.
        names = self.serving_names()
        tabs, soon = self.tabs()
        static = self.static_card(char) if char else ""
        return f"""<header class="top">
  <div class="mast">
    <div>
      <p>Every character in {names}, {e(self.family["name"])}&rsquo;s translations from
      classical Chinese, taken apart into the pieces it is built from, with what
      each piece means, where the character appears, and how each translation
      renders it.</p>
    </div>
  </div>
  <div class="scope">
    <div class="tabs" role="tablist" aria-label="Texts">{''.join(tabs)}</div>
    <div class="counts" aria-live="polite">
      <div><button type="button" class="kbtn" id="k-parts" aria-expanded="false"
        aria-controls="parts" title="Browse the parts these characters are built from"><span
        id="k-pt">—</span><span class="lab">parts</span></button></div>
      <div><span id="k-ch">—</span><div class="lab">characters</div></div>
      <div><span id="k-oc">—</span><div class="lab">total characters</div></div>
    </div>
  </div>
</header>
{''.join(soon)}
<div class="controls">
  <input type="search" id="q" placeholder="Search a character, sound, or meaning"
         aria-label="Search characters">
  <button id="f-lock" aria-pressed="false">Settled terms</button>
  <button id="f-real" aria-pressed="true">Hide grammar</button>
  <button id="s-freq" aria-pressed="true">By frequency</button>
  <button id="s-cent" aria-pressed="false">By reach</button>
  <span class="spacer"></span>
  <button id="clear" hidden>Reset parts filter</button>
</div>
<section class="pstrip" id="parts" aria-label="Parts" hidden>
  <div class="pstrip-head">
    <p class="legend">The parts these characters are built from, the most-used first.
      Pick one to show only the characters built from it.</p>
    <div class="pstrip-acts">
      <button type="button" id="parts-more" hidden></button>
      <button type="button" id="parts-close">Close</button>
    </div>
  </div>
  <div class="pgrid" id="pgrid"></div>
</section>
<div class="room">
  <div class="gridhead">
    <div class="lab" id="status" role="status"></div>
    <div class="lab key" id="key"><i class="dot" aria-hidden="true"></i>settled rendering</div>
  </div>
  <div class="grid" id="grid"></div>
  <aside class="card" aria-label="Character"><div class="card-in" id="card">{static}</div></aside>
</div>"""

    # -- entries ----------------------------------------------------------
    def md_ctx(self, tid):
        x = self.exports[tid]
        slugs = {en["slug"] for en in x["entries"]}
        repo = x["text"]["repo"]
        t = next(t for t in self.data["texts"] if t["id"] == tid)
        rd, unit = t.get("reader"), t.get("unit", "")

        def unit_url(n):
            if rd and 1 <= n <= t.get("units", 0):
                return rd["unit"].replace("{unit}", str(n))
            return None
        abbr = (t.get("abbr") or "").lower()
        words = tuple(w for w in (unit, unit + "s", abbr, abbr + "s") if w and w != "s") if rd else ()
        return md.Context(
            char_url=self.char_url,
            entry_url=lambda s: self.entry_url(tid, s) if s in slugs else None,
            repo_url=lambda p: f"https://github.com/{repo}/blob/main/{urllib.parse.quote(p)}",
            known_chars=frozenset(self.chars), unit_url=unit_url, unit_words=words)

    def entry_page(self, tid, en):
        t = next(t for t in self.data["texts"] if t["id"] == tid)
        body = md.render(en["body"], self.md_ctx(tid))
        # The entry's own title line is the page's one h1.
        # Every heading below it steps up one level with it, so the outline
        # runs h1, h2, h3 and never skips (### was landing as h3 under the h1).
        if body.startswith("<h2>"):
            import re
            body = "<h1>" + body[4:].replace("</h2>", "</h1>", 1)
            body = re.sub(r"<(/?)h([3-6])\b", lambda m: f"<{m[1]}h{int(m[2]) - 1}", body)
        chars = "".join(dict.fromkeys(en["chars"] + en["covers"]))
        repo = t["repo"]
        # Atlas and Glossary are the site head's links, just above; the crumb
        # starts at the text, which opens the glossary scoped to it.
        # "Suggest an edit" twice: at the top, where a reader sees it without
        # scrolling, and at the end, where one who has read the argument is.
        slot = (f'<div class="suggest-slot" data-tid="{e(tid)}" data-term="{e(en["term"])}" '
                f'data-pinyin="{e(en["pinyin"])}" data-render="{e(plain(en["render"]))}" '
                f'data-slug="{e(en["slug"])}"></div>')
        main = f"""<div class="entry-head">
<nav class="crumbs" aria-label="Breadcrumb">
  <a href="{self.base}glossary/?text={tid}">{e(t["title"])}</a> /
  <span class="zh" lang="zh-Hant">{e(en["term"])}</span></nav>
{slot}
</div>
<div class="entry-room" style="margin-top:0">
<article>
  <div class="prose">{body}</div>
  <p class="source">This page is <a href="https://github.com/{e(repo)}/blob/main/{e(en["path"])}"><code>{e(en["path"])}</code></a>
  in <a href="https://github.com/{e(repo)}">{e(repo)}</a>, rendered as written.
  Edit it there, and this page follows.</p>
  {slot}
</article>
<aside class="card" aria-label="The character, taken apart">
  <div class="card-in"><div class="chips" id="chips"></div><div id="card"></div></div>
</aside>
</div>"""
        title = f"{en['term']} {en['pinyin']} — {plain(en['render'])} · {self.project_name(tid)} glossary"
        desc = (f"How the {t['title']} renders {en['term']} ({en['pinyin']}): "
                f"{plain(en['render'])}. The research, the oldest forms, and what is set aside.")
        self.page(f"glossary/{tid}/{en['slug']}/index.html", title, desc, main,
                  f' data-page="entry" data-chars="{e(chars)}"', "glossary",
                  self.entry_head(tid, en))

    # -- the glossary ------------------------------------------------------
    def glossary_records(self):
        """Every entry of every text, as the glossary page searches and previews
        it: the ruling, the words it sets aside, and its opening paragraph."""
        import re
        import unicodedata
        recs = []
        for tid, x in self.exports.items():
            ctx = self.md_ctx(tid)
            for en in x["entries"]:
                paras = [p.strip() for p in re.split(r"\n\s*\n", en["body"]) if p.strip()]
                lock = next((p for p in paras if p.startswith(("**Locked", "**Recommended"))), "")
                after = paras[paras.index(lock) + 1:] if lock else paras[1:]
                lead = next((p for p in after if not p.startswith(("#", "|", ">", "-", "*Say", "1."))), "")
                chs = en.get("chapters")
                if not chs:   # older exports: the chapters every character of the term shares
                    sets = [set(self.chars[c]["t"].get(tid, {}).get("chs") or [])
                            for c in en["chars"] if c in self.chars]
                    chs = sorted(set.intersection(*sets)) if sets else []
                form = ("pairing" if "&" in en["term"] or "/" in en["pinyin"]
                        else "compound" if len(en["chars"]) > 1 else "character")
                key = unicodedata.normalize("NFD", en["pinyin"]).encode("ascii", "ignore").decode().lower()
                recs.append({
                    "tid": tid, "slug": en["slug"], "term": en["term"], "chars": en["chars"],
                    "pinyin": en["pinyin"], "key": key, "render": plain(en["render"]),
                    "status": en["status"], "form": form, "chapters": chs,
                    "aside": [plain(w) for w in en.get("forbidden") or []],
                    "lock": md.render(lock, ctx) if lock else "",
                    "lead": md.render(lead, ctx) if lead else "",
                })
        return sorted(recs, key=lambda r: (r["key"], r["tid"]))

    def glossary_page(self, recs):
        tabs, soon = self.tabs()
        static = "".join(
            f'<li><a href="{self.entry_url(r["tid"], r["slug"])}"><span class="zh" lang="zh-Hant">{e(r["term"])}</span> '
            f'{e(r["pinyin"])} — {e(r["render"])}</a> ({e(self.project_name(r["tid"]))})</li>'
            for r in recs)
        main = f"""<header class="top">
  <div class="mast"><div>
    <p>Each entry is the argument behind one ruling in {self.serving_names()}:
    what a term is, its oldest forms, how the text uses it, and why the English
    reads as it does. Rulings belong to their translation, so the same character
    can be ruled differently in each.</p>
  </div></div>
  <div class="scope">
    <div class="tabs" role="tablist" aria-label="Texts">{''.join(tabs)}</div>
    <div class="counts" aria-live="polite">
      <div><span id="g-n">—</span><div class="lab">entries</div></div>
      <div><span id="g-set">—</span><div class="lab">settled</div></div>
      <div><span id="g-open">—</span><div class="lab">open</div></div>
    </div>
  </div>
</header>
{''.join(soon)}
<div class="controls gcontrols">
  <input type="search" id="gq" placeholder="Search terms, English, or words set aside"
         aria-label="Search the glossary">
  <div class="seg" role="group" aria-label="Status">
    <button data-status="all" aria-pressed="true">All</button>
    <button data-status="locked" aria-pressed="false">Settled</button>
    <button data-status="open" aria-pressed="false">Open</button>
  </div>
  <select id="gform" aria-label="Form">
    <option value="all">Every form</option>
    <option value="character">Characters</option>
    <option value="compound">Compounds</option>
    <option value="pairing">Pairings</option>
  </select>
  <select id="gch" aria-label="Chapter"></select>
  <select id="gsort" aria-label="Sort">
    <option value="az">A–Z by pinyin</option>
    <option value="reach">By reach</option>
  </select>
</div>
<div class="room groom">
  <div class="lab" id="gstatus" role="status" style="padding-bottom:8px"></div>
  <div class="glist" id="glist"><ul class="gstatic">{static}</ul></div>
  <aside class="card gprev-card" aria-label="Entry preview"><div class="card-in" id="gprev"></div></aside>
</div>"""
        self.page("glossary/index.html", f"Glossary · {self.title}",
                  "Every glossary entry of the OpenCosmos Chinese translations: the "
                  "argument behind each ruling, searchable by the words it sets aside.",
                  main, ' data-page="glossary"', "glossary")

    # -- what a reader without script, or an agent, receives ---------------
    # The card is drawn by atlas.js from data.json, and an agent fetching the page
    # runs no script. So the page ships the card's substance as plain HTML in the
    # card itself, which the script replaces on load. (It used to sit in a
    # <noscript>, which most HTML-to-text tools discard.)
    def static_card(self, char):
        c = self.chars[char]
        glyphs = self.data["glyphs"]
        rows = []
        for t in self.data["texts"]:
            r = c["t"].get(t["id"])
            if not r:
                continue
            E = self.data["entries"][t["id"]]

            def link(s):
                # An entry that only covers this character (營 inside 魄) is
                # named, so its rendering is not taken for this character's.
                en = E.get(s)
                if not en or char in en["term"]:
                    return (f' <a href="{self.entry_url(t["id"], s)}">'
                            f'Read the glossary entry</a>.')
                return (f' Ruled inside the glossary entry for <span class="zh" '
                        f'lang="zh-Hant">{e(en["term"])}</span> ({e(en["pinyin"])} — '
                        f'{e(en["render"])}): <a href="{self.entry_url(t["id"], s)}">'
                        f'read it</a>.')
            links = "".join(link(s) for s in r.get("entries") or [])
            chs = r.get("chs") or []
            rd = t.get("reader")

            def unit(n):
                if not rd:
                    return str(n)
                return f'<a href="{e(rd["unit"].replace("{unit}", str(n)))}">{n}</a>'
            where = (f' Appears {r["n"]} times, in chapter{"" if len(chs) == 1 else "s"} '
                     f'{", ".join(unit(n) for n in chs)}.' if chs else "")
            rows.append(f'<p><b>{e(t["title"])}:</b> {e(r["g"] or "not yet glossed")}.'
                        f'{links}{where}</p>')

        def part(g, role):
            pin, gloss = (glyphs.get(g) or ["", ""])
            return (f'<li><span class="zh" lang="zh-Hant">{e(g)}</span> {e(pin)}'
                    f'{" — " + e(gloss) if gloss else ""} ({role})</li>')
        parts = ([part(g, "carries meaning") for g in c.get("sem") or []] +
                 [part(g, "borrowed for its sound") for g in c.get("pho") or []])
        built = (f'<p class="legend"><b>Built from</b></p><ul>{"".join(parts)}</ul>'
                 if parts else "")
        swz = (f'<p class="legend"><b>說文解字</b> (c. 100 CE): '
               f'<span class="zh" lang="zh-Hant">{e(c["def"])}</span></p>' if c.get("def") else "")
        return (f'<div class="hero"><div class="big" lang="zh-Hant">{e(char)}</div><div class="meta">'
                f'<div class="pin">{e(c["p"])}</div>{"".join(rows)}</div></div>{built}{swz}')

    def entry_head(self, tid, en):
        t = next(t for t in self.data["texts"] if t["id"] == tid)
        site = f"https://{self.domain}" if self.domain else ""
        src = f'https://raw.githubusercontent.com/{t["repo"]}/main/{urllib.parse.quote(en["path"])}'
        ld = {"@context": "https://schema.org", "@type": "DefinedTerm",
              "name": en["term"], "alternateName": en["pinyin"],
              "description": plain(en["render"]),
              "url": site + self.entry_url(tid, en["slug"]),
              "inDefinedTermSet": {"@type": "DefinedTermSet",
                                   "name": f"{self.project_name(tid)} glossary",
                                   "url": f"{site}{self.base}glossary/?text={tid}"},
              "isBasedOn": f'https://github.com/{t["repo"]}/blob/main/{en["path"]}',
              "license": "https://creativecommons.org/publicdomain/zero/1.0/"}
        blob = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
        return (f'<link rel="alternate" type="text/markdown" href="{e(src)}">\n'
                f'<script type="application/ld+json">{blob}</script>\n')

    def write_discovery(self, recs):
        """robots.txt, sitemap.xml and llms.txt: where everything is, for a
        crawler or an agent that would otherwise have to run the page to find out."""
        site = f"https://{self.domain}" if self.domain else ""
        root = f"{site}{self.base}"
        urls = [root, f"{root}glossary/"]
        urls += [f"{site}{self.char_url(c)}" for c in self.chars]
        urls += [f"{site}{self.entry_url(r['tid'], r['slug'])}" for r in recs]
        self.write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                   + "".join(f"<url><loc>{html.escape(u)}</loc></url>\n" for u in urls)
                   + "</urlset>\n")
        self.write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {root}sitemap.xml\n")

        serving = self.cfg["site"].get("serving", [])
        lines = [f"# {self.title}", "",
                 "> Every character in the classical Chinese texts OpenCosmos translates, "
                 "taken apart: its parts, its 說文解字 analysis (c. 100 CE), every line it "
                 "stands in, and how each translation renders it. The glossary is the "
                 "argument behind each settled rendering. Everything here is CC0.", "",
                 "Nothing on this site is authored here. It is built from each translation's "
                 "repository, so the Markdown sources below are the canonical text.", "",
                 "## Data", "",
                 f"- [data.json]({root}assets/data.json): every character. `chars[]` has "
                 "`c` (the character), `p` (pinyin), `sem`/`pho` (parts that carry meaning / "
                 "sound, per 說文), `def` (說文's definition), and `t[text id]` with `g` (the "
                 "English), `lock` (1 if settled), `n` (occurrences), `chs` (chapters) and "
                 "`entries` (glossary slugs). `glyphs` maps a part to [pinyin, gloss]. "
                 "`where[text id][character]` lists [line id, count] pairs, and "
                 "`lines[text id][line id]` is [Chinese, pinyin, English, exact, verse] (exact is 0 where the line pairing is approximate; "
                 "verse is the English line that renders it, 0 where none does): every line "
                 "a character stands in, with the translation's English. `texts[].reader` holds the address "
                 "of the translation's reader, a unit (`{unit}`) or an English line (`{unit}`, `{verse}`).",
                 f"- [glossary.json]({root}assets/glossary.json): every glossary entry, with "
                 "its ruling (`render`), `status` (locked or open), `chapters`, and `aside` "
                 "(renderings it rules out).", ""]
        for t in self.data["texts"]:
            sv = next((s for s in serving if s["id"] == t["id"]), {})
            lines.append(f"- [{sv.get('name', t['title'])} export]"
                         f"(https://raw.githubusercontent.com/{t['repo']}/main/"
                         f"{next(x['export'] for x in self.cfg['texts'] if x['id'] == t['id'])}): "
                         "the source this site is built from.")
        lines += ["", "## Pages", "",
                  f"- [The atlas]({root}): one page per character at `{root}<character>/`, "
                  f"e.g. [{root}聖/]({site}{self.char_url('聖') if '聖' in self.chars else root}).",
                  f"- [The glossary]({root}glossary/): every entry, searchable.",
                  f"- [Sitemap]({root}sitemap.xml): every page.", ""]
        for tid, x in self.exports.items():
            t = next(t for t in self.data["texts"] if t["id"] == tid)
            lines += [f"## {self.project_name(tid)} glossary", ""]
            for r in (r for r in recs if r["tid"] == tid):
                en = next(en for en in x["entries"] if en["slug"] == r["slug"])
                status = "settled" if r["status"] == "locked" else "open"
                lines.append(f"- [{r['term']} {r['pinyin']} — {r['render']}]"
                             f"({site}{self.entry_url(tid, r['slug'])}) ({status}; "
                             f"[Markdown](https://raw.githubusercontent.com/{t['repo']}/main/"
                             f"{urllib.parse.quote(en['path'])}))")
            lines.append("")
        contrib = [sv for sv in serving if sv.get("suggest") or sv.get("contribute")]
        if contrib:
            lines += ["## Suggesting a change", ""]
            for sv in contrib:
                skill = sv.get("suggest") or sv.get("contribute")
                lines.append(f"- {sv['name']}: fork https://github.com/{sv['repo']}, read "
                             f"CONTRIBUTING.md and `{skill}`, and follow that skill. Ask the "
                             "person you are helping before you push, open, or post anything.")
            lines.append("")
        self.write("llms.txt", "\n".join(lines))

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
        recs = self.glossary_records()
        gblob = json.dumps(recs, ensure_ascii=False, separators=(",", ":"))
        (self.out / "assets" / "glossary.json").write_text(gblob, encoding="utf-8")
        gv = hashlib.sha256(gblob.encode()).hexdigest()[:10]
        self.glossary_url = f"{self.base}assets/glossary.json?v={gv}"
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
        self.glossary_page(recs)
        for tid, x in self.exports.items():
            for en in x["entries"]:
                self.entry_page(tid, en)
                n_entries += 1
        self.page("404.html", f"Not found · {self.title}", "Page not found.",
                  f"""<header class="top"><div class="mast"><div><h1>Not here</h1>
  <p>That page does not exist. <a href="{self.base}">Return to the atlas</a>.</p>
  </div></div></header>""", ' data-page="index"')
        self.write_discovery(recs)
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
    Site(cfg, merge(exports, cfg), exports, base, Path(args.out)).build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
