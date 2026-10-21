"""The whole site, built and checked: every page there, every link resolving,
no Markdown left unrendered. Reads sibling checkouts when present; set
ATLAS_REMOTE=1 to build from GitHub, as CI does."""

import json
import os
import re
import tempfile
import unittest
import urllib.parse
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
        cls.data = build.merge(cls.exports)
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

    def test_entry_headings_never_skip_a_level(self):
        for page in self.out.glob("glossary/*/*/index.html"):
            prose = page.read_text(encoding="utf-8").split('<div class="prose">', 1)[1]
            levels = [int(n) for n in re.findall(r"<h([1-6])\b", prose.split("</article>", 1)[0])]
            for a, b in zip(levels, levels[1:]):
                self.assertLessEqual(b - a, 1, f"{page.parent.name}: h{a} then h{b}")


if __name__ == "__main__":
    unittest.main()
