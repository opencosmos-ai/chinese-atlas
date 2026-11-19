"""The whole site, built and checked: every page there, every link resolving,
no Markdown left unrendered. Reads sibling checkouts when present; set
ATLAS_REMOTE=1 to build from GitHub, as CI does."""

import json
import os
import re
import tempfile
import unittest
import urllib.parse
from copy import deepcopy
from pathlib import Path

from atlas import build

ROOT = Path(__file__).resolve().parent.parent


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cfg = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))
        cls.exports = build.fetch(cfg, bool(os.environ.get("ATLAS_REMOTE")))
        cls.data = build.merge(cls.exports, cfg)
        build.Site(cfg, cls.data, cls.exports, "/", cls.out).build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_character_has_a_page(self):
        for c in self.data["chars"]:
            self.assertTrue((self.out / c["c"] / "index.html").exists(), c["c"])

    def test_every_entry_has_a_page(self):
        for tid, x in self.exports.items():
            for en in x["entries"]:
                self.assertTrue((self.out / "glossary" / tid / en["slug"] / "index.html").exists(),
                                en["slug"])

    def test_glossary_lists_every_entry_without_script(self):
        page = (self.out / "glossary" / "index.html").read_text(encoding="utf-8")
        for tid, x in self.exports.items():
            for en in x["entries"]:
                self.assertIn(f'/glossary/{tid}/{urllib.parse.quote(en["slug"])}/', page, en["slug"])

    def test_internal_links_resolve(self):
        broken = set()
        for page in self.out.rglob("*.html"):
            for href in re.findall(r'href="(/[^"#?]*)', page.read_text(encoding="utf-8")):
                target = self.out / urllib.parse.unquote(href).lstrip("/")
                if href.endswith("/"):
                    target = target / "index.html"
                if not target.exists():
                    broken.add(href)
        self.assertEqual(sorted(broken), [])

    def test_no_markdown_survives_rendering(self):
        for page in (self.out).glob("glossary/*/*/index.html"):
            prose = page.read_text(encoding="utf-8").split('<div class="prose">', 1)[1]
            prose = prose.split("</article>", 1)[0]
            text = re.sub(r"<code>.*?</code>", "", prose)
            text = re.sub(r"<[^>]+>", "", text)
            for mark in ("**", "`", "](", "\n## ", "\n| "):
                self.assertNotIn(mark, text, f"{page.parent.name}: {mark!r}")

    # -- what an agent, a crawler, or a screen reader receives -------------

    def test_sitemap_and_llms_txt_list_every_page(self):
        sitemap = (self.out / "sitemap.xml").read_text(encoding="utf-8")
        llms = (self.out / "llms.txt").read_text(encoding="utf-8")
        self.assertIn("Sitemap:", (self.out / "robots.txt").read_text(encoding="utf-8"))
        for c in self.data["chars"]:
            self.assertIn(f'/{urllib.parse.quote(c["c"])}/</loc>', sitemap, c["c"])
        for tid, x in self.exports.items():
            for en in x["entries"]:
                path = f'/glossary/{tid}/{urllib.parse.quote(en["slug"])}/'
                self.assertIn(path + "</loc>", sitemap, en["slug"])
                self.assertIn(path + ")", llms, en["slug"])

    def test_a_character_page_says_what_it_knows_without_script(self):
        for c in self.data["chars"]:
            page = (self.out / c["c"] / "index.html").read_text(encoding="utf-8")
            card = page.split('id="card">', 1)[1].split("</aside>", 1)[0]
            for tid, r in c["t"].items():
                for slug in r.get("entries") or []:
                    self.assertIn(f'/glossary/{tid}/{urllib.parse.quote(slug)}/', card, c["c"])
                if r.get("chs"):
                    self.assertIn(f'Appears {r["n"]} times', card, c["c"])

    def test_shuowen_card_pairs_its_own_reading_with_an_english_definition(self):
        cfg = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))
        exports = deepcopy(self.exports)
        char = next(c for c in exports["tao-te-ching"]["chars"] if c["c"] == "\u57cf")
        char.update(p="shān", shuowen={"pinyin": "yán", "english": "The far reaches of the earth."})
        site = build.Site(cfg, build.merge(exports, cfg), exports, "/", self.out)
        card = site.static_card(char["c"])
        self.assertIn('<div class="pin">shān</div>', card)
        self.assertIn('<span lang="zh-Latn-pinyin">yán</span> — The far reaches of the earth.', card)
        self.assertNotIn(char["def"], card)

        char["shuowen"] = {"pinyin": "yán"}
        site = build.Site(cfg, build.merge(exports, cfg), exports, "/", self.out)
        card = site.static_card(char["c"])
        self.assertNotIn('class="blk shuowen"', card)
        self.assertNotIn(char["def"], card)

    def test_a_line_knows_the_english_line_the_reader_opens(self):
        """A citation opens the translation's reader at the English line that
        renders the Chinese one. Ch 41's first line is its first English line."""
        lines = self.data["lines"]["tao-te-ching"]
        self.assertEqual(lines["41.1"][4], 1)
        for key, L in lines.items():
            self.assertGreater(L[4], 0, key)

    def test_a_character_page_links_its_chapters_to_the_reader(self):
        page = (self.out / "勤" / "index.html").read_text(encoding="utf-8")
        card = page.split('id="card">', 1)[1].split("</aside>", 1)[0]
        for n in (6, 41, 52):
            self.assertIn(
                f'href="https://opencosmos.ai/library/sources/taoism-tao-te-ching/{n}"', card)

    def test_source_footers_use_registry_anchors_and_show_incomplete_citations(self):
        cfg = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))
        page_url = "https://example.test/translation/sources"
        cfg["texts"][0]["reader"]["sources"] = page_url
        tid = cfg["texts"][0]["id"]
        exports = deepcopy(self.exports)
        export = exports[tid]
        export["sources"] = {"records": [
            {"id": "historical-work", "name": "Historical Work",
             "editions": [{"id": "reprint", "title": "Reprint Edition"}]},
            {"id": "catalogue", "name": "Research Catalogue"},
        ]}
        for entry in export["entries"]:
            entry.update(refs_status="complete", refs=[])
        cited, incomplete, complete = export["entries"][:3]
        cited.update(refs_status="incomplete", refs=[{
            "source": "historical-work", "via": "catalogue", "chain": ["catalogue"], "edition": "reprint",
            "locator": "Entry 3 & note 2", "url": "https://example.test/entry?q=3&note=2",
        }, {
            "source": "catalogue", "chain": [], "locator": "Manuscript notes",
            "url": "notes/manuscript.md#chapter-1",
        }])
        incomplete["refs_status"] = "incomplete"

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            site = build.Site(cfg, build.merge(exports, cfg), exports, "/", out)
            site.build()
            pages = [(out / "glossary" / tid / en["slug"] / "index.html").read_text(encoding="utf-8")
                     for en in (cited, incomplete, complete)]
            self.assertIn(f'<a href="{page_url}#historical-work">Historical Work</a> via ', pages[0])
            self.assertIn(f'<a href="{page_url}#catalogue">Research Catalogue</a>', pages[0])
            self.assertIn(' · Reprint Edition · ', pages[0])
            self.assertIn('<a href="https://example.test/entry?q=3&amp;note=2">Entry 3 &amp; note 2</a>',
                          pages[0])
            self.assertIn('https://github.com/opencosmos-ai/taoteching/blob/main/notes/manuscript.md#chapter-1', pages[0])
            self.assertIn("Citation records are incomplete.", pages[0])
            self.assertIn("Citation records are incomplete.", pages[1])
            self.assertNotIn('class="entry-sources"', pages[2])
            card = (out / self.data["chars"][0]["c"] / "index.html").read_text(encoding="utf-8")
            self.assertIn(f'<a href="{page_url}">Translation sources</a>', card)

            cited["refs"][0]["source"] = "unknown"
            with self.assertRaisesRegex(ValueError, "unknown citation source"):
                site.entry_sources(site.data["texts"][0], cited)

    def test_a_covering_entry_is_named_not_passed_off_as_the_characters_own(self):
        # 營 is ruled inside 魄's entry, as "housing"; its card must not read
        # as if 營 meant 魄's "aliveness".
        checked = 0
        for c in self.data["chars"]:
            for tid, r in c["t"].items():
                E = self.data["entries"][tid]
                for slug in r.get("entries") or []:
                    if c["c"] in E[slug]["term"]:
                        continue
                    page = (self.out / c["c"] / "index.html").read_text(encoding="utf-8")
                    self.assertIn(f'Ruled inside the glossary entry for <span class="zh" '
                                  f'lang="zh-Hant">{build.e(E[slug]["term"])}</span>', page, c["c"])
                    checked += 1
        self.assertGreater(checked, 0)

    def test_every_page_has_one_main_and_marks_its_chinese(self):
        # A screen reader voices Chinese only when it is marked as Chinese, so
        # every element that sets Han text carries lang="zh-Hant".
        for page in self.out.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertEqual(text.count("<main"), 1, page)
            body = re.sub(r"(?s)<head>.*?</head>|<script.*?</script>", "", text)
            unmarked = [m[0] for m in re.finditer(r'class="(zh|big|pg)"(?! lang="zh-Hant")', body)]
            self.assertEqual(unmarked, [], page)

    def test_a_part_says_how_it_is_written_only_where_it_is(self):
        # 沖's card said "built from 水", and a reader could not find water in 沖:
        # at the left it is written 氵. Then it said "氵 at the left, 氺 at the
        # bottom", and 沖 has no 氺 (2026-11-15). A row shows on the pages of
        # its own characters, and on no other.
        forms = self.data.get("forms") or {}
        for c in self.data["chars"]:
            parts = [p for p in (c.get("sem") or []) + (c.get("pho") or []) if p in forms]
            if not parts:
                continue
            page = (self.out / c["c"] / "index.html").read_text(encoding="utf-8")
            built = page.split("<b>Built from</b>", 1)[-1].split("</ul>", 1)[0]
            for p in parts:
                for row in forms[p]:
                    mark = f'<span class="zh" lang="zh-Hant">{row[0]}</span>, its form {row[1]}'
                    shown = len(row) > 2 and c["c"] in row[2]
                    self.assertEqual(mark in built, shown, (c["c"], p, row[:2]))

    def test_entry_headings_never_skip_a_level(self):
        for page in self.out.glob("glossary/*/*/index.html"):
            prose = page.read_text(encoding="utf-8").split('<div class="prose">', 1)[1]
            levels = [int(n) for n in re.findall(r"<h([1-6])\b", prose.split("</article>", 1)[0])]
            for a, b in zip(levels, levels[1:]):
                self.assertLessEqual(b - a, 1, f"{page.parent.name}: h{a} then h{b}")


if __name__ == "__main__":
    unittest.main()
