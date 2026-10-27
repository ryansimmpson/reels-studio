---
name: reels-studio
description: Turn any creator's long-form talking-head video (YouTube, podcast clip, course lesson, phone video) into polished 9:16 Instagram Reels, TikToks and YouTube Shorts, in any niche and any brand. Finds the strongest 25-60 s moments in the transcript, cuts them tight without clipping a word, and builds an animated HyperFrames composition. That composition has split-screen morphs between the full-frame speaker and a graphics slot, word-timed captions (soft, bold or karaoke box), animated figures (real logos, counters, checklists, app windows, tables, notifications, screenshots), punch-ins and sound effects, then runs a QA pass before delivery. Colours, fonts and caption style come from a brand file, with presets (studio, bold, minimal, warm, neon) or the creator's own. Use when someone asks for reels, shorts, TikToks, clips or "short form" from a video, wants clips in their brand, or wants to restyle an existing reel. macOS 26+.
---

# Reels Studio

A long-form video goes in. 3-5 vertical reels come out, each built from one moment, in the creator's brand.

The short-form grammar:
- a split-screen layout that morphs with the full-frame speaker;
- frame 0 already packed with a hook;
- captions always on;
- every spoken number gets a counter;
- real logos for every tool or product named;
- reaction GIFs on the jokes;
- a QA pass that re-transcribes the reel before it ships.

Read `reference/style.md` before designing.

**Workspace:** `~/reels-studio` (or `$REELS_HOME`):
- `projects/<video>/`: one work dir per long-form video. Reels live in `reels/<nn-slug>/`.
- `_graphics/`: HyperFrames, plus ffmpeg and ffprobe in `bin/`. Reel compositions go in `_graphics/<video>-reels/<nn-slug>/`, and shared logos and GIFs in `_graphics/_library/`.
- `_sound/sfx/`: the sound-effects library.
- `tools/`: the compiled tools (`audio`, `stt2`, `render_reel`, `vgrid`, `ocr`, `hf`).
- `out/<video>/`: delivery.
- `notes.md`: the creator's profile and their notes from past rounds (see "Working with the creator").

**First time on a machine:** `bash ~/.claude/skills/reels-studio/scripts/setup.sh`. It needs the Xcode command line tools, Node 18+ and Python 3. Transcription runs on device, which needs macOS 26 or newer.

## The look in one screen

1. **Two layouts, morphing.**
   - **full**: the speaker fills the 9:16 frame, face-anchored. Use it for the hook line, emotional lines and the payoff. On this shot it's captions and subtle camera motion only.
   - **split**: the speaker sits in a rounded band at the bottom, under an accent line. A graphics slot above sits on a frosted, darkened copy of their own footage.
   - Switch every 6-10 s. The morph is 0.62 s and eased, with a soft whoosh.
