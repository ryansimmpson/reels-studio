"""screenkit: screenshots and screen recordings as animated figures.

    from screenkit import Screen, kit
    s = Screen("scr1", "screens/article.png", t0=3.2, t1=11.0, w=1100, h=680, url="example.com/article")
    s.zoom(4.4, find="The headline")             # eased camera into the headline
    s.circle(5.3, find="The headline")           # hand-drawn circle around it
    s.reset(6.6); s.scroll(7.0, find="the passage"); s.highlight(8.0, find="the passage they read")
    s.focus(9.2, find="the passage they read"); s.unfocus(10.6)
    html = s.html(cx, cy)                        # the host places it (centre point, composition px)
    js = s.js()                                  # SK.init + every call, sorted by time
    css, runtime = kit()                         # inline once per page, before the timeline script
    s.sfx                                        # [(t, kind, gain)] for the host's SFX plan (sound-library kinds)

Rects are [x, y, w, h] in source pixels (the PNG, or the video frame), top-left origin. find= looks a phrase up in
the capture's sidecar JSON, written by capture.mjs (web pages) or ocr (anything else). A multi-line passage returns
one rect per line: highlight() sweeps each line, everything else uses their union. select= uses capture.mjs selects.
"""
import json, os, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
from paths import FFPROBE
VIDEO = (".mp4", ".mov", ".m4v", ".webm")
BAR = {"browser": 46, "window": 40, "phone": 0, "none": 0}
LOCK = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">'
        '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/></svg>')
# SFX per action (sound-library kinds, see reference/sound.md): quiet, under the voice
SFX = {"enter": ("whoosh", -31), "snap": ("shutter", -29), "zoom": ("swish", -35), "highlight": ("marker", -31),
       "underline": ("marker", -33), "circle": ("scribble", -30), "box": ("scribble", -32), "arrow": ("scribble", -32),
       "focus": ("swish", -36), "popout": ("pop", -30)}


def kit():
    """(css, js) to inline once per page that has screens"""
    return open(f"{HERE}/screenkit.css").read(), open(f"{HERE}/screenkit.js").read()


def media_size(path):
    if path.lower().endswith(".png"):
        with open(path, "rb") as f:
            return struct.unpack(">II", f.read(24)[16:24])
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height", "-of", "json", path], capture_output=True, text=True).stdout
    st = json.loads(out)["streams"][0]
    return st["width"], st["height"]


def union(rs):
    x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
    return [x0, y0, max(r[0] + r[2] for r in rs) - x0, max(r[1] + r[3] for r in rs) - y0]


