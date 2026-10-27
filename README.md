# reels-studio

A Claude Code skill that turns long-form talking-head videos into 9:16 Reels, TikToks and Shorts, for any creator, niche and brand.

Point it at a video and it:
- finds the best moments;
- cuts them tight without clipping a word;
- adds word-timed captions, animated figures (real logos, counters, checklists, app windows, tables, screenshots), camera punch-ins and sound effects;
- renders 1080x1920;
- re-transcribes the result to check that nothing was clipped.

## Requirements
- macOS 26 or newer (on-device transcription with Apple's SpeechAnalyzer; AVFoundation for audio and video)
- Xcode command line tools (`xcode-select --install`)
- Node 18+ and Python 3

## Install
```bash
git clone <this repo> ~/.claude/skills/reels-studio
bash ~/.claude/skills/reels-studio/scripts/setup.sh
```
`setup.sh` creates `~/reels-studio` (override with `REELS_HOME`), installs HyperFrames and ffmpeg there, and builds the Swift tools.

Then ask Claude Code: "make reels from ~/Movies/my-video.mp4". It reads `SKILL.md` and runs the pipeline.

## Brands
Colours, fonts and caption style live in a brand file. Five presets ship in `brands/`: `studio` (default), `bold`, `minimal`, `warm` and `neon`. Write your own in a few lines (`reference/brand.md`):
```json
{"name": "My Brand", "extends": "studio", "colors": {"accent": "#FF3B6B", "accent_text": "#FF7A97"}, "captions": {"style": "box"}}
```

## Layout
- `SKILL.md`: when to use it and the pipeline.
- `reference/`:
  - `pipeline.md`: commands and gotchas
  - `style.md`: layouts, safe zones, type, motion
  - `components.md`: the figure library
  - `brand.md`: brands and presets
  - `moments.md`: picking moments
  - `screens.md`: screenshots and recordings
  - `sound.md`: effects and music
- `brands/`: the brand presets.
- `scripts/`:
  - `setup.sh`: one-time install
  - `ingest.py`: probe a source, pick the mic channel, transcribe
  - `moments.py`: candidate finder
  - `reel_cut.py`: envelope-snapped cut list with a validator
  - `reelkit.py`, `brand.py`, `scenes.py`, `screenkit.*`: the composition builder
  - `reel_template.py`: an example reel script
  - `render_reel.swift`: the cut, the voice mix and the SFX bus
  - `qa.py`, `finish.sh`: QA and delivery
  - `fetch_logo.py`, `fetch_gif.py`, `capture.mjs`, `ocr.swift`, `music.py`, `vgrid.swift`: logos, reaction GIFs, web captures, OCR, music bed, contact sheets

## Credits
The short-form grammar (split layout, packed first frame, counters for numbers, logo lanes, reaction GIFs, a QA pass) builds on ideas from [open-edits](https://github.com/kevinbadi/open-edits) (MIT). Logos come from [Simple Icons](https://simpleicons.org) (CC0). Rendering is [HyperFrames](https://hyperframes.dev) with GSAP.
