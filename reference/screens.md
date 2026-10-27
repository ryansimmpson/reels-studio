# Screens: screenshots and screen recordings

When the speaker names a website, an article, a product page or something on their own screen, show the real thing: a screenshot or screen recording in 3D, zoomed in, with passages highlighted, things circled and the rest blurred to draw focus.

Toolkit files:
- `capture.mjs`: web pages.
- `ocr.swift` (built as `$REELS_HOME/tools/ocr`): the creator's own screenshots and recordings.
- `screenkit.py`, `screenkit.js` and `screenkit.css`: the figure. Annotations use the brand's accent colours.

## 1. Get the capture

**A public web page:**
```bash
node "$K/capture.mjs" "<url>" "$WORK/screens/<name>.png" --full --find "the headline" --find "the passage they read" [--select "css"] [--w 1440 --h 900 --dpr 2] [--dark] [--clip "article"]
```
- **Output:** the PNG plus `<name>.json`. That JSON holds each phrase's boxes (one per line of text) and each selector's box. A page takes about 7 s.
- **What it uses:** the Chrome HyperFrames installed.
- **Cookie and consent banners** are hidden with CSS, never clicked.
- **Size:** `--full` takes the whole page up to 9000 CSS px, for scrolling. Leave it off for an above-the-fold shot. `--clip` takes one element.
- **Toggles and tabs:** `--click "Monthly"` presses a button, tab or switch by its visible text before the shot (pricing pages default to yearly). It never touches links, inputs or forms.
- **Public pages only.** Never type a password or log in. For anything behind a login, ask the creator for their own screenshot or recording.

**The creator's own screenshot or screen recording** (saved into `$WORK/screens/`):
```bash
"$T/ocr" "$WORK/screens/dashboard.mov" "$WORK/screens/dashboard.json" --at 12.5 --find "phrase" --find "another phrase"
```
- **How it reads:** on-device text recognition (Apple Vision), about 30 s for a 4K image. Phrases match along paragraphs, so two columns don't interleave, and across hyphenated line wraps.
- **Recordings:** OCR the frame where the beat happens (`--at` seconds into the recording). The boxes hold while that part of the screen stays still.
- **Pairing:** keep the JSON beside the image or video with the same stem, and `Screen()` picks it up. `find=` then works the same on either kind of capture.

## 2. The figure

```python
sc = r.screen(src, t0, t1, w=1000, h=620, frame="browser", url="example.com/article")   # returns a Screen
```

- **`frame`:**
  - `browser`: traffic lights and a URL pill;
  - `window`: a title bar, for apps;
  - `phone`: a bezel and notch, for mobile captures;
  - `none`.
- **`fit`:**
  - `width`: the default, and the page scrolls;
  - `contain`: the whole capture fits;
  - `height`.
- **`dark=True`:** for dark UIs. The marker switches to a screen blend.
- **Screen recordings:** pass the .mov or .mp4 as `src`. It plays in sync, and every effect works except `popout`, which falls back to `focus`.

Regions are `find="phrase"` (with `nth=` for a repeat), `select="css"`, or `rect=[x, y, w, h]` in source pixels. Calls can be written in any order; they run in time order.

| Call | What it does | Sound (library kind) |
|---|---|---|
| `enter(t, "tilt" \| "rise" \| "snap" \| "zoom")` | Arrives in 3D. `snap` flashes like a screenshot being taken. | whoosh, or shutter for snap |
| `float(t0, t1)` | Gentle hover while it's idle | none |
| `zoom(t, find=..., flat=True)` | Eased camera into a region. `flat=True` levels the 3D tilt for reading. `pad` sets the margin (lower is closer). | swish |
| `reset(t)`, `tilt_to(t, pose)`, `flat(t)` | Back out to the whole page; change or level the 3D pose | none |
| `scroll(t, find=...)` or `scroll(t, y=...)` | Smooth scroll so the region sits a fifth of the way down | none |
| `highlight(t, find=..., until=)` | A marker (the brand's marker colour) sweeping each line of a passage | marker |
| `underline(t, ...)` | Hand-drawn underline | marker |
| `circle(t, ...)` | Hand-drawn circle, slightly wobbly, overshooting where it started | scribble |
| `box(t, ...)` | Rounded box drawn around a panel or section | scribble |
| `arrow(t, ..., frm="left\|right\|top\|bottom")` | Curved hand-drawn arrow to a small target | scribble |
| `focus(t, ...)`, `unfocus(t)` | Everything outside the region blurs and dims, with a thin accent ring | swish |
| `edges(t, on=True)` | Soft blur and shade around the outer edges of the whole screen | none |
| `popout(t, ..., until=)` | The region (a headline, a price, a button) lifts off the page with a shadow while the rest dims | pop |
| `exit(t)` | Leaves | none |

## 3. Rules

- **Purpose:** a screen is a "show the real thing" moment. Use it when the speaker names a site, a headline, a stat in an article, or a screen of their own, not as decoration.
- **3D for entrances:** enter tilted, go flat (`flat=True`) on the first zoom that needs reading, and tilt back when zooming out. The 3D look is for arriving and overviews; reading is flat.
- **Pacing:** every camera move and annotation lands on the words the speaker says (`r.at`). Hold a zoom at least 1.5 s, and make at most one camera move per sentence.
- **Which annotation:**
  - marker: a passage the speaker reads aloud;
  - circle: one word, number or button;
  - arrow: a small UI target;
  - box: a panel;
  - focus: "look at this part";
  - popout: a headline or price.
- **Limits:** at most two annotations on screen at once, each with an `until`.
- **Readability:** text has to read without a caption. Zoom closer (lower `pad`) rather than adding words. At 1080p, aim for at least about 24 px on screen.
- **Privacy:** nothing private on screen unless the creator says it's fine. That covers email addresses, phone numbers, client or customer names, revenue, addresses and API keys. Crop, `focus()` away from them, or recapture.
- **Sounds:** `marker`, `scribble` and `shutter` are library kinds (see `sound.md`); built-in synth versions play until the library has files for them.

## 4. In a reel

- **Placement:** `sc = r.screen(src, t0, t1, w=1000, h=620)` places it in the split layout's graphics slot (zone `slot`, centre 540, 525). It enters on its own, and exits at `t1`; then chain the calls on `sc`.
- **Use the split layout** for screens. In the full layout, the only room is the top strip, which is too small to read.
- **Tilt:** smaller than on long-form (default `(6, -12, -1.5)`). Go flat before any reading.
- **Captures:** for portrait phone recordings use `frame="phone"`, `w=560, h=1000` in a full-height cutaway; for a web page use a 1080-wide viewport (`--w 1080`) so the text is bigger in the slot.
