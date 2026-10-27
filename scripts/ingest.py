#!/usr/bin/env python3
"""ingest.py <source video> <work dir> [--mic auto|mix|left|right] [--lang en-US]

Step 1 for a new long-form video: reads the source, works out what it is, and writes what every later step needs.
  <work>/source.json   the source path, its display size and aspect (rotation applied), fps, mic channel, language
  <work>/audio.wav     the voice, 48 kHz mono
  <work>/env.txt       10 ms loudness envelope (cuts snap to it)
  <work>/words.jsonl   word timestamps (on-device transcription)

--mic   which channel the voice is on. auto (default) measures both: if one is 15 dB+ quieter (a lav or shotgun on
        one channel of a camera), the louder one is used; otherwise the two are mixed.
--lang  the language spoken, as a locale (en-US default; en-GB, es-ES, de-DE, fr-FR, pt-BR, ja-JP...). It sets the
        transcription and the QA re-transcription.
A source with rotation metadata (phone footage) or in a container AVFoundation can't read (mkv, webm) is converted
once to <work>/source.mov, upright, so every later step sees the frame the way it's watched.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import FFMPEG, FFPROBE, TOOLS

args = sys.argv[1:]
if len(args) < 2: sys.exit(__doc__)
SRC, WORK = os.path.abspath(args[0]), os.path.abspath(args[1])
opt = {"--mic": "auto", "--lang": "en-US"}
for k in opt:
    if k in args: opt[k] = args[args.index(k) + 1]
os.makedirs(WORK, exist_ok=True)
for t in ("audio", "stt2", "render_reel"):
    if not os.path.exists(f"{TOOLS}/{t}"): sys.exit(f"missing {TOOLS}/{t}: run scripts/setup.sh first")

# ---------- probe ----------
pr = json.loads(subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", SRC],
                               capture_output=True, text=True, check=True).stdout)
v = next(s for s in pr["streams"] if s["codec_type"] == "video")
a = next((s for s in pr["streams"] if s["codec_type"] == "audio"), None)
if a is None: sys.exit("the source has no audio track")
rot = 0
for sd in v.get("side_data_list", []):
    if "rotation" in sd: rot = int(float(sd["rotation"]))
rot = int(v.get("tags", {}).get("rotate", rot)) % 360
w, h = int(v["width"]), int(v["height"])
if rot in (90, 270): w, h = h, w
num, den = map(int, (v.get("avg_frame_rate") or v["r_frame_rate"]).split("/"))
fps = num / den if den else 0
dur = float(pr["format"]["duration"])
print(f"source {w}x{h} (display{', rotated %d' % rot if rot else ''}), {fps:.2f} fps, {dur / 60:.1f} min, "
      f"{a.get('channels', 1)} audio channel(s)")

# ---------- upright, readable copy when needed ----------
src = SRC
if rot or not SRC.lower().endswith((".mov", ".mp4", ".m4v")):
    src = f"{WORK}/source.mov"
    if not os.path.exists(src):
        print("converting to an upright .mov once (rotation or container)…")
        subprocess.run([FFMPEG, "-y", "-v", "error", "-stats", "-i", SRC, "-map", "0:v:0", "-map", "0:a:0",
                        "-c:v", "hevc_videotoolbox", "-b:v", "40M", "-tag:v", "hvc1", "-metadata:s:v", "rotate=0",
                        "-c:a", "pcm_s16le", "-ar", "48000", src], check=True)

# ---------- which channel the voice is on ----------
mic = opt["--mic"]
if mic == "auto":
    mic = "mix"
    if int(a.get("channels", 1)) >= 2:
        st = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-t", "300", "-i", src, "-vn", "-af",
                             "astats=measure_overall=none:measure_perchannel=RMS_level", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
        lv = [float(x) if x not in ("-inf", "inf") else -120.0 for x in re.findall(r"RMS level dB: (-?[\d.inf]+)", st)[:2]]
        if len(lv) == 2 and abs(lv[0] - lv[1]) >= 15: mic = "left" if lv[0] > lv[1] else "right"
        print(f"channel levels {lv[0]:.1f} / {lv[1]:.1f} dB -> mic {mic}" if len(lv) == 2 else "mic mix")

info = dict(src=src, original=SRC, width=w, height=h, aspect=round(w / h, 5), fps=round(fps, 3), duration=round(dur, 2),
            mic=mic, lang=opt["--lang"])
json.dump(info, open(f"{WORK}/source.json", "w"), indent=1)

# ---------- voice, envelope, words ----------
env = {**os.environ, "REELS_MIC": mic, "REELS_LANG": opt["--lang"]}
print("extracting the voice and the loudness envelope…")
subprocess.run([f"{TOOLS}/audio", src, f"{WORK}/audio.wav", f"{WORK}/env.txt"], check=True, env=env)
print("transcribing on device (about a minute per 10 minutes of video)…")
r = subprocess.run([f"{TOOLS}/stt2", f"{WORK}/audio.wav", f"{WORK}/words.jsonl"], capture_output=True, text=True, env=env)
if r.returncode: sys.exit(r.stdout[-800:] + r.stderr[-800:])
n = sum(1 for l in open(f"{WORK}/words.jsonl") if l.strip())
print(f"done: {n} words. source.json, audio.wav, env.txt and words.jsonl are in {WORK}")
print(f'next: python3 {os.path.dirname(os.path.abspath(__file__))}/moments.py "{WORK}"')