def _esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Screen:
    def __init__(self, sid, src, t0, t1=None, w=1100, h=680, frame="browser", url="", title="", fit="width",
                 tilt=(8, -16, -1.5), radius=None, data=None, media_start=0.0, D=None, asset_dir="assets/screens",
                 track=40, sfx=True, dark=False):
        """frame: browser | window | phone | none. fit: width (scrolls) | contain | height.
        tilt: resting pose (rotateX, rotateY, rotateZ degrees); (0, 0, 0) is flat. data: sidecar JSON path/dict
        (default: <src stem>.json if it exists). D: composition length, for screen recordings that run to the end."""
        self.sid, self.src, self.t0, self.t1 = sid, src, t0, t1
        self.name = os.path.basename(src)
        self.rel = f"{asset_dir}/{self.name}"
        self.video = src.lower().endswith(VIDEO)
        self.sw, self.sh = media_size(src)
        self.w, self.h, self.frame, self.url, self.title, self.fit = w, h, frame, url, title, fit
        self.tilt = list(tilt)
        self.radius = radius if radius is not None else (62 if frame == "phone" else 20)
        if data is None:
            guess = os.path.splitext(src)[0] + ".json"
            data = guess if os.path.exists(guess) else None
        self.data = json.load(open(data)) if isinstance(data, str) else (data or {})
        self.media_start, self.D, self.track, self.sfx_on, self.dark = media_start, D, track, sfx, dark
        self.calls, self.sfx = [], []

    # ---- regions ----
    def lines(self, find=None, select=None, rect=None, nth=0):
        """the rects for a phrase (one per line), a CSS selector match, or a literal rect"""
        if rect is not None: return [list(rect)]
        key, table = (find, "finds") if find is not None else (select, "selects")
        hits = self.data.get(table, {}).get(key)
        if not hits or nth >= len(hits):
            raise SystemExit(f"{self.sid}: {key!r} isn't in {self.name}'s capture data. Re-run capture.mjs/ocr with "
                             f"--{'find' if find is not None else 'select'} \"{key}\" (or pass rect=[x, y, w, h]).")
        hit = hits[nth]
        return [list(r) for r in hit] if find is not None else [list(hit)]

    def rect(self, find=None, select=None, rect=None, nth=0):
        return union(self.lines(find, select, rect, nth))

    # ---- calls (any order; emitted sorted by time) ----
    def _c(self, t, js, sound=None):
        self.calls.append((round(t, 3), len(self.calls), js))
        if sound and self.sfx_on and t >= 0:
            kind, gain = SFX[sound]
            self.sfx.append((round(t, 3), kind, gain))

    def _r(self, kw):
        return self.rect(kw.pop("find", None), kw.pop("select", None), kw.pop("rect", None), kw.pop("nth", 0))

    def _o(self, kw):
        return json.dumps({k: v for k, v in kw.items() if v is not None})

    def enter(self, t, style="tilt"):
        """tilt | rise | snap (a screenshot flash, with a shutter) | zoom"""
        self._c(t, f'SK.enter("{self.sid}", {t:.3f}, "{style}");', "snap" if style == "snap" else "enter")

    def exit(self, t):
        self._c(t, f'SK.exit("{self.sid}", {t:.3f});')

    def tilt_to(self, t, pose=(0, 0, 0), dur=1.0):
        """change the 3D pose; (0, 0, 0) lays the screen flat for reading"""
        self._c(t, f'SK.tilt("{self.sid}", {t:.3f}, {json.dumps(list(pose))}, {{"dur": {dur}}});')

    def flat(self, t, dur=1.0): self.tilt_to(t, (0, 0, 0), dur)

    def float(self, t0, t1, amp=7):
        self._c(t0, f'SK.float("{self.sid}", {t0:.3f}, {t1:.3f}, {amp});')

    def zoom(self, t, dur=1.1, pad=.14, zmax=3.2, flat=False, sfx=True, **where):
        """eased camera into a region: find= / select= / rect=. flat=True levels the 3D tilt at the same time"""
        r = self._r(where)
        self._c(t, f'SK.zoom("{self.sid}", {t:.3f}, {json.dumps(r)}, {self._o(dict(dur=dur, pad=pad, zmax=zmax))});', "zoom" if sfx else None)
        if flat: self.flat(t, dur)

    def reset(self, t, dur=1.0):
        self._c(t, f'SK.reset("{self.sid}", {t:.3f}, {{"dur": {dur}}});')

    def scroll(self, t, y=None, dur=1.6, at=.2, **where):
        """scroll so source y (or the region from find=/select=) sits a fifth of the way down the view"""
        if y is None: y = self._r(where)[1]
        self._c(t, f'SK.scroll("{self.sid}", {t:.3f}, {y}, {self._o(dict(dur=dur, at=at))});')

    def highlight(self, t, until=None, color=None, stagger=.24, **where):
        """marker sweep over a passage, one bar per line"""
        ls = self.lines(where.pop("find", None), where.pop("select", None), where.pop("rect", None), where.pop("nth", 0))
        self._c(t, f'SK.highlight("{self.sid}", {t:.3f}, {json.dumps(ls)}, {self._o(dict(until=until, color=color, stagger=stagger))});', "highlight")

    def underline(self, t, until=None, color=None, **where):
        self._c(t, f'SK.underline("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(until=until, color=color))});', "underline")

    def circle(self, t, until=None, color=None, pad=18, **where):
        self._c(t, f'SK.circle("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(until=until, color=color, pad=pad))});', "circle")

    def box(self, t, until=None, color=None, **where):
        self._c(t, f'SK.box("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(until=until, color=color))});', "box")

    def arrow(self, t, until=None, frm="left", length=230, color=None, **where):
        """frm: left | right | top | bottom, the side the arrow comes from"""
        self._c(t, f'SK.arrow("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(until=until, color=color, len=length, **{"from": frm}))});', "arrow")

    def focus(self, t, blur=7, dim=.5, ring=True, pad=16, **where):
        """blur and dim everything outside the region"""
        self._c(t, f'SK.focus("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(blur=blur, dim=dim, ring=ring, pad=pad))});', "focus")

    def unfocus(self, t):
        self._c(t, f'SK.unfocus("{self.sid}", {t:.3f});')

    def edges(self, t, on=True):
        """soft blur and shade around the outer edges of the whole screen"""
        self._c(t, f'SK.edges("{self.sid}", {t:.3f}, {"true" if on else "false"});')

    def popout(self, t, until=None, scale=1.12, **where):
        """lift a region (a headline, a price, a button) off the page; images only (recordings get focus())"""
        self._c(t, f'SK.popout("{self.sid}", {t:.3f}, {json.dumps(self._r(where))}, {self._o(dict(until=until, scale=scale))});', "popout")

    # ---- output ----
    def media(self, cls):
        if not self.video:
            return f'<div class="{cls}"><img src="{self.rel}" alt=""></div>'
        end = self.t1 if self.t1 is not None else (self.D or self.t0 + 30)
        k = 1 if cls == "sk-sharp" else 0
        return (f'<div class="{cls}"><video src="{self.rel}" muted playsinline data-start="{max(0.0, self.t0 - .4):.3f}" '
                f'data-duration="{end - self.t0 + .9:.3f}" data-media-start="{self.media_start:.3f}" '
                f'data-track-index="{self.track + k}"></video></div>')

    def html(self, cx, cy):
        bar = BAR[self.frame]
        chrome = {"browser": f'<div class="sk-bar"><i></i><i></i><i></i><span class="sk-nav">‹›</span>'
                             f'<div class="sk-url">{LOCK}<span>{_esc(self.url)}</span></div><span style="width:70px"></span></div>',
                  "window": f'<div class="sk-bar"><i></i><i></i><i></i><div class="sk-title">{_esc(self.title)}</div></div>',
                  "phone": '<div class="sk-notch"></div>', "none": ""}[self.frame]
        return (f'<div id="{self.sid}" class="sk sk-{self.frame}{" sk-dark" if self.dark else ""}" style="left:{round(cx - self.w / 2)}px;'
                f'top:{round(cy - self.h / 2)}px;width:{self.w}px;height:{self.h}px;--r:{self.radius}px;--bar:{bar}px">'
                f'<div class="sk-float"><div class="sk-card">{chrome}<div class="sk-view"><div class="sk-page">'
                f'{self.media("sk-base")}{self.media("sk-sharp")}<svg class="sk-mark"></svg><svg class="sk-ink"></svg></div>'
                f'<div class="sk-vig"></div></div><div class="sk-glare"></div></div></div></div>')

    def js(self):
        o = dict(sw=self.sw, sh=self.sh, fit=self.fit, tilt=self.tilt, kind="video" if self.video else "image",
                 src=self.rel, dark=self.dark)
        return "\n".join([f'SK.init("{self.sid}", {json.dumps(o)});'] + [c[2] for c in sorted(self.calls)])
