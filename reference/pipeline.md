# Pipeline: commands and gotchas

Timings are from an Apple Silicon Mac: a 30-minute 4K source, cut to a 45 s reel.

## 0. Setup (once per machine)

```bash
bash ~/.claude/skills/reels-studio/scripts/setup.sh
```
It makes the workspace (`~/reels-studio`, or `$REELS_HOME`), installs HyperFrames and ffmpeg into `_graphics`, and builds the Swift tools into `tools/`. An existing HyperFrames install can be reused with `REELS_GFX=/path/to/it`.

Shell variables used below:
```bash
K=~/.claude/skills/reels-studio/scripts
RH="${REELS_HOME:-$HOME/reels-studio}"; T="$RH/tools"; GFX="${REELS_GFX:-$RH/_graphics}"
V=my-video                                   # a short slug for the long-form video
WORK="$RH/projects/$V"
```

## 1. Ingest (once per video)

```bash
python3 "$K/ingest.py" "/path/to/video.mp4" "$WORK" [--mic auto|mix|left|right] [--lang en-US]
SRC=$(python3 -c "import json;print(json.load(open('$WORK/source.json'))['src'])")
```
- Writes `source.json`, `audio.wav`, `env.txt` and `words.jsonl`. About a minute of transcription per 10 minutes of video.
- **Any source:** 16:9 camera footage, 9:16 phone video, square, any frame rate. Phone footage with rotation metadata is converted once to an upright `source.mov`.
- **Mic channel:** `auto` measures both channels. A lav or shotgun on one channel of a camera (the other near-silent) picks that channel; otherwise it mixes. Force it with `--mic left|right|mix` if the voice sounds thin or roomy.
- **Language:** `--lang` sets transcription and QA. Captions are in that language; `moments.py` scoring is tuned for English, so for other languages read the sentence list and judge by hand.
- **Face anchor:** look at one frame and note where the face is, as fractions of the frame (x across, y down). It goes into `Reel(face=(x, y))`. Defaults are (0.51, 0.40).

## 2. Moments

```bash
python3 "$K/moments.py" "$WORK"                       # -> $WORK/reels/moments.md (every sentence + ranked windows)
python3 "$K/moments.py" "$WORK" --keep 154-160        # a starting keep.json from sentence numbers
```
Print the word indices of a stretch to trim fillers or reorder:
```bash
python3 -c "import json;W=[json.loads(l) for l in open('$WORK/words.jsonl')];print(' '.join(f'{i}:{W[i][\"w\"].strip()}' for i in range(3039,3100)))"
```
If a long-form edit already threw out the flubbed takes, put its kept word ranges in `$WORK/takes.json` (`{"keep": [[a, b], ...]}`) and `moments.py` only looks there.

## 3. Cut

```bash
RD="$WORK/reels/01-slug"; P="$GFX/$V-reels/01-slug"; mkdir -p "$RD"
# $RD/keep.json: {"keep": [[3072,3081],[3054,3071],[3239,3268,null,1652.65], ...]}
python3 "$K/reel_cut.py" "$WORK" "$RD"         # edl.json, words.json (reel times), cuts.json
```
- **Validation:** it prints `validation problems: N`, and N must be 0.
- **Levels:** it prints the speech levels it used (`act`/`decay`, relative to this recording). If cuts land in the room tone of a noisy room, pin them in keep.json: `"levels": {"act": -40, "decay": -47}`.
- **A flagged cut:** look at the envelope around it first.
  ```bash
  python3 -c "E=[float(x) for x in open('$WORK/env.txt')];t0=1651.6;print(' '.join(f'{t0+k/100:.2f}:{E[int(t0*100)+k]:.0f}' for k in range(0,220,4)))"
  ```
  If the flag is a breath after the word has decayed, pin the cut at the quietest frame after the decay with the 4th value (the end override).
- **Pace:** reels tighten pauses over 0.40 s, leaving 0.24 s after the decay and 0.10 s before speech. For a faster reel, set `"pace": {"pad_tail": 0.15, "pad_lead": 0.06, "min_sil": 0.28}` in keep.json.

## 3b. Reaction GIFs (optional; needs a free GIPHY_API_KEY)

The user adds the key themselves: `echo 'GIPHY_API_KEY=<key>' >> ~/.config/reels-studio.env`. Never ask for it in chat.
```bash
python3 "$K/fetch_gif.py" "this is fine dog" --sheet --slug this-is-fine     # -> $GFX/_library/gifs/_sheets/this-is-fine.jpg: LOOK at it
python3 "$K/fetch_gif.py" "this is fine dog" --pick 3 --slug this-is-fine     # -> $GFX/_library/gifs/this-is-fine.mp4 (+ .json credit)
```
Then in reel.py: `r.gif("this-is-fine", at("all day long"), style="cut")`. The library is shared by every reel.

## 4. Design, base clip, check

