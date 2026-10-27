# reelkit components

`r = Reel(reel_dir, project_dir, brand=None, keywords=[...], band_zoom=1.6, face=(0.51, 0.40), sfx_boost=0, aspect=None)`

- `brand`: a preset (studio, bold, minimal, warm, neon), a path to a brand .json, or None ($REELS_BRAND, then `<work>/brand.json`, then studio). See `brand.md`.
- `face`: where the face sits in the source frame, as fractions (x across, y down). Measure it on a frame.
- `aspect`: read from `<work>/source.json`; any source shape works (16:9, 9:16 phone footage, square).

All times are reel seconds; get them from `r.at("spoken phrase", after=0, end=False)`. Most components take `t0`, `t1` (exit; None = stays to the end), and placement: `zone=` ("slot" in split, "top" in full, "low"), or `x=`/`y=` for the centre, plus `scale=` where offered. Every component adds its SFX unless `sfx=False`.

| Call | Shows | Good for |
|---|---|---|
| `layout(t, "full"/"split")` | morph between the speaker full-frame and the split band | every 6-10 s |
| `auto_punch(0.12)`, `zoom(t, s, dur, x)`, `push(t)` | camera on the speaker | jump cuts, the payoff |
| `shake(t, amp)`, `flash(t)` | impact on the graphics layer, soft light hit | the one dramatic beat |
| `hook(text, accent, until, y)` | frame-0 title, already visible on the first frame | always |
| `title(text, accent, t0, t1)` | a line in the brand's sans plus an accent phrase in its accent font | section labels, the point |
| `notifs([(icon or logo, title, text, t)], t1)` | iOS banners dropping into a stack (t ≤ 0 = on screen at frame 0) | missed calls, leads coming in, DMs, emails, "your phone all day" |
| `logos(names, times, labels=)` | real logos on white app tiles, each landing on its word | "we use X, Y and Z" |
| `conveyor(names, t0, t1, y)` | a topic lane: the story's tools drifting sideways | atmosphere under a title, the stack |
| `hub(center, [(logo, label, t)], t0, t1)` | a system wired to tools: spokes draw, nodes connect on their word, packets flow | integrations, agents, MCP, "we connected everything" |
| `counter(to, t0, land, t1, frm=, prefix=, suffix=, label=)` | odometer: tabular digits roll with carry and motion blur, land with a ding | every spoken number: money, followers, hours, percent, reps |
| `window(t0, t1, kind="claude"/"terminal"/"browser", prompt=, lines=, line_times=)` | app window: the prompt types, lines land (kind claude shows a spinning Claude mark) | AI prompts, code, "I typed this into..." |
| `checklist([(text, t)], t0, t1, title=)` | a list that ticks itself off on each word | steps, "it handles A, B and C" |
| `rows(title, cols, [(cells, status, t)], t0, t1)` | live table with status pills | orders, leads, a schedule, a comparison |
| `chart(t0, t1, label, kind="line"/"bars", values=)` | a line drawing upward with a live dot, or ranked bars | growth, comparisons |
| `image(path, t0, t1, w, h, caption, video=)` | screenshot, photo, or an mp4 (GIF) in a glass frame with Ken Burns | a product shot, a before/after, a real screen |
| `gif(slug or path, t0, t1, style="card"/"cut", w=, tilt=, caption=)` | reaction GIF from `$REELS_GFX/_library/gifs/<slug>.mp4`: a tilted glass sticker in the slot, or a full-screen cutaway band over a blurred copy. Clamped to the clip's length. | punchlines, pain lines, flexes (see style.md "Reaction GIFs") |
| `mark(t0, t1, name="claude")` | a brand mark that lands, spins and settles (any library logo) | bringing a logo to life |
| `raw(html, js)` | escape hatch for a bespoke figure | anything the library lacks; add it to reelkit after |
| `Scenes(r).takeover(t0, t1)` (`scenes.py`) | full-screen explainer: a frosted dark panel over the speaker, the voice continues, captions on top. Build the inside with `r.raw` plus `row()`, `head()`, `show()` | the technical stretch, a busy process, "X and Y" where both need room |
| `spell("cap cut", "CapCut")` | fixes a recognizer spelling in the captions only (multi-word too); timing, `r.at()` and QA keep the words as heard | product names, brands, the creator's name |
| `r.captions_on = False` | turn captions off | never for a reel, unless the creator asks |

**Icons for `notifs`:** mail, phone, missed, chat, user, users, cal, doc, chart, trend, check, bolt, clock, money, spark, cloud, code, search, lock, cart, home, db, mic. Anything else is treated as a logo name.

**Logos:** they resolve from `$P/assets/logos`, then `$REELS_GFX/_library/logos`. Aliases: sheets, drive, docs, workspace, ads, gemini. One-colour Simple Icons SVGs get their brand colour from `BRAND_HEX`. For a missing logo, run `fetch_logo.py <slug>` and check the result looks right. Use real logos for every tool, site or product the speaker names, and for the best-known examples of a category they describe ("video editors": Premiere Pro, DaVinci Resolve, CapCut). If Simple Icons has no mark (some brands were removed there), the script falls back to the site's favicon; if that is low-res or wrong, find the official press-kit mark and ask the user before downloading it.

**New figure:** build it with `raw()` in the same language (glass card or no container, one accent colour, a living detail, a sans label). Use the brand tokens in its HTML and CSS (`__ACC__`, `__ACC2__`, `rgba(__ACCRGB__,.4)`, `"__SANS__"`), so it follows the brand. Once the creator likes it, promote it into reelkit as a method with its own SFX, and list it here.

## Screens (screenshots and screen recordings)

`sc = r.screen(src, t0, t1=None, w=1000, h=620, frame="browser", url="", zone=None, tilt=(6, -12, -1.5), fit="width", data=None, enter="tilt", dark=False)` returns a `Screen`. Then chain the calls:
- `sc.zoom(t, find="...", flat=True)`, `sc.highlight(t, find="...", until=)`, `sc.circle()`, `sc.arrow()`, `sc.box()`;
- `sc.focus()` / `sc.unfocus()`, `sc.popout()`, `sc.scroll()`, `sc.edges()`, `sc.reset()`, `sc.tilt_to()`.

Captures come from `capture.mjs` (web) or `ocr` (the creator's own screenshots and recordings), which write the `find=` data. Full guide: `screens.md`.

## Style hooks (for a new style skill)

A style is a `Reel` subclass that changes these in `__init__`; leave them alone for the default look. Colours and fonts belong in a brand file, not a style.
- `self.band`: where the speaker sits in "split" (x, y, w, h, radius). A radius of w/2 makes a circle PiP.
- `self.morph`: the length of the full/split morph.
- `self.cap_y`: caption centre line per layout.
- `self.zones`: figure zones. Add your own, e.g. "stage" or "above".
- `self.cap_rule`: caption chunking (words, chars, gap, `cuts=True` breaks at jump cuts, `start` delays the first chunk).
- `self.css`, `self.head`: extra CSS and <head> tags (fonts).
- `self.under`, `self.over`: HTML layers behind the speaker (backgrounds) and above the graphics (bars, grain).
- `self.cap_mute`: (t0, t1) windows with no captions.
- `self.cap_classes`: (t0, t1, "css classes") windows where captions get extra classes, e.g. dark ink over a light full-screen card. Caption lines break at each window's edges, so no line spans two looks.

Rule for every kit: never schedule a tween before t = 0. GSAP shifts the whole timeline to fit it, and frame 0 comes up empty. Show frame-0 pieces with a `fromTo` at 0.
