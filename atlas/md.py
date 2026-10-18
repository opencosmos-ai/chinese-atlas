"""md.py — the Markdown the glossary entries use, and nothing more.

A general Markdown library would be a dependency, and these tools have none.
The entries use a small, regular subset: headings, paragraphs, emphasis, code
spans, backslash escapes, blockquotes, flat lists, and pipe tables. This renders
exactly that. Anything outside it is printed as text rather than guessed at, and
tests/test_md.py renders every real entry to keep that honest.

Two things are added on the way through, both for the atlas's reader:

- **Han characters are set in the Song face.** Runs of CJK are wrapped in
  <span class="zh" lang="zh-Hant">, and each character that has an atlas page links to it.
- **Repository paths become links.** A code span naming a glossary entry links
  to that entry's page; any other path links to the file on GitHub.
"""

import html
import re

HAN = "㐀-䶿一-鿿豈-﫿\U00020000-\U0002ebef"
HAN_RUN = re.compile(f"[{HAN}]+")


class Context:
    """What the renderer needs to know to make links."""

    def __init__(self, char_url=None, entry_url=None, repo_url=None,
                 known_chars=frozenset()):
        self.char_url = char_url or (lambda c: None)
        self.entry_url = entry_url or (lambda slug: None)
        self.repo_url = repo_url or (lambda path: None)
        self.known_chars = known_chars


# ---------------------------------------------------------------- inline

def _han(text, ctx):
    """Wrap Han runs in the Song face, linking each character with a page."""
    def run(m):
        out = []
        for c in m.group(0):
            url = ctx.char_url(c) if c in ctx.known_chars else None
            out.append(f'<a class="zc" href="{url}">{c}</a>' if url else c)
        return f'<span class="zh" lang="zh-Hant">{"".join(out)}</span>'
    return HAN_RUN.sub(run, text)


def _code(span, ctx):
    path = span.strip()
    name = path.rsplit("/", 1)[-1]
    url = None
    if name.endswith(".md") and (path.startswith("glossary/") or "/" not in path):
        url = ctx.entry_url(name[:-3])
    if url is None and "/" in path and not path.startswith(("http", "/")):
        url = ctx.repo_url(path)
    inner = f"<code>{html.escape(span)}</code>"
    return f'<a class="path" href="{url}">{inner}</a>' if url else inner


def inline(text, ctx):
    # Code spans and escapes are lifted out first so nothing inside them is
    # read as emphasis, then put back at the end.
    held = []

    def hold(s):
        held.append(s)
        return f"\x00{len(held) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: hold(_code(m.group(1), ctx)), text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>~])",
                  lambda m: hold(html.escape(m.group(1))), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", text)
    text = _han(text, ctx)
    return re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], text)


# ---------------------------------------------------------------- blocks

def _cells(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in row.split("|")]


def _is_rule_row(row):
    return bool(re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", row.strip()))


def render(md, ctx=None):
    ctx = ctx or Context()
    lines = md.replace("\r\n", "\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2).strip(), ctx)}</h{n}>")
            i += 1
            continue

        if re.match(r"^-{3,}$", line.strip()):
            out.append("<hr>")
            i += 1
            continue

        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(re.sub(r"^> ?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{render(chr(10).join(block), ctx)}</blockquote>")
            continue

        if line.lstrip().startswith("|") and i + 1 < len(lines) and _is_rule_row(lines[i + 1]):
            head = _cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            t = ["<div class=\"tbl\"><table><thead><tr>"]
            t += [f"<th>{inline(c, ctx)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{inline(c, ctx)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue

        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+", line)
        if lm:
            ordered = lm.group(2)[0].isdigit()
            items = []
            pat = r"^\s*\d+\.\s+" if ordered else r"^\s*[-*]\s+"
            while i < len(lines) and re.match(pat, lines[i]):
                item = re.sub(pat, "", lines[i])
                i += 1
                # A wrapped continuation line belongs to the item above it.
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() \
                        and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(item, ctx)}</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        para = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|>|\s*([-*]|\d+\.)\s|-{3,}$)", lines[i]) \
                and not (lines[i].lstrip().startswith("|") and i + 1 < len(lines)
                         and _is_rule_row(lines[i + 1])):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(para), ctx)}</p>")
    return "\n".join(out)