2. **Frame 0 is packed, and always has a hook.** The hook title and a first figure are on screen at the first frame. If no line the speaker says is a strong enough opener, write a text hook they never said (≤ 8 words, from the reel's own payoff), cold-open on the payoff figure for 1.5-2.5 s, or both (`reference/moments.md`).
3. **Show, don't type.** Every point gets a figure of the thing itself: notification banners for "my phone never stops", a checklist for steps, an odometer for every number, a live table for orders.
   - **Real logos** whenever the speaker names a tool, site or product, and for the best-known examples of a category they describe.
4. **Reaction GIFs** on punchlines and pain lines, 1-3 per reel, via the Giphy API (needs the user's free key).
5. **Captions always on**, styled by the brand:
   - `soft`: words rise out of a blur, keywords in the accent font;
   - `bold`: big caps that pop;
   - `box`: karaoke, the spoken word on an accent box.
6. **Camera:**
   - punch in or out at every jump cut;
   - a slow push-in on the payoff;
   - at most one shake and one light hit per reel, on the graphics layer, never on the speaker.
7. **Full-screen scenes** (`scripts/scenes.py`): 2-3 times in a longer reel, take the whole frame to explain a process with shapes, logos and text while the voice carries on.
8. **Screens:** when the speaker names a site, an article or one of their own screens, capture it and show it with zooms, highlights, circles and focus blur (`reference/screens.md`).
9. **Sound:** quiet UI effects (pops, dings, ticks, whooshes) from the sound library, or built-in synth sounds until it's filled. Music only when asked. Final mix at -14 LUFS (`reference/sound.md`).
10. **Brand:** colours, fonts and caption style come from a brand file. Five presets ship in `brands/`; make one per creator with `reference/brand.md`.

## Pipeline

Commands and gotchas are in `reference/pipeline.md`; components are in `reference/components.md`.

1. **Ingest.** `scripts/ingest.py <video> <work>` reads any source (camera or phone, any aspect or frame rate) and finds the mic channel. It writes `source.json`, `audio.wav`, `env.txt` and the word timestamps (`words.jsonl`). Pass `--lang` for a language other than US English.
2. **Brand.** Pick a preset or write `<work>/brand.json` from the creator's colours and fonts (`reference/brand.md`). Ask if you don't know their brand. Don't guess a palette for a real business.
3. **Find moments.** `scripts/moments.py "$WORK"` writes `reels/moments.md`.
   - Read every sentence, then pick 3-5 moments using `reference/moments.md`.
   - **Show the user the shortlist** before cutting: hook line, payoff line, length, why it works, plus 2-3 text/visual hook options.
4. **Cut.**
   - Write `reels/<nn-slug>/keep.json` as word ranges. Cut hard: open on the strongest short line, reorder, drop generic lines and fillers.
   - `scripts/reel_cut.py "$WORK" "$RD"` must print `validation problems: 0`.
   - Pin any flagged cut by hand after looking at the envelope. Never ship a clipped ending.
5. **Design.** Copy `scripts/reel_template.py` to `$RD/reel.py`, then:
   - Set the brand, the keywords and the face anchor.
   - Declare the layouts first.
   - Anchor every beat with `r.at("spoken words")`. It warns when a phrase repeats; pass `after=`.
   - Run it. It writes `$RD/plan.json` (SFX), `$RD/snaps.txt` and the composition's `index.html`.
6. **Base footage.** `tools/render_reel SRC $RD/edl.json $P/base.mp4 $RD` renders the cut and `$RD/edit_audio.wav` (voice plus effects, at -14 LUFS).
   - After SFX-only changes, rerun with `audio` as the last argument. That's seconds, not a full render.
7. **Check.**
   - HyperFrames `snapshot` at `snaps.txt`, then `tools/vgrid` makes a 9:16 contact sheet with the safe zones in red. Look at every tile.
   - Nothing covers the face or sits in the safe zones, no overlaps, captions clear of figures, logos correct, text big enough for a phone.
   - Pre-QA the audio before the slow render (`reference/pipeline.md`). Fix every leak or clipped word first.
8. **Render.** HyperFrames `render` (1080x1920, 29.97 fps). About 4 minutes for 45 s.
9. **Finish.** `scripts/finish.sh` muxes the render with `edit_audio.wav` and runs `scripts/qa.py`: resolution, fps, loudness, and a re-transcription that FAILs on a clipped or leaked word at a cut. It delivers only on a pass.
10. **Deliver.**
    - Files: `$REELS_HOME/out/<video>/<nn> - <title>.mp4`, plus `<nn> - <title> - caption.txt`.
    - The caption file holds the hook as the first line of the post caption, 2-3 plain sentences, 3-5 hashtags, and a cover-frame time.
    - Write like a person: no hype words, no "here's the thing", no em dashes, no stacked emoji.

## Styles

A style is a `Reel` subclass that changes the layout hooks in `reelkit.py` (`band`, `cap_y`, `zones`, `cap_rule`, `css`, `head`, `under`, `over`, `cap_mute`, `cap_classes`; see `reference/components.md`). A circle picture-in-picture, a text-card style or a diagram style are each one small subclass. Colours and fonts stay in the brand, so any style works with any brand.

## Working with the creator

- **Keep a profile** in `$REELS_HOME/notes.md`: who they are, their niche and audience, the brand file, words to spell right (`r.spell`), and every note they've given, as "their words → the rule that came out of it". Read it before every edit, and let it override the defaults in `reference/style.md`. It lives in the workspace, never in this skill.
- **Render one reel first** and wait for notes before batching the rest. Notes often arrive as long voice-note style messages. Pull out every concrete note and confirm each one is fixed.
- **Ask before** downloads (GIFs, footage, sounds, fonts outside Google Fonts) and before any paid generation. Logos of tools the speaker names come from Simple Icons via `fetch_logo.py`; check each one looks right.
- **Keys** (GIPHY_API_KEY) are the user's to add, in `~/.config/reels-studio.env`. Never ask for a key in chat.
- **Privacy:** nothing private on screen (emails, phone numbers, customer names, addresses, revenue, keys) unless the creator says it's fine.
- **Truth:** captions say what was said, and on-screen claims never go beyond the speaker's words.
