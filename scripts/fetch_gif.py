import json, os, subprocess, sys, urllib.parse, urllib.request
# fetch_gif.py "<search>" [--sheet] [--pick N] [--slug name] [--n 9]
# Reaction GIFs from Giphy (an idea from open-edits, MIT), saved as MP4 so HyperFrames can seek them frame-accurately.
#   (no flag)   print the top results: title, size, length.
#   --sheet     also download small previews of the top N (default 9) and tile 3 frames of each into
#               $G/_library/gifs/_sheets/<slug>.jpg. LOOK at it before picking: the right face, the right joke,
#               no burned-in text that fights the line, nothing offensive.
#   --pick N    download result N (1-based, from the same search) to $G/_library/gifs/<slug>.mp4
# Needs GIPHY_API_KEY (free at developers.giphy.com: Create an App -> API). The user adds it themselves:
#   echo 'GIPHY_API_KEY=<key>' >> ~/.config/reels-studio.env
# Rating is capped at pg-13. GIF audio is never mixed in. Place it with reel.gif(...).
q = sys.argv[1]
args = sys.argv[2:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
key = os.environ.get("GIPHY_API_KEY")
envf = os.path.expanduser("~/.config/reels-studio.env")
if not key and os.path.exists(envf):
    for line in open(envf):
        if line.startswith("GIPHY_API_KEY="): key = line.split("=", 1)[1].strip()
if not key: sys.exit("No GIPHY_API_KEY. Ask the user to add it to ~/.config/reels-studio.env themselves (never paste it in chat).")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import GFX, FFMPEG, FFPROBE, TOOLS, source_info, work_of
FF, FP = FFMPEG, FFPROBE
LIB = f"{GFX}/_library/gifs"
os.makedirs(f"{LIB}/_sheets", exist_ok=True)
slug = opt("--slug") or "-".join(q.lower().split())
n = int(opt("--n", 9))
url = "https://api.giphy.com/v1/gifs/search?" + urllib.parse.urlencode({"api_key": key, "q": q, "limit": max(n, 12), "rating": "pg-13", "lang": "en"})
data = json.load(urllib.request.urlopen(url, timeout=20))["data"]

def dur(f):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0

if "--pick" in args:
    g = data[int(opt("--pick")) - 1]
    out = f"{LIB}/{slug}.mp4"
    urllib.request.urlretrieve(g["images"]["original_mp4"]["mp4"], out)
    json.dump({"title": g.get("title", ""), "url": g["url"], "query": q, "rating": g.get("rating")}, open(f"{LIB}/{slug}.json", "w"))
    print(f"saved {out}  {dur(out):.1f}s  ({g.get('title', '')})")
    sys.exit(0)

for k, g in enumerate(data, 1):
    m = g["images"]["original_mp4"]
    print(f"{k:2}. {g.get('title', '')[:58]:58} {m.get('width')}x{m.get('height')} {int(m.get('mp4_size', 0)) // 1024:5} KB")
if "--sheet" in args:
    tmp = f"{LIB}/_sheets/{slug}"
    os.makedirs(tmp, exist_ok=True)
    tiles = []
    for k, g in enumerate(data[:n], 1):
        src = g["images"].get("fixed_height_small", {}).get("mp4") or g["images"]["original_mp4"]["mp4"]
        f = f"{tmp}/{k}.mp4"
        urllib.request.urlretrieve(src, f)
        d = dur(f) or 1.0
        row = f"{tmp}/{k}.jpg"
        # 3 frames across the clip, labelled with its number and length
        subprocess.run([FF, "-y", "-v", "error", "-i", f, "-vf",
                        f"fps=3/{d:.3f},scale=-2:200,tile=3x1,drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:text='{k}  {d:.1f}s':x=8:y=8:fontsize=26:fontcolor=yellow:box=1:boxcolor=black",
                        "-frames:v", "1", row])
        tiles.append(row)
    sheet = f"{LIB}/_sheets/{slug}.jpg"
    subprocess.run([FF, "-y", "-v", "error"] + sum([["-i", t] for t in tiles], []) + [
        "-filter_complex", "".join(f"[{i}:v]scale=900:200:force_original_aspect_ratio=decrease,pad=900:220:0:0[v{i}];" for i in range(len(tiles)))
        + "".join(f"[v{i}]" for i in range(len(tiles))) + f"vstack=inputs={len(tiles)}", sheet])
    print(f"sheet: {sheet}")
