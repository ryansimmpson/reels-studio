#!/usr/bin/env python3
"""music: lay a steady music bed under a finished video.

    python3 music.py WORK --music FILE [--video FILE] [--start auto|SECONDS] [--bed -30] [--fade-out 1.8] [--duck] [--out FILE]

  --music   the track (wav/mp3), from a source the user is licensed to use (their music library subscription, or a
            royalty-free track they supplied). Log the source, title and id in the project's LICENSES.txt
            (see reference/sound.md).
  --video   the finished mp4 to score
  --fade-out  seconds; 0 for a loopable reel or an edit that already ends on its own
  --start   where in the track to begin: "auto" skips a quiet intro (first second within 4 dB of the track's body)
  --bed     music loudness, LUFS: one steady level for the whole video (ducking tends to sound pumpy under talking).
            -30 calm, -29 fast/upbeat (-26 is usually too loud), with the voice at -16: the music sits ~14 dB under
            the voice the whole way through.
  --duck    opt-in only: sidechain-duck the music under speech (often too much; don't use by default)
  --out     default: "<video> + music.mp4" next to the video; the no-music version is left as is

The voice is the edit's own track, only level-matched to -16 LUFS. The music is trimmed to the video, faded in (0.8 s)
and out (1.8 s), and held at one constant level (no ducking unless --duck). The mix is limited and loudness-normalised (two-pass) to -14 LUFS, true peak -1.5 dBTP. Video is copied.
"""
import json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import GFX, FFMPEG, FFPROBE, TOOLS, source_info, work_of
FF, FP = FFMPEG, FFPROBE


def lufs(args):
    r = subprocess.run([FF, "-hide_banner", "-nostats", *args, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1])


def auto_start(track):
    """first second where the track's short-term loudness reaches its body (skip a soft intro)"""
    # one reading per real second (asetnsamples groups 1 s of audio per frame; astats resets every frame)
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", track, "-t", "90", "-af",
                        "aresample=48000,asetnsamples=n=48000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    lv = [float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", r)]
    if len(lv) < 8: return 0.0
    body = sorted(lv)[len(lv) // 2]
    return float(next((k for k, v in enumerate(lv) if v >= body - 4), 0))


def main():
    a = sys.argv[1:]
    if not a or "--music" not in a: raise SystemExit(__doc__)
    work = os.path.abspath(a[0])
    if "--video" not in a: sys.exit("pass --video <finished.mp4>")
    video = a[a.index("--video") + 1]
    track = a[a.index("--music") + 1]
    bed = float(a[a.index("--bed") + 1]) if "--bed" in a else -30.0
    duck = "--duck" in a
    fade_out = float(a[a.index("--fade-out") + 1]) if "--fade-out" in a else 1.8
    st = a[a.index("--start") + 1] if "--start" in a else "auto"
    start = auto_start(track) if st == "auto" else float(st)
    out = a[a.index("--out") + 1] if "--out" in a else os.path.splitext(video)[0] + " + music.mp4"
    D = float(json.loads(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "json", video],
                                        capture_output=True, text=True).stdout)["format"]["duration"])
    lv = lufs(["-i", video, "-vn"])
    lm = lufs(["-ss", f"{start}", "-t", f"{D}", "-i", track])
    if lm < -45: raise SystemExit(f"the music from {start:.1f}s measures {lm:.1f} LUFS (silent?): pick --start inside the track")
    gv, gm = -16 - lv, bed - lm
    print(f"voice {lv:.1f} LUFS -> -16 ({gv:+.1f} dB) | music from {start:.1f}s {lm:.1f} LUFS -> {bed} ({gm:+.1f} dB)")
    graph = (f"[1:a]atrim=start={start},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,volume={gm:.2f}dB,"
             f"afade=t=in:d=0.8" + (f",afade=t=out:st={max(0, D - fade_out):.3f}:d={fade_out}" if fade_out > 0 else "") + "[m];"
             + (f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={gv:.2f}dB,asplit=2[v][sc];"
                f"[m][sc]sidechaincompress=threshold=0.025:ratio=6:attack=25:release=400:knee=4[md];"
                if duck else f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={gv:.2f}dB[v];[m]anull[md];")
             + "[v][md]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.84:level=false")
    # pass 1: measure the mix
    r = subprocess.run([FF, "-hide_banner", "-nostats", "-i", video, "-i", track, "-filter_complex",
                        graph + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run([FF, "-v", "error", "-y", "-i", video, "-i", track, "-filter_complex", graph + "," + ln + "[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-t", f"{D:.3f}", "-movflags", "+faststart", out], check=True)
    fin = lufs(["-i", out, "-vn"])
    vd = float(json.loads(subprocess.run([FP, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "json", out],
                                         capture_output=True, text=True).stdout)["streams"][0]["duration"])
    if abs(vd - D) > 0.1: raise SystemExit(f"video track {vd:.2f}s vs {D:.2f}s: do not deliver")
    print(f"out: {out}\n  {vd:.2f}s | {fin:.1f} LUFS")


if __name__ == "__main__":
    main()
