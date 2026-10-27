import difflib, json, os, re, subprocess, sys
# qa.py <final.mp4> <reel dir> [tools dir]
# The QA pass before anyone sees a reel. Exits 1 on any FAIL.
#   - 1080x1920, ~29.97 fps, H.264, AAC 48 kHz stereo, length matches the cut
#   - loudness about -14 LUFS integrated, true peak at or under -1 dBTP
#   - re-transcribes the reel and checks every planned word is heard. A word missing right before a jump cut
#     is a clipped ending, the most noticeable mistake in a reel, so it is a FAIL, not a warning.
# Needs <tools dir>/stt2 (setup.sh builds it into $REELS_HOME/tools) and ffmpeg/ffprobe ($REELS_GFX/bin or PATH).
# Transcribes in the language ingest.py recorded for the video (source.json "lang").
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import GFX, FFMPEG, FFPROBE, TOOLS, source_info, work_of
OUT, RD = sys.argv[1], sys.argv[2]
TOOLS = sys.argv[3] if len(sys.argv) > 3 else TOOLS
FF, FP = FFMPEG, FFPROBE
LANG = source_info(work_of(RD)).get("lang", "en-US")
fails, warns = [], []

def probe(sel, entries):
    r = subprocess.run([FP, "-v", "error", "-select_streams", sel, "-show_entries", entries, "-of", "json", OUT], capture_output=True, text=True)
    return json.loads(r.stdout)["streams"][0]
v = probe("v:0", "stream=width,height,codec_name,avg_frame_rate,pix_fmt")
a = probe("a:0", "stream=codec_name,sample_rate,channels")
dur = float(json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "json", OUT], capture_output=True, text=True).stdout)["format"]["duration"])
total = json.load(open(f"{RD}/cuts.json"))["total"]
num, den = map(int, v["avg_frame_rate"].split("/")); fps = num / den
print(f"video {v['width']}x{v['height']} {v['codec_name']} {fps:.3f} fps {v['pix_fmt']} | audio {a['codec_name']} {a['sample_rate']} Hz x{a['channels']} | {dur:.2f}s (cut {total:.2f}s)")
QW, QH = map(int, os.environ.get("QA_SIZE", "1080x1920").split("x"))
if (v["width"], v["height"]) != (QW, QH): fails.append(f"resolution {v['width']}x{v['height']}, must be {QW}x{QH}")
if abs(fps - 29.97) > 0.05: fails.append(f"frame rate {fps:.3f}")
if v["codec_name"] != "h264": warns.append(f"video codec {v['codec_name']} (h264 is the safest upload)")
if v["pix_fmt"] != "yuv420p": warns.append(f"pixel format {v['pix_fmt']}")
if a["codec_name"] != "aac" or int(a["sample_rate"]) != 48000 or int(a["channels"]) != 2: fails.append(f"audio {a} (want aac 48000 stereo)")
if abs(dur - total) > 0.15: fails.append(f"length {dur:.2f}s vs cut {total:.2f}s")
if dur > 90: warns.append("over 90 s: Instagram treats it as a regular video in some placements")

r = subprocess.run([FF, "-nostats", "-i", OUT, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]); pk = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)[-1])
print(f"loudness {I:.1f} LUFS, true peak {pk:.1f} dBTP")
if not -15.5 <= I <= -12.5: fails.append(f"loudness {I:.1f} LUFS (want about -14)")
if pk > -0.5: fails.append(f"true peak {pk:.1f} dBTP (want <= -1)")

wav, js = f"{RD}/qa_audio.wav", f"{RD}/qa_words.jsonl"
subprocess.run([FF, "-y", "-v", "error", "-i", OUT, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav], check=True)
subprocess.run([f"{TOOLS}/stt2", wav, js], capture_output=True, text=True, check=True, env={**os.environ, "REELS_LANG": LANG})
norm = lambda w: re.sub(r"[^a-z0-9']", "", w.lower())
plan = json.load(open(f"{RD}/words.json"))
heard = [json.loads(l) for l in open(js) if l.strip()]
A, B = [norm(w["w"]) for w in plan], [norm(w["w"]) for w in heard]
cuts = json.load(open(f"{RD}/cuts.json"))["cuts"] + [total]
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
missing = []
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op in ("delete", "replace"):
        for i in range(i1, i2):
            w = plan[i]
            before_cut = any(0 <= c - w["e"] < 0.6 for c in cuts) and (i + 1 == len(plan) or plan[i + 1]["s"] >= min(c for c in cuts if c >= w["e"] - 0.01) - 0.01)
            missing.append((w, before_cut, op))
# leaks: words heard that were never planned, right at a cut. A cut that starts or ends a few frames off
# drags in the neighbouring take's word ("right?" at the head of a line). Reel 02 v2 shipped one past the old QA.
starts = [0.0] + cuts[:-1]
for op, i1, i2, j1, j2 in sm.get_opcodes():
    extra = range(j1, j2) if op == "insert" else (range(j1 + (i2 - i1), j2) if op == "replace" and j2 - j1 > i2 - i1 else [])
    for j in extra:
        h = heard[j]
        near = any(-0.15 <= h["s"] - c <= 1.0 for c in starts) or any(-1.0 <= h["e"] - c <= 0.15 for c in cuts)
        (fails if near else warns).append(f"extra '{h['w'].strip()}' heard at {h['s']:.2f}s" + (" LEAK? (next to a cut)" if near else ""))
print(f"transcript match {sm.ratio() * 100:.0f}% ({len(A)} planned words, {len(B)} heard)")
for w, cut, op in missing:
    tag = "CLIPPED? (last word before a cut)" if cut else ("misheard" if op == "replace" else "not heard")
    (fails if cut else warns).append(f"'{w['w']}' at {w['s']:.2f}s {tag}")
# <reel>/qa_ignore.json: ["word@seconds", ...] for flags proven false by transcribing each side of the cut on its
# own (the joined audio can make the recognizer invent a word, e.g. "handle, 100" heard as "handle towards 100")
ign = json.load(open(f"{RD}/qa_ignore.json")) if os.path.exists(f"{RD}/qa_ignore.json") else []
def ignored(msg):
    m = re.match(r"(?:extra )?'(.+?)'(?: heard)? at ([\d.]+)s", msg)
    return bool(m) and any(norm(i.split("@")[0]) == norm(m.group(1)) and abs(float(i.split("@")[1]) - float(m.group(2))) < 0.4 for i in ign)
for lst in (fails, warns):
    skipped = [x for x in lst if ignored(x)]
    for x in skipped: print("  ignored (verified in qa_ignore.json):", x)
    lst[:] = [x for x in lst if not ignored(x)]
for x in warns: print("  warn:", x)
for x in fails: print("  FAIL:", x)
print("QA", "FAILED" if fails else "passed", f"({len(fails)} fails, {len(warns)} warnings)")
os.remove(wav)
sys.exit(1 if fails else 0)
