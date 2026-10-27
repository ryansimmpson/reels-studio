# Reel style

Coordinates are CSS px on a 1080x1920 composition. The implementation is `scripts/reelkit.py`; colours and fonts come from the brand (`brand.md`). These rules are the defaults; a creator's own notes (kept in `$REELS_HOME/notes.md`, see SKILL.md) win over them.

## The rules that matter most
1. **Frame 0 is packed and hooks.** The first frame already has the hook title and a figure on it. A scroll-stop never sees a blank or half-built frame.
2. **Show, don't type.** Every point gets a figure of the thing itself: notification banners for "my phone never stops", real logos for the tools named, an odometer for every number, a checklist for steps.
3. **On the speaker's full-frame shot: captions and subtle camera motion only.** Titles, logos, counters and labels go in split or a full-screen scene. A crowded face shot reads as overstimulating.
4. **Never clip a word.** Every cut lands in silence. A clipped ending or a half-word fragment is the most noticeable mistake a reel can have; QA fails on it.
5. **Real logos** whenever the speaker names a tool, a site or a product, and for the best-known examples of a category they only describe ("editing apps": CapCut, Premiere Pro, DaVinci Resolve). Viewers recognise the tools they use.
6. **Cut hard.** Open on the strongest short line, even from the middle of the moment. Drop generic lines and fillers. The reel is one idea with a turn in it.

## Layouts

| Layout | Speaker | Graphics | Captions |
|---|---|---|---|
| full | fills 1080x1920, face-anchored crop of the source | none (the hook is the only exception) | centre y 1300, on the chest |
| split | band x 24, y 968, 1032x912, radius 44, 1.6x zoom (head and shoulders), 1.5 px light rim | zone `slot`: y 200-860, centre (540, 525), up to 1000 wide | centre y 900, just above the accent line at y 952 |
| scene (takeover) | hidden: a frosted dark panel covers the frame, the voice carries on | the whole frame: content in y 220-1220, 980 wide | centre y 1300 (run the layout underneath as `full`) |

- **Behind the slot:** the same footage, blurred 44 px and darkened, plus a faint accent glow from the top. It looks like glass over the room, not a flat wash.
- **When to use each:** the hook line, emotional lines and the payoff go full. Steps, systems, numbers and anything with a figure go split.
- **Scenes** (`scenes.py`): 2-3 per reel of 60 s or more, 7-12 s each, on the most technical stretch: how something works, a list that builds up, a process. Each scene builds piece by piece on the spoken words and ends before the speaker says the next thing to camera. Never on the hook or the payoff.
- **Morph:** 0.62 s, eased, with a whoosh. Switch every 6-10 s, a beat before the line that needs it.
- **Any source shape works.** A 16:9 camera gives the most room to reframe; 9:16 phone footage fills the full layout exactly, and the band crops it to head and shoulders.

## Safe zones (Instagram, TikTok, YouTube Shorts UI)
- **Top 200 px:** status bar, search, tabs. No text.
- **Bottom 380 px (y > 1540):** handle, caption, audio. No text or figures. In split the speaker's band runs into it, which is fine.
- **Right rail** (x > 950, y 900-1540): like, comment, share. No text there.
- `vgrid` draws all three in red on every contact sheet.

## Type and size (phone-first)

| Use | Size |
|---|---|
| Hook | sans 700, 74 px, accent at the brand's `accent_scale` |
| Titles | sans 600, 62 px, accent at the brand's `accent_scale` |
| Captions | the brand's caption size (62-70 px) |
| Labels | 32-38 px |
| Card body text | 33-42 px |
| Counter digits | 230-250 px |

- Nothing smaller than 28 px. If it would be, the figure is too dense: cut items.
- **Caption chunks:** 1-3 words, broken at punctuation and at pauses over 0.45 s. Keywords (the `keywords=` list) and numbers get the accent treatment of the caption style.
- **Caption styles** (set in the brand):
  - `soft`: each word is hidden until its onset, then rises out of a blur; keywords in the accent font. Calm, cinematic.
  - `bold`: caps, each word pops in with an overshoot; keywords in a heavier weight and the accent colour. Loud.
  - `box`: the whole line shows, and the word being spoken sits on an accent box (karaoke). Easy to follow with the sound off.
- No em or en dashes in on-screen text, no chrome gradients, no stamps.

## Motion
- **Entrances rotate** automatically (up, left, pop, right, drop), so no two pieces in a row enter the same way. Each starts 0.1 s before its word.
- **Exits:** fade up with a blur, 0.4 s, before the next big piece lands.
- **One idea in the slot at a time.** A title plus one figure is the normal stack; two big pieces at most.
- **Density:** something new every 2-4 s. Captions and the camera carry the full-frame stretches.
- **Living details** while on screen: data packets on a hub, typing, a live dot, a drifting logo lane. No idle pulsing on big pieces.
- **Camera:**
  - `auto_punch(0.12)` alternates 1.12 / 1.0 at every jump cut, to hide the jump.
  - `push()` 1.08-1.10 over 1.3-1.4 s on the payoff.
  - A sideways reframe (`zoom(x=)`) only in full, and only when a cutaway lands beside the speaker.
- **Shake and flash:** once per reel at most, on the result or the number, graphics layer only, never on the speaker.

## Reaction GIFs (memes)
A real reaction GIF on the joke lifts engagement more than a text pill. They come from Giphy (`fetch_gif.py`) and are placed with `r.gif()`.
- **Where they earn a spot:** a pain line, an exaggeration or flex, a self-own or aside, a rhetorical question.
- **Not on:** the hook frame, a counter while it rolls, a figure while it builds, the payoff line.
- **How many:** 1-3 per reel, each 1-2.5 s, never the same GIF twice in a video.
- **Styles:** `card` (a tilted glass sticker in the split slot; exit whatever was there first) or `cut` (a full-screen cutaway of 0.8-1.8 s in full layout; captions stay on top).
- **Picking:** search 2-3 phrasings and run `--sheet` for each. Look at the frames and choose by the face and the joke, not the title.
- **Reject:** burned-in text that says something different from the line, anything rated above pg-13, real people in a context that mocks them, competitors' mascots, slurs and gore.
- GIF audio is never used.

## Sound
- **Automatic per component:** pop on enter, ding when a logo lands or a counter settles, ticks while typing or counting, whoosh on each layout switch, impact on the flash. Quiet, under the voice.
- `sfx_boost=` lifts the whole bus for a creator who wants more punch.
- **Mix:** voice high-passed at 80 Hz, compressed, -14 LUFS, limited at -1.5 dBFS. No fade at the end: the reel loops.
- Files come from the sound library (`sound.md`); missing kinds use built-in synth sounds.

## Ending and loop
End on the payoff line, full-frame, pushed in. No outro card or "follow for more" unless the creator says it. The last frame should cut back to frame 0 cleanly.
