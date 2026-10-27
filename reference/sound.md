# Sound

Reels ship with quiet UI sound effects under the voice, and music only when the creator asks for it.

## Effects library

`$SFX_LIB` (default `$REELS_HOME/_sound/sfx`). `render_reel` reads it directly:

- **File names:** `<kind>.wav`, or variants `<kind>-1.wav`, `<kind>-2.wav`… taken in turn so repeats don't sound identical.
- **Levels:** each file is peak-normalised on load, so the gains in the components keep their meaning whatever the file's level. `levels.json` (`{"whoosh": -3}`) trims a kind in dB.
- **Missing kinds** play a built-in synth version, and the run says which. The synth is fine for a draft; real samples sound better, so fill the library before delivering to a client.
- **One-off sounds:** for a sound that fits only one beat, put the file in the project and pass its absolute path: `r.sfx(t, "custom", -30, file="/path/to/sound.wav")`.

| kind | used for | search for | length |
|---|---|---|---|
| pop | a piece entering, a GIF card | "soft ui pop", "bubble pop", "interface pop" | ≤ 250 ms |
| tick | typing, counting, checklist items | "ui click", "soft tick", "keyboard tap" | ≤ 80 ms |
| ding | a logo landing, a counter settling | "soft notification", "chime ding", "success chime" | ≤ 900 ms |
| whoosh | layout switches, scenes, GIF cutaways | "soft whoosh transition", "air swipe" | 300–700 ms |
| swish | zooms, small moves | "short swish", "fast swipe" | ≤ 300 ms |
| riser | building into a reveal | "short riser", "tension build" | 0.8–1.5 s |
| impact | the one dramatic beat | "soft cinematic hit", "deep boom short" | ≤ 1 s |
| shutter | a screenshot snapping in | "camera shutter", "screenshot" | ≤ 400 ms |
| marker | a highlighter sweep | "marker pen stroke", "highlighter" | 300–700 ms |
| scribble | a drawn circle, box or arrow | "pencil scribble", "pen circle drawing" | 400–900 ms |

Build 2–3 variants each for pop, tick and ding (they repeat the most).

## Where sounds come from

Use only sources the creator is licensed to use:
- their sound-library subscription (if a sound or music library connector is attached to this session, search and download through it);
- royalty-free packs with a clear licence (CC0, or a licence that allows use in monetised social video);
- sounds the creator supplies.

Never rip sounds or music from other videos, songs or platforms.

**Picking sounds without hearing them:**
1. Shortlist by title, tags and duration. Prefer short, clean, dry sounds: no long tails, no music bed inside an effect, nothing comedic unless the moment asks for it.
2. Measure each file with ffmpeg: duration, where the peak sits (a pop, tick or ding must peak within about 30 ms), tail length (`silencedetect`), overall level. Reject slow attacks for hits.
3. Put it in the sample render and let the creator approve by ear. If they don't like a sound, swap the file; the code stays the same.

**Logging:** every file used goes in `$SFX_LIB/LICENSES.txt` (and music in the project's), one line each: `date · source · sfx|music · title · id or url · licence`.

## Music, when it's used

- **Choosing:** instrumental only. Match the mood and the BPM to the pacing. Under talking, keep it sparse: soft keys, pads, light percussion. Use an instruments-only stem if the full mix is busy.
- **Length:** reels loop, so use a loopable edit at the reel's exact length if the library offers one, or trim on a bar line.
- **Mixing:** `scripts/music.py WORK --video <final.mp4> --music <track.wav> --fade-out 0`.
  - The bed stays at ONE steady level, no ducking: −30 LUFS for calm reels, −29 for upbeat (−28 at most).
  - The voice is level-matched to −16, and the result is mastered to −14 LUFS.
  - Re-run `qa.py` on the result; every word must still come through.
