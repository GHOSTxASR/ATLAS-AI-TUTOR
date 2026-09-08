# Bundled fonts

Atlas ships these two families rather than loading them from Google Fonts, so
that running the app makes no request to a third party. Both are licensed
under the SIL Open Font License 1.1, which permits bundling and redistribution
provided the licence travels with the files — which is what the `OFL-*.txt`
files beside this one are for.

| Family | Copyright | Source | Licence |
| --- | --- | --- | --- |
| Geist | 2024 The Geist Project Authors | <https://github.com/vercel/geist-font> | [OFL-1.1](OFL-Geist.txt) |
| Instrument Serif | 2022 The Instrument Serif Project Authors | <https://github.com/Instrument/instrument-serif> | [OFL-1.1](OFL-InstrumentSerif.txt) |

The `.woff2` files were taken from the Google Fonts CDN, which is the same
build the app previously fetched at runtime, so the rendering is unchanged.

## What is here

Geist is a **variable** font: one file per subset covers the whole 300–700
weight range, which is why there are five Geist files rather than
five-weights × five-subsets. Instrument Serif is used at a single weight in
upright and italic.

| | latin | latin-ext | vietnamese | cyrillic | cyrillic-ext |
| --- | --- | --- | --- | --- | --- |
| Geist (300–700) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Instrument Serif (400) | ✅ | ✅ | — | — | — |
| Instrument Serif italic (400) | ✅ | ✅ | — | — | — |

Nine files, 140 KB total. Every subset is included because the whole set costs
less than a single screenshot in this repository — text in any of these
scripts renders in the intended font rather than a fallback. Instrument Serif
simply has no Cyrillic or Vietnamese coverage upstream; text in those scripts
falls back to a system serif, which only affects the display headings.

The `unicode-range` declarations in `src/styles/fonts.css` are Google's, so a
browser still downloads only the subsets a given page actually needs.

## Updating them

Fetch the CSS with a modern browser User-Agent (Google serves `woff2` only
when it believes the client supports it), then download each `url(...)` it
names:

```
https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap
```

Keep the `unicode-range` values from that CSS in step with the files, or
browsers will download subsets they cannot use and skip ones they need.
