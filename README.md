# Open Classical Chinese Character Atlas

Every character in the classical Chinese texts OpenCosmos translates, taken
apart: the pieces it is built from and what each piece means, its analysis in
說文解字 (*Shuōwén Jiězì*, c. 100 CE), every line it stands in, and how each
translation renders it. Every glossary entry, in full, with the character beside
it.

**Now holding:** the [Tao Te Ching](https://github.com/opencosmos-ai/taoteching)
(道德經). **Next:** the [I Ching](https://github.com/opencosmos-ai/iching) (易經).

## How it stays true

The atlas has **no content of its own**. Each translation repository publishes
one file, its export, and the atlas is built from those files alone:

```
taoteching/data/atlas-export.json ─┐
iching/…/atlas-export.json ────────┼─▶ atlas/build.py ─▶ site/ ─▶ GitHub Pages
(any future text) ─────────────────┘
```

The export carries every character, every line, and every glossary entry
verbatim: frontmatter and body. **To change what the atlas says, edit the
glossary entry in the translation's repository and merge.** That repository's
CI refuses a stale export, and a merge to its `main` signals this one to
rebuild (`repository_dispatch`, with an hourly rebuild as a fallback).

| File | What it is |
|---|---|
| `texts.json` | the translations this atlas reads, and the site's address |
| `atlas/build.py` | fetch every export, merge by character, write every page |
| `atlas/md.py` | the Markdown the glossary entries use, and nothing more |
| `atlas/assets/` | the stylesheet, the script, and the rare-character font |
| `atlas/fonts.py` | cuts that font to exactly the characters the site shows |
| `tests/` | every page exists, every internal link resolves, no Markdown leaks |

## Adding a text

1. In the translation's repository, write an exporter that produces the same
   shape as `taoteching/tools/export_atlas.py` (contract 1), commit the file,
   and gate it in CI.
2. Add the text to `texts.json`.
3. Add a step to that repository's CI that sends `text-updated` here (see
   `taoteching/.github/workflows/notify-atlas.yml`).

## Running it

```bash
python3 -m atlas.build --base /           # sibling checkouts if present, else GitHub
python3 -m http.server -d site 8000       # then open http://localhost:8000
python3 -m unittest discover -s tests -t .
```

Standard library only. Python 3.9 or later.

## Typography

Chinese is set in a Song (Ming) face: **Songti** where the reader's device has
it, **Noto Serif TC** everywhere else, and **HanaMin** (花園明朝, GlyphWiki
Project, Hanazono Font License) for the rare characters neither carries:
CJK Extension A and B, which is where 說文's older forms and components live.
Every text colour meets WCAG AA (4.5:1) on the surface it sits on, in both
themes.

## Deferred

**說文解字's definitions are hidden from the card** (2026-10-14, Shalom's call).
Each character's 說文 line is Xu Shen's definition, c. 100 CE. It was shown in
Chinese, with English only where a glossary entry had translated it by hand:
three of 798. For a reader who does not read Chinese, the box was noise in the
most prominent place on the card. The block is commented out in
`atlas/assets/atlas.js`; the data still ships, so restoring it is uncommenting.

**Before it returns it must be accessible to English-only readers**, for
example: the structural half rendered in English from the parse the atlas
already has ("from 彳, with 巠 for sound"), and the definitions translated, by
hand or by glossary entries. The *Built from* tiles, which come from the same
analysis, stay. **Revisit by 2026-12-14** —
`.github/workflows/revisit-shuowen.yml` opens an issue that day.

## Licence

The atlas's code is MIT (`LICENSE`). The content it publishes comes from the
translation repositories and is dedicated to the public domain under CC0. The
rare-character font is HanaMin, under the Hanazono Font License
(`atlas/assets/fonts/LICENSE-hanazono.txt`).
