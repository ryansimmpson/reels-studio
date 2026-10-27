"""Where reels-studio keeps its shared things. Every path can be overridden with an environment variable.

  REELS_HOME   the workspace (default ~/reels-studio)
                 projects/<video>/        one work dir per long-form video (transcript, envelope, reels/<nn-slug>/)
                 out/<video>/             finished reels and caption files
                 tools/                   the compiled Swift tools (setup.sh builds them)
  REELS_GFX    the HyperFrames install and every composition (default $REELS_HOME/_graphics)
                 bin/ffmpeg, bin/ffprobe  (setup.sh copies them in; otherwise the ones on PATH are used)
                 _library/logos, _library/gifs   shared by every reel
  SFX_LIB      the sound-effects library (default $REELS_HOME/_sound/sfx), see reference/sound.md
  REELS_TOOLS  the compiled Swift tools (default $REELS_HOME/tools)
"""
import json, os, shutil

HOME = os.path.expanduser(os.environ.get("REELS_HOME") or "~/reels-studio")
GFX = os.path.expanduser(os.environ.get("REELS_GFX") or f"{HOME}/_graphics")
SFX = os.path.expanduser(os.environ.get("SFX_LIB") or f"{HOME}/_sound/sfx")
TOOLS = os.path.expanduser(os.environ.get("REELS_TOOLS") or f"{HOME}/tools")
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bin(name):
    p = f"{GFX}/bin/{name}"
    return p if os.path.exists(p) else (shutil.which(name) or name)


FFMPEG, FFPROBE = _bin("ffmpeg"), _bin("ffprobe")


def source_info(work):
    """the source facts ingest.py wrote for a work dir (display size, aspect, mic channel, language); {} if missing"""
    p = os.path.join(work, "source.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def work_of(reel_dir):
    """a reel dir is <work>/reels/<nn-slug>"""
    return os.path.normpath(os.path.join(reel_dir, "..", ".."))
