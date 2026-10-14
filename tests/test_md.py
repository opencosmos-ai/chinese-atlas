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
        self.assertEqual(out, '<span class="zh"><a class="zc" href="/道/">道</a>德</span>')

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