```bash
cp "$K/reel_template.py" "$RD/reel.py"     # rewrite the beats
python3 "$RD/reel.py" "$RD" "$P"           # plan.json, snaps.txt, $P/index.html, $P/assets
"$T/render_reel" "$SRC" "$RD/edl.json" "$P/base.mp4" "$RD" > "$RD/render_base.log" 2>&1   # ~1 min: the cut + edit_audio.wav
cd "$P"
"$T/hf" snapshot . --at "$(cat "$RD/snaps.txt")" -o "$RD/snaps" --no-end --describe false     # ~10 s per frame
"$T/vgrid" "$RD/snaps/sheet.jpg" 6 300 "$RD"/snaps/frame-*.png      # safe zones drawn in red
```
- **SFX-only changes:** rerun reel.py, then `render_reel ... "$RD" audio` (seconds). The run reports how many sounds came from the library and which kinds used the built-in synth.
- **Cut changes** (a new keep.json): rerun everything from `reel_cut.py` down.
- **Snapshots are slow** with 4K sources because Chrome decodes the clip twice per frame (band and frost). Check 5–8 key frames while iterating, and the full `snaps.txt` list once before the final render.

## 5. Render and finish

```bash
cd "$P" && (HF_CAPTURE_PARALLEL_STREAM=true "$T/hf" render . --format mp4 --quality delivery --fps 30000/1001 -o video.mp4) > render.log 2>&1   # ~4 min for 45 s
bash "$K/finish.sh" "$P" "$RD" "$RH/out/$V/01 - <title>.mp4"
```
`finish.sh` muxes `video.mp4` with `edit_audio.wav` (H.264 high, CRF 17, yuv420p, AAC 256k 48 kHz, faststart), runs `qa.py`, and delivers only on a pass. `qa.py` checks:
- 1080x1920 at 29.97 fps, length matches the cut;
- loudness between -15.5 and -12.5 LUFS, true peak at or under -0.5;
- a fresh transcription. A planned word missing just before a cut is a FAIL ("CLIPPED?"); an unplanned word right at a cut is a FAIL ("LEAK?"). Other misses are warnings, usually recognizer noise. Listen to those spots anyway.

## Gotchas

- **Pre-QA the cut before the slow render.** Mux a black video with `edit_audio.wav` and run `qa.py`. It runs the same word check in a minute.
  ```bash
  D=$(python3 -c "import json;print(json.load(open('$RD/cuts.json'))['total'])")
  "$GFX/bin/ffmpeg" -y -v error -f lavfi -i "color=black:s=1080x1920:r=30000/1001" -i "$RD/edit_audio.wav" -map 0:v -map 1:a -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -ar 48000 -ac 2 -t $D "$RD/preqa.mp4"
  python3 "$K/qa.py" "$RD/preqa.mp4" "$RD"
  ```
- **Dip cuts are the "weird sounds".** A cut inside continuous speech keeps a sliver of the neighbouring word. Prefer starting at the pause before the phrase, and slice-check each remaining dip cut. A word's real end can sit 0.3 s past its timestamp.
- **Leaked words.** A cut a few frames off drags in a neighbouring word. Find the real word edges by re-transcribing only those source seconds (`ffmpeg -ss <t> -t 3 -i "$SRC" -ac 1 -ar 16000 slice.wav`, then `"$T/stt2" slice.wav slice.jsonl`). Full-file timestamps drift 0.1–0.3 s; a short slice is accurate. Then pin the cut at the envelope dip between the words.
- **Recognizer false positives at a join.** The joined audio can make the recognizer invent a likely word. Prove it first: transcribe each side of the cut on its own from the reel's `final.mp4`. If both sides are clean, add `"word@seconds"` to `<reel>/qa_ignore.json`. `qa.py` prints every flag it skips. Never add an entry without that check.
- **Retakes:** when the speaker flubs a line they usually say it again right after. Join the clean part of the first take to the second at a silent gap, or use the second take.
- **Notes to the editor inside the take** ("cut that", "use this one for the reel"): read the whole transcript for them, follow them, and never put them in the cut.
- **Drawn-out last words** can dip below the decay level mid-word, so the auto end cuts the tail. QA catches it; pin the end where the envelope stays quiet.
- **Two words with no gap** ("or a", "know, a") can't be separated cleanly. Change the cut instead.
- **A layout at t = 0** is stored at -1 so frame 0 is already in that layout.
- **Repeated phrases:** `r.at()` uses the first match and prints a note when a phrase occurs more than once. Pass `after=`.
- **Run the steps separately, or check each exit code.** `python3 reel.py ... | grep` hides a failure, and the render then uses the old index.html against the new base.mp4.
- **Never overlap two tweens on one property.** HyperFrames renders with parallel workers that seek out of order. Visibility goes through instant `tl.set`s; entrances animate position, scale and blur.
- **Never schedule a tween before t = 0.** GSAP shifts the whole timeline and frame 0 comes up empty. Show frame-0 pieces with a `fromTo` at 0.
- **GSAP owns `transform`** on anything it animates. Put static offsets on a wrapper (`.pos` does that) or use `top`/`left`.
- **Don't name `raw()` classes `cw`, `cap`, `ck` or `cm`.** Those are reelkit's caption, checklist and counter classes.
- **Caption timing:** the recognizer can fold a pause into the next word's start, so a caption word can light slightly early. That reads fine. Never trust word times for cut points; `reel_cut.py` uses the envelope. If a word visibly lands early, fix its `s`/`e` in `words.json` after `reel_cut.py` and rerun reel.py.
