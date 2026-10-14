#!/usr/bin/env python3
"""fonts.py — the rare characters' typeface, cut to exactly what the site shows.

    python3 -m atlas.build --base /                # first, so site/ is current
    pip install fonttools brotli                   # once; this tool only
    python3 -m atlas.fonts --source <dir holding HanaMinA.ttf and HanaMinB.ttf>

Songti (on Apple devices) and Noto Serif TC (everywhere else) cover the common
characters. Neither covers the rare ones — CJK Extension A, Extension B and
beyond — and those are exactly the graphs the atlas exists to show: 說文's
older forms and the components inside 說文's analyses (𩠐, 𦘫, 𦣻). Without a
font for them a reader sees an empty box where the explanation should be.

HanaMin (花園明朝, GlyphWiki Project) is a Ming/Song face like Songti, covers
every block the site reaches, and is free to modify and redistribute under the
Hanazono Font License (it is also offered under the OFL; we use the Hanazono
licence, which has no renaming condition for modified versions). Source:
https://glyphwiki.org/hanazono/ — hanazono-20170904.zip.

This writes two subsets into atlas/assets/fonts/, a few kilobytes each, and
`rare-han.txt`, the list they cover. The build reads that list, so it needs no
font tools: if a glossary edit introduces a rare character the subset lacks,
the build warns and names it, and running this again closes the gap.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "assets" / "fonts"


def is_rare(ch):
    o = ord(ch)
    return (0x3400 <= o <= 0x4DBF or 0x2E80 <= o <= 0x2FDF or o >= 0x20000)


def used(site):
    seen = set()
    for p in site.rglob("*"):
        if p.suffix in (".html", ".json") and p.is_file():
            seen.update(c for c in p.read_text(encoding="utf-8") if is_rare(c))
    return seen


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", required=True, help="directory with HanaMinA.ttf and HanaMinB.ttf")
    ap.add_argument("--site", default=str(ROOT / "site"))
    args = ap.parse_args(argv)
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.exit("  needs fonttools and brotli: pip install fonttools brotli")

    want = used(Path(args.site))
    if not want:
        sys.exit("  no rare characters found — build the site first")
    OUT.mkdir(parents=True, exist_ok=True)
    covered = set()
    for name, pick in (("rare-a", lambda c: ord(c) < 0x20000),
                       ("rare-b", lambda c: ord(c) >= 0x20000)):
        src = Path(args.source) / ("HanaMinA.ttf" if name == "rare-a" else "HanaMinB.ttf")
        cmap = TTFont(src, lazy=True).getBestCmap()
        chars = sorted(c for c in want if pick(c) and ord(c) in cmap)
        covered.update(chars)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = []
        opts.name_IDs = ["*"]
        opts.notdef_outline = False
        font = subset.load_font(str(src), opts)
        s = subset.Subsetter(opts)
        s.populate(unicodes=[ord(c) for c in chars])
        s.subset(font)
        dest = OUT / f"{name}.woff2"
        subset.save_font(font, str(dest), opts)
        print(f"  {name}.woff2  {len(chars):>3} glyphs  {dest.stat().st_size / 1024:.1f} KB")
    (OUT / "rare-han.txt").write_text("".join(sorted(covered)) + "\n", encoding="utf-8")
    missing = sorted(want - covered)
    if missing:
        print(f"  not in HanaMin ({len(missing)}): {''.join(missing)}")
    print(f"  covered {len(covered)} of {len(want)}  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
