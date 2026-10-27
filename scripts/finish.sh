#!/bin/bash
# finish.sh <graphics project dir> <reel dir> <deliver path.mp4>
# Muxes the rendered picture (video.mp4) with the reel's mixed audio (edit_audio.wav: the voice on both channels
# plus the SFX bus), runs qa.py, and copies the result to the delivery path only if QA passes.
set -euo pipefail
P="$1"; RD="$2"; OUT="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
FF=$(python3 -c "import sys; sys.path.insert(0, '$HERE'); from paths import FFMPEG; print(FFMPEG)")
D=$(python3 -c "import json;print(json.load(open('$RD/cuts.json'))['total'])")
"$FF" -y -v error -i "$P/video.mp4" -i "$RD/edit_audio.wav" -map 0:v:0 -map 1:a:0 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -profile:v high -r 30000/1001 \
  -c:a aac -b:a 256k -ar 48000 -ac 2 -af "pan=stereo|c0=c1|c1=c1,afade=t=out:st=$(python3 -c "print($D-0.06)"):d=0.06" \
  -t "$D" -movflags +faststart "$P/final.mp4"
python3 "$HERE/qa.py" "$P/final.mp4" "$RD"
mkdir -p "$(dirname "$OUT")"
cp "$P/final.mp4" "$OUT"
echo "delivered: $OUT"
