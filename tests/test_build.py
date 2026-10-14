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
                self.assertTrue((self.out / tid / "glossary" / en["slug"] / "index.html").exists(),
                                en["slug"])

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
        for page in (self.out).glob("*/glossary/*/index.html"):
            prose = page.read_text(encoding="utf-8").split('<div class="prose">', 1)[1]
            prose = prose.split("</article>", 1)[0]
            text = re.sub(r"<code>.*?</code>", "", prose)
            text = re.sub(r"<[^>]+>", "", text)
            for mark in ("**", "`", "](", "\n## ", "\n| "):
                self.assertNotIn(mark, text, f"{page.parent.name}: {mark!r}")


if __name__ == "__main__":
    unittest.main()
