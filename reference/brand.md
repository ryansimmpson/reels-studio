# Brands: colours, fonts and captions

Every reel is built with colour and font tokens, and the brand fills them in. Switching a reel from one look to another is one argument: `Reel(RD, P, brand="bold")`. Nothing in the figure code changes.

## Pick a brand

| Preset | Look | Captions | Good for |
|---|---|---|---|
| `studio` (default) | electric blue on dark footage, Inter + Instrument Serif italic accent | soft: each word rises out of a blur, keywords in the serif | business, tech, education, most talking heads |
| `bold` | yellow on black, Poppins everywhere | bold: big caps, every word pops in | hype, motivation, finance, sports |
| `minimal` | teal, DM Sans + Fraunces italic accent | soft, lighter weight | design, wellness, lifestyle, calm explainers |
| `warm` | coral, Plus Jakarta Sans + Playfair Display italic accent | box: the spoken word sits on a coral box | food, beauty, family, friendly how-tos |
| `neon` | acid lime, Space Grotesk + Space Mono | box | gaming, tech, crypto, dev content |

Which brand a reel uses, in order:
1. `Reel(..., brand="name" or "/path/to/brand.json")`;
2. the `REELS_BRAND` environment variable;
3. `<work>/brand.json`, so a creator's brand travels with their project;
4. `studio`.

## Make one for a creator

Ask for their brand colours (hex), fonts, and two or three reels or posts they like. Then write `<work>/brand.json`, or a file in `brands/` if they'll use it across videos. Only list what differs. `"extends"` starts from a preset:

```json
{
  "name": "Acme Fitness",
  "extends": "bold",
  "colors": {"accent": "#FF3B6B", "accent_text": "#FF7A97", "accent_light": "#FFC2D0", "on_accent": "#1A0008"},
  "fonts": {"sans": "Archivo", "sans_weights": [500, 600, 700, 800, 900]},
  "captions": {"style": "bold", "size": 68}
}
```

### Fields
| Field | What it colours or sets | Rule of thumb |
|---|---|---|
| `colors.accent` | icon chips, check marks, chart areas, screen circles and boxes | the brand colour itself |
| `colors.accent_text` | accent words in titles, caption keywords, numbers, chart lines | a lighter tint of the accent, readable on dark footage |
| `colors.accent_light` | glows, data packets, status pills | a pale tint |
| `colors.on_accent` | icons drawn on an accent fill, the spoken word in "box" captions | near-black for light accents, near-white for dark ones |
| `colors.success` | live dots, "ok" lines | a green that sits next to the accent |
| `colors.marker` | the highlighter on screenshots | the accent text colour usually works |
| `fonts.sans`, `sans_weights` | labels, titles, captions | a Google Fonts family; ask only for weights it has (some stop at 700) |
| `fonts.accent`, `accent_italic`, `accent_weight` | the one accent phrase in a hook or title, soft-caption keywords | a serif italic for an editorial look, or the sans at a heavy weight |
| `fonts.accent_scale` | accent size against the sans | 1.3–1.42 for a serif (smaller x-height), 1.0–1.1 for a sans |
| `fonts.mono`, `mono_weights` | code windows, URLs | |
| `captions.style` | `soft`, `bold` or `box` | match the creator's energy |
| `captions.size`, `weight`, `upper` | caption type | 62–70 px; 600 soft, 700–800 bold and box |

### Checks before using a new brand
- **Fonts load:** the build writes a Google Fonts link. A weight the family doesn't have makes Google reject the whole request, and every font falls back. Check with:
  ```bash
  python3 -c "import sys; sys.path.insert(0, '$K'); import brand, re; print(re.search(r'href=\"(https://fonts[^\"]+)', brand.font_link(brand.load('<name or path>'))).group(1))" | xargs curl -s -o /dev/null -w "%{http_code}\n"
  ```
  It must print 200.
- **Contrast on footage:** `accent_text` sits on the speaker's footage and on dark glass. Very dark accents (navy, maroon) disappear; use a lighter tint for `accent_text` and keep the dark shade for `accent`.
- **One accent colour.** Two competing accent colours read as noise in a 9:16 frame.
- **The creator's own logo** isn't part of the brand: on the speaker's shot it's captions only. Put a logo in the library (`$REELS_GFX/_library/logos/<name>.svg`) and use `r.logos()` or `r.mark()` where it belongs in the story.

## Writing figures that follow the brand
In `raw()` HTML, scenes and new components, write tokens instead of colours and font names:
- colours: `__ACC__`, `__ACC2__` (accent text), `__ACCL__` (light), `__ONACC__`, `__OK__`;
- the same as `r,g,b` for transparency: `rgba(__ACCRGB__,.4)`, `rgba(__ACC2RGB__,.6)`, `rgba(__ACCLRGB__,.3)`;
- fonts: `"__SANS__"`, `"__SERIF__"` (the accent font), `"__MONO__"`.

`build()` swaps them for the brand's values.
