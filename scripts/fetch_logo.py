import os, re, sys, urllib.request
# fetch_logo.py <slug> [<slug> ...]   -> $G/_library/logos/<slug>.svg (shared by every reel)
# Real brand marks, full colour. Order: Simple Icons CDN (brand-coloured SVG, CC0) -> the site's favicon via
# Google's s2 service (PNG, last resort). Slugs are Simple Icons slugs: lower case, no spaces
# (googledocs, quickbooks, hubspot, n8n). Look a slug up at https://simpleicons.org.
# Use real logos for every tool, site or product the speaker names or describes: viewers recognise the tools they use.
# Pattern borrowed from open-edits' fetch_brand_asset.py (MIT).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import GFX, FFMPEG, FFPROBE, TOOLS, source_info, work_of
OUT = f"{GFX}/_library/logos"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "reels-edit/1.0 (logo fetch for a local video edit)"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read(), r.headers.get("Content-Type", "")

for slug in sys.argv[1:]:
    slug = re.sub(r"[^a-z0-9]", "", slug.lower())
    try:
        data, ct = get(f"https://cdn.simpleicons.org/{slug}")
        if b"<svg" in data:
            open(f"{OUT}/{slug}.svg", "wb").write(data); print(f"{slug}: simple-icons svg -> {OUT}/{slug}.svg"); continue
    except Exception as e:
        print(f"{slug}: simple-icons miss ({e})")
    try:
        data, ct = get(f"https://www.google.com/s2/favicons?domain={slug}.com&sz=256")
        open(f"{OUT}/{slug}.png", "wb").write(data); print(f"{slug}: favicon png -> {OUT}/{slug}.png (check it looks right)")
    except Exception as e:
        print(f"{slug}: no logo found ({e})")
