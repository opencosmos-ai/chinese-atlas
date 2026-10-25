import unittest

from atlas import md


class Inline(unittest.TestCase):
    def test_emphasis(self):
        self.assertEqual(md.inline("**a** *b* ***c***", md.Context()),
                         "<strong>a</strong> <em>b</em> <strong><em>c</em></strong>")

    def test_escape_is_literal(self):
        # 道 is roughly *\*l'uːʔ* — the escaped asterisk must survive as text.
        out = md.inline(r"*\*l'uːʔ*", md.Context())
        self.assertEqual(out, "<em>*l'uːʔ</em>")

    def test_html_is_escaped(self):
        self.assertIn("&lt;b&gt;", md.inline("<b>", md.Context()))

    def test_han_is_wrapped_and_linked(self):
        ctx = md.Context(char_url=lambda c: f"/{c}/", known_chars=frozenset("道"))
        out = md.inline("道德", ctx)
        self.assertEqual(out, '<span class="zh" lang="zh-Hant"><a class="zc" href="/道/">道</a>德</span>')

    def test_code_path_links(self):
        ctx = md.Context(entry_url=lambda s: f"/e/{s}/" if s == "de-德" else None,
                         repo_url=lambda p: f"https://x/{p}")
        self.assertIn('href="/e/de-德/"', md.inline("`glossary/de-德.md`", ctx))
        self.assertIn('href="https://x/chapters/001.md"', md.inline("`chapters/001.md`", ctx))
        self.assertNotIn("href", md.inline("`render:`", ctx))


class Blocks(unittest.TestCase):
    def test_table(self):
        out = md.render("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<th>a</th>", out)
        self.assertIn("<td>2</td>", out)

    def test_blockquote_keeps_lines_together(self):
        out = md.render("> one\n>\n> two")
        self.assertEqual(out.count("<blockquote>"), 1)
        self.assertIn("<p>one</p>", out)

    def test_lists(self):
        self.assertIn("<ol><li>a</li><li>b</li></ol>", md.render("1. a\n2. b"))
        self.assertIn("<ul><li>a</li></ul>", md.render("- a"))


if __name__ == "__main__":
    unittest.main()


class Units(unittest.TestCase):
    """Chapter citations link to the translation's reader."""

    ctx = md.Context(unit_url=lambda n: f"R/{n}" if 1 <= n <= 81 else None,
                     unit_words=("chapter", "chapters", "ch", "chs"))

    def links(self, html):
        import re
        return re.findall(r'href="R/(\d+)"', html)

    def test_every_form_of_citation(self):
        self.assertEqual(self.links(md.inline("ch 6 · Chapter 16 · chs 6 and 52", self.ctx)),
                         ["6", "16", "6", "52"])
        self.assertEqual(self.links(md.inline("天地不仁 (5), and (2, 77)", self.ctx)), ["5", "2", "77"])

    def test_numbers_that_are_not_chapters_stay_plain(self):
        for s in ("Analects 2.18", "(14.37)", "(100)", "(d. 249)", "3–4 lines", "(2009)"):
            self.assertEqual(self.links(md.inline(s, self.ctx)), [], s)

    def test_a_table_column_or_row_of_chapters(self):
        t = md.render("| | 尤 |\n|---|---|\n| chapters | 9, 46 |\n\n"
                      "| English | Where |\n|---|---|\n| strain | 6, 52 |", self.ctx)
        self.assertEqual(self.links(t), ["9", "46", "6", "52"])

    def test_no_reader_no_links(self):
        self.assertNotIn("<a", md.inline("ch 6 (5)", md.Context()))
