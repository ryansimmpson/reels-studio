#!/bin/bash
# setup.sh: one-time install for reels-studio. Safe to run again (it skips what's already there).
# Needs macOS 26+ (on-device transcription), the Xcode command line tools (swiftc), Node 18+ and Python 3.
#   REELS_HOME   the workspace (default ~/reels-studio)
#   REELS_GFX    an existing HyperFrames install to reuse (default $REELS_HOME/_graphics)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RH="${REELS_HOME:-$HOME/reels-studio}"
GFX="${REELS_GFX:-$RH/_graphics}"
TOOLS="${REELS_TOOLS:-$RH/tools}"

need() { command -v "$1" >/dev/null || { echo "missing $1: $2"; exit 1; }; }
need swiftc "install the Xcode command line tools: xcode-select --install"
need node "install Node 18 or newer (nodejs.org)"
need python3 "install Python 3"
MAJOR=$(sw_vers -productVersion | cut -d. -f1)
[ "$MAJOR" -ge 26 ] || echo "note: macOS $MAJOR. On-device transcription (stt2) needs macOS 26 or newer."

mkdir -p "$RH/projects" "$RH/out" "$RH/_sound/sfx" "$GFX/_library/logos" "$GFX/_library/gifs" "$GFX/bin" "$TOOLS"

# HyperFrames (renders the composition in headless Chrome) plus static ffmpeg/ffprobe builds
if [ ! -f "$GFX/node_modules/hyperframes/bin/hyperframes.mjs" ]; then
  echo "installing HyperFrames into $GFX…"
  ( cd "$GFX" && { [ -f package.json ] || npm init -y >/dev/null; } && npm install --no-fund --no-audit hyperframes@^0.8.145 ffmpeg-static ffprobe-static )
fi
[ -x "$GFX/bin/ffmpeg" ] || cp "$(node -p "require('$GFX/node_modules/ffmpeg-static')")" "$GFX/bin/ffmpeg"
[ -x "$GFX/bin/ffprobe" ] || cp "$(node -p "require('$GFX/node_modules/ffprobe-static').path")" "$GFX/bin/ffprobe"
chmod +x "$GFX/bin/ffmpeg" "$GFX/bin/ffprobe"

# the Swift tools: voice + envelope, transcription, base clip + audio mix, contact sheets, OCR for screen captures
echo "building the tools into $TOOLS…"
for t in audio render_reel vgrid ocr; do swiftc -O "$HERE/$t.swift" -o "$TOOLS/$t" 2>/dev/null; done
swiftc -O -parse-as-library "$HERE/stt2.swift" -o "$TOOLS/stt2" 2>/dev/null

# hf: HyperFrames with this install's ffmpeg on PATH
cat > "$TOOLS/hf" <<EOF
#!/bin/bash
export PATH="$GFX/bin:\$PATH"
exec node "$GFX/node_modules/hyperframes/bin/hyperframes.mjs" "\$@"
EOF
chmod +x "$TOOLS/hf"

echo
echo "ready."
echo "  workspace  $RH  (projects/, out/, _sound/sfx/)"
echo "  graphics   $GFX"
echo "  tools      $TOOLS  (audio, stt2, render_reel, vgrid, ocr, hf)"
[ -n "$(ls "$RH/_sound/sfx" 2>/dev/null | grep -i '\.wav$' || true)" ] || \
  echo "  sounds     none yet: reels use built-in synth effects until you add files (reference/sound.md)"
