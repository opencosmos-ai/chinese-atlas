# Open Classical Chinese Character Atlas & Glossary

**Live at [chinese-atlas.opencosmos.ai](https://chinese-atlas.opencosmos.ai/)**, with the glossary at [/glossary/](https://chinese-atlas.opencosmos.ai/glossary/). Part of [OpenCosmos](https://opencosmos.ai/).

Every character in the classical Chinese texts OpenCosmos translates, taken
apart: the pieces it is built from and what each piece means, its analysis in
說文解字 (*Shuōwén Jiězì*, c. 100 CE), every line it stands in, and how each
translation renders it. Every glossary entry, in full, with the character beside
it.

**Now holding:** the [Open Tao Te Ching](https://github.com/opencosmos-ai/taoteching)
(道德經), announced on 2026-10-17 in
[*Welcome to the Open Tao Te Ching*](https://shalomormsby.substack.com/p/welcome-to-the-open-tao-te-ching). **Next:** the [I Ching](https://github.com/opencosmos-ai/iching) (易經).

## Two rooms

- **The atlas** (`/`, and `/常/` for each character) is about **characters**:
  what each is built from, where it occurs, and how each translation renders
  it. Descriptive, from data, and mostly shared across texts. Tabs scope it to
  one text or all of them.
- **The glossary** (`/glossary/`, entries at `/glossary/<text>/<entry>/`) is
  about **decisions**: why a translation renders a term the way it does. Each
  entry is one translator's ruling for one text, so entries stay labelled with
  their translation, and the same character can carry a different ruling in
  each. One index serves every text, scoped by the same tabs; search reaches
  the words each ruling sets aside, so "eternal" finds 常.

## For agents, crawlers and screen readers

Both rooms are drawn by `atlas.js`, and a reader that runs no script still
gets the substance. Every character page carries its renderings, its glossary
links, where it occurs, its parts and its 說文 line as plain HTML, which the
script replaces on load. The glossary index lists every entry the same way, and
entry pages are static throughout.

- **`/llms.txt`**: what the site is, the data files and their fields, every
  entry with a link to its Markdown source, and how to suggest a change.
- **`/sitemap.xml`** and **`/robots.txt`**: every page.
- **`/assets/data.json`** and **`/assets/glossary.json`**: everything the
  pages are drawn from. They also work without the `?v=` the pages add.
- **Entry pages** carry a schema.org `DefinedTerm` and a
  `<link rel="alternate" type="text/markdown">` to the entry's source file.
- **Every Han character is marked `lang="zh-Hant"`**, so a screen reader
  voices it as Chinese rather than spelling a code point. `tests/test_build.py`
  fails on any unmarked `zh`, `big` or `pg` element, and on any page without
  exactly one `<main>`.

## How it stays true

The atlas has **no content of its own**. Each translation repository publishes
one file, its export, and the atlas is built from those files alone:

```
taoteching/data/atlas-export.json ─┐
iching/…/atlas-export.json ────────┼─▶ atlas/build.py ─▶ site/ ─▶ GitHub Pages
(any future text) ─────────────────┘
```

The export carries every character, every line, and every glossary entry
verbatim: frontmatter and body. **To change what the atlas says, change the
file that owns it in the translation's repository, rebuild that repository's
export, and merge.** Most of a card's English is not a glossary entry. For the
Tao Te Ching, the English under most characters comes from the hand-kept lists
`sources/word-glosses.yaml` and `sources/grammar-glosses.yaml`. The meanings of
the *Built from* parts come from `sources/component-glosses.yaml`, and only a
character with a glossary entry takes its English from `glossary/`.
[`process/skills/suggest-edit/SKILL.md`](https://github.com/opencosmos-ai/taoteching/blob/main/process/skills/suggest-edit/SKILL.md)
routes each part of a card to its file, says which are pull requests and which
need an issue first, and gives the rebuild. That repository's CI refuses a PR
whose export is stale, and a merge to its `main` signals this one to rebuild
(`repository_dispatch`, with an hourly rebuild as a fallback).

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
