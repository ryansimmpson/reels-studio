"""reelkit: builds a 9:16 HyperFrames reel from a talking-head clip plus animated figures, in any brand.

A reel script (copy scripts/reel_template.py) does:

    from reelkit import Reel
    r = Reel(REEL_DIR, PROJECT_DIR, brand="studio")  # loads words.json + cuts.json from reel_cut.py
    t = r.at("three tools")                         # reel time of a spoken phrase
    r.layout(0, "split"); r.layout(r.at("and that's"), "full")
    r.hook("Three tools I", "use daily", until=2.6)
    r.logos(["notion", "figma"], times=[...])
    ...
    r.build()                                       # <reel>/plan.json (SFX for render_reel) + <project>/index.html

Canvas: 1080x1920 CSS px. The base clip (render_reel output, any aspect) sits inside the composition, so the glass
can blur it. Two layouts:
  full   the speaker fills the frame (face-anchored 9:16 crop). Captions sit on the chest. On this shot it's
         captions and subtle camera motion only; the hook is the one exception.
  split  the speaker in a rounded band at the bottom, a frosted copy of the footage behind a graphics slot on top
         (zone "slot", y 200-840). Captions sit on the line just above the band.
Colours and fonts come from the brand (scripts/brand.py, brands/*.json): the code below writes tokens such as
__ACC__ and __SANS__ and build() swaps in the brand's values.
Every method takes reel seconds. Every component adds its own SFX at quiet levels unless sfx=False.
See reference/components.md for the full list and reference/style.md for the rules.
"""
import json, math, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screenkit import Screen, kit as screen_kit
import brand as brandkit
from paths import GFX, FFPROBE, source_info, work_of

LOGO_DIRS = [f"{GFX}/_library/logos"]
# brand colours for one-colour (Simple Icons) SVGs, so they render as real logos on a white tile
BRAND_HEX = {"google": "#4285F4", "googledocs": "#4285F4", "googleads": "#4285F4", "googledrive": "#1FA463",
             "googlesheets": "#34A853", "googlegemini": "#8E75B2", "gmail": "#EA4335", "zoom": "#0B5CFF",
             "quickbooks": "#2CA01C", "facebook": "#0866FF", "meta": "#0467DF", "instagram": "#E4405F",
             "youtube": "#FF0000", "openai": "#000000", "chatgpt": "#10A37F", "claude": "#D97757",
             "anthropic": "#191919", "notion": "#000000", "slack": "#4A154B", "hubspot": "#FF7A59",
             "stripe": "#635BFF", "shopify": "#7AB55C", "canva": "#00C4CC", "tiktok": "#000000", "linkedin": "#0A66C2",
             "x": "#000000", "github": "#181717", "zapier": "#FF4F00", "make": "#6D00CC", "n8n": "#EA4B71",
             "airtable": "#18BFFF", "calendly": "#006BFF", "salesforce": "#00A1E0", "wordpress": "#21759B"}
ALIAS = {"sheets": "googlesheets", "drive": "googledrive", "docs": "googledocs", "workspace": "google",
         "googleworkspace": "google", "ads": "googleads", "gemini": "googlegemini", "openai_logo": "openai"}

FULL = (0, 0, 1080, 1920)
BAND = (24, 968, 1032, 912, 44)          # split layout: the speaker's band (x, y, w, h, radius)
CAP_Y = {"full": 1300, "split": 900}     # caption centre line per layout
ZONE = {"slot": (540, 525), "top": (540, 300), "low": (540, 1450)}
MORPH = 0.62
ACC, ACC2, GREEN = "__ACC__", "__ACC2__", "__OK__"     # brand tokens, filled in by build()

def _norm(w): return re.sub(r"[^a-z0-9%$']", "", w.lower())
def _esc(s): return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

ICONS = {
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M4 7l8 6 8-6"/>',
    "phone": '<path d="M6.6 3.5h2.6l1.6 4.3-2 1.5a12 12 0 006 6l1.5-2 4.3 1.6v2.6a2 2 0 01-2.2 2A17 17 0 014.6 5.7a2 2 0 012-2.2z"/>',
    "missed": '<path d="M6.6 3.5h2.6l1.6 4.3-2 1.5a12 12 0 006 6l1.5-2 4.3 1.6v2.6a2 2 0 01-2.2 2A17 17 0 014.6 5.7a2 2 0 012-2.2z"/><path d="M15 3l6 6M21 3l-6 6"/>',
    "chat": '<path d="M5 5h14a2 2 0 012 2v8a2 2 0 01-2 2h-7l-5 4v-4H5a2 2 0 01-2-2V7a2 2 0 012-2z"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0116 0"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0113 0"/><circle cx="17" cy="9" r="2.8"/><path d="M16 14.2a5.5 5.5 0 016 5.8"/>',
    "cal": '<rect x="3" y="5" width="18" height="16" rx="2.5"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "doc": '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "money": '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.8"/><path d="M6 9v6M18 9v6"/>',
    "spark": '<path d="M12 2.5l1.9 5.6 5.6 1.9-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9z"/>',
    "cloud": '<path d="M7 18.5h10.5a4 4 0 00.6-7.95A5.5 5.5 0 007.4 9.2 4.2 4.2 0 007 18.5z"/>',
    "code": '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    "cart": '<path d="M3 4h2.5l2.2 11.2a2 2 0 002 1.6h7.6a2 2 0 002-1.5L21 8H6.2"/><circle cx="10" cy="20.5" r="1.3"/><circle cx="17" cy="20.5" r="1.3"/>',
    "home": '<path d="M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z"/>',
    "db": '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
}
def icon(name, size=24, color="currentColor", sw=1.9):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


class Reel:
    def __init__(self, reel_dir, project_dir, face=(0.51, 0.40), band_zoom=1.6, face_y_full=0.40, face_y_band=0.40,
                 keywords=(), sfx_boost=0.0, brand=None, aspect=None):
        """brand: a preset name (studio, bold, minimal, warm, neon), a path to a brand .json, or None
        ($REELS_BRAND, then <work>/brand.json, then studio). aspect: the source's display width/height; read from
        <work>/source.json (ingest.py) when left out, else 16:9."""
        self.RD, self.P = reel_dir, project_dir
        self.brand = brandkit.load(brand, work_of(reel_dir))
        self.acc_scale = brandkit.accent_scale(self.brand)
        src = source_info(work_of(reel_dir))
        self.aspect = aspect or src.get("aspect") or 16 / 9
        self.W = json.load(open(f"{reel_dir}/words.json"))
        cj = json.load(open(f"{reel_dir}/cuts.json"))
        self.D, self.cuts = cj["total"], cj["cuts"]
        self.face, self.band_zoom, self.fyf, self.fyb = face, band_zoom, face_y_full, face_y_band
        self.keywords = {_norm(k) for k in keywords}
        self.sfx_boost = sfx_boost
        self.lay, self.zooms, self.shakes, self.sfxs = [], [], [], []
        self.html, self.js, self.snaps, self.assets = [], [], [], set()
        self.n, self._last_enter = 0, None
        self.captions_on, self.punch = True, None
        self.cutwins = []          # (t0, t1, band bottom y) of full-screen GIF cutaways: captions drop below the band
        self.screens = []          # screenkit figures (screenshots, screen recordings)
        self.fixes = []            # caption spellings: (normalized words, display text)
        # ---- style hooks: a style kit (a Reel subclass, see reference/components.md) changes these; the default
        # look leaves them alone ----
        self.band, self.morph = list(BAND), MORPH          # where the speaker sits in "split" (x, y, w, h, radius), morph length
        self.cap_y, self.zones = dict(CAP_Y), dict(ZONE)   # caption centre line per layout; figure zones
        self.cap_rule = dict(words=3, chars=17, gap=0.45, cuts=False)  # caption chunking: max words, max characters,
                                                                         # break on pauses (and at jump cuts if cuts=True)
        self.css, self.head = [], []                       # extra CSS, extra <head> tags (fonts)
        self.under, self.over = [], []                     # layers behind the speaker (backgrounds) and over the graphics (bars, grain)
        self.cap_mute = []                                 # (t0, t1) windows with no captions (a full-screen text card says it)
        self.cap_classes = []                              # (t0, t1, css class): captions in a window get the class (dark ink on a light card); lines break at its edges

    # ---------- time helpers ----------
    def at(self, phrase, after=0.0, end=False):
        """reel time where `phrase` starts (end=True: where its last word ends), searching from `after`"""
        p = [_norm(x) for x in phrase.split()]
        ws = [_norm(w["w"]) for w in self.W]
        hits = [k for k in range(len(ws) - len(p) + 1) if ws[k:k + len(p)] == p and self.W[k]["s"] >= after - 1e-6]
        if len(hits) > 1 and after == 0.0:
            when = ", ".join("%.2f" % self.W[k]["s"] for k in hits)
            print(f"  note: {phrase!r} is said {len(hits)} times ({when}); using the first. Pass after= to pick another.")
        for k in hits[:1]:
            return self.W[k + len(p) - 1]["e"] if end else self.W[k]["s"]
        raise SystemExit(f"phrase not found after {after:.2f}s: {phrase!r}")

    def layout_at(self, t):
        cur = "full"
        for tt, l in self.lay:
            if tt <= t + 1e-6: cur = l
        return cur

    def _id(self):
        self.n += 1
        return f"c{self.n}"

    # ---------- timeline ----------
    def layout(self, t, name, sfx=True):
        """switch to "full" or "split" at t (the morph takes 0.62 s and starts at t)"""
        assert name in ("full", "split")
        prev = self.layout_at(t)
        self.lay.append((round(t, 3) if t > 0.01 else -1.0, name)); self.lay.sort()
        if sfx and self.lay and prev != name and t > 0.05: self.sfx(t, "whoosh", -28)

    def zoom(self, t, s, dur=0.0, x=0.0):
        """camera on the speaker: s = scale, dur 0 = hard punch (only at a jump cut), x = sideways reframe (fraction of width)"""
        self.zooms.append([round(t, 3), s, dur, x])

    def push(self, t, s=1.08, dur=1.3):
        """slow eased push-in on the sentence that is the point"""
        self.zoom(t, s, dur)

    def auto_punch(self, amount=0.12, skip=()):
        """alternate punch-in / punch-out at every jump cut (hides the jump). skip: cut times to leave alone"""
        self.punch = (amount, [round(s, 2) for s in skip])

    def shake(self, t, amp=12):
        """impact shake on the graphics layer only, never on the speaker. One or two per reel."""
        self.shakes.append([round(t, 3), amp])

    def sfx(self, t, kind, gain, file=None):
        """kinds: pop, tick, ding, swish, whoosh, riser, impact, shutter, marker, scribble: files from the sound library
        ($SFX_LIB, reference/sound.md); a kind the library lacks falls back to a built-in synth sound.
        file: an absolute path to a one-off sound for this beat"""
        if 0 <= t < self.D:
            self.sfxs.append(dict(t=round(t, 3), kind=kind, gain=round(gain + self.sfx_boost, 1), **({"file": file} if file else {})))

    # ---------- placement ----------
    def _place(self, inner, t0, zone=None, x=None, y=None, scale=1.0, z=5):
        if self.layout_at(t0 + 0.01) == "full" and t0 > 0.05:
            # full-frame on the speaker = captions and subtle camera motion only; it keeps the shot from feeling crowded
            print(f"  note: a piece at {t0:.2f}s sits on the full-frame shot of the speaker. There it's captions and subtle "
                  f"motion only; put graphics in split or a full-screen scene.")
        zone = zone or ("slot" if self.layout_at(t0 + 0.01) == "split" else "top")
        cx, cy = self.zones[zone]
        cx, cy = x if x is not None else cx, y if y is not None else cy
        cid = self._id()
        self.html.append(f'<div class="pos" style="left:{cx}px;top:{cy}px;z-index:{z};transform:translate(-50%,-50%) scale({scale})">'
                         f'<div id="{cid}" class="cmp">{inner(cid)}</div></div>')
        return cid

    def _enter(self, cid, t, kind=None):
        kinds = ["up", "left", "pop", "right", "drop"]
        if kind is None:
            k = (kinds.index(self._last_enter) + 1) % len(kinds) if self._last_enter in kinds else 0
            kind = kinds[k]
        self._last_enter = kind
        if t <= 0.05:      # on screen at frame 0: a settle, never a fade from nothing (scroll-stop frame)
            self.js.append(f'tl.fromTo("#{cid}", {{opacity: .9, y: 8, scale: 1.02}}, {{opacity: 1, y: 0, scale: 1, duration: .5, ease: "power3.out"}}, 0);')
            self.snaps.append(0.0); return
        self.js.append(f'enter("#{cid}", {t:.3f}, "{kind}");')
        self.snaps.append(round(t + 0.7, 2))

    def _exit(self, cid, t):
        if t is not None and t < self.D - 0.05: self.js.append(f'outUp("#{cid}", {t:.3f});')

    # ---------- logos ----------
    def logo_svg(self, name, size=84):
        """an <img> for a logo from the shared library; one-colour SVGs get their brand colour"""
        key = ALIAS.get(name.lower(), name.lower())
        for d in [f"{self.P}/assets/logos"] + LOGO_DIRS:
            for ext in ("svg", "png"):
                for cand in (key, name):
                    f = f"{d}/{cand}.{ext}"
                    if not os.path.exists(f): continue
                    out = f"assets/logos/{key}.{ext}"
                    src = open(f, "rb").read()
                    if ext == "svg" and b"fill=" not in src and b"fill:" not in src:
                        col = BRAND_HEX.get(key, "#111111")
                        src = src.replace(b"<svg", f'<svg fill="{col}"'.encode(), 1)
                    self.assets.add((out, src))
                    return f'<img src="{out}" style="width:{size}px;height:{size}px;object-fit:contain">'
        raise SystemExit(f"no logo for {name!r}: add assets/logos/{key}.svg (fetch_logo.py) or pass a different name")

    def tile(self, name, size=150, label=None, cls="app"):
        lab = f'<div class="tlab">{_esc(label)}</div>' if label else ""
        return (f'<div class="tilew" style="width:{size}px"><div class="{cls}" style="width:{size}px;height:{size}px;'
                f'border-radius:{size * .26:.0f}px">{self.logo_svg(name, int(size * .56))}</div>{lab}</div>')

    # ================= components =================
    def hook(self, text, accent="", until=2.8, zone=None, y=None, size=74):
        """frame-0 title: already on screen at the first frame (a scroll-stop never sees a blank frame).
        It does not have to be something the speaker says: with no strong spoken opener, write a text hook (≤ 8 words,
        taken from the reel's own payoff) and/or cold-open on the payoff figure (any component with t0=0)."""
        def inner(cid):
            return (f'<div class="shade" style="left:-90px;right:-90px;top:-70px;bottom:-70px"></div>'
                    f'<div class="hd wrap" style="width:960px;text-align:center"><span class="tx" style="font-size:{size}px;font-weight:700">{_esc(text)}</span>'
                    + (f' <span class="sf" style="font-size:{size * self.acc_scale:.0f}px">{_esc(accent)}</span>' if accent else "") + '</div>')
        cid = self._place(inner, 0, zone, y=y, z=8)
        self.js.append(f'tl.fromTo("#{cid}", {{opacity: .9, y: 10, scale: 1.03}}, {{opacity: 1, y: 0, scale: 1, duration: .55, ease: "power3.out"}}, 0);')
        self._exit(cid, until)
        self.snaps.append(0.0)
        return cid

    def title(self, text, accent="", t0=0, t1=None, zone=None, x=None, y=None, size=62, enter=None, sfx=True):
        """a label line in the brand's sans plus one accent phrase in its accent font"""
        def inner(cid):
            return (f'<div class="shade" style="left:-60px;right:-60px;top:-50px;bottom:-50px"></div>'
                    f'<div class="hd wrap" style="max-width:980px;text-align:center"><span class="tx" style="font-size:{size}px">{_esc(text)}</span>'
                    + (f' <span class="sf" style="font-size:{size * self.acc_scale:.0f}px">{_esc(accent)}</span>' if accent else "") + '</div>')
        cid = self._place(inner, t0, zone, x, y, z=7)
        self._enter(cid, t0 - 0.1, enter or "up"); self._exit(cid, t1)
        if sfx: self.sfx(t0, "pop", -33)
        return cid

    def logos(self, names, times, t1=None, labels=None, zone=None, x=None, y=None, size=180, gap=30, sfx=True):
        """a row of real logos on white app tiles, each landing on its spoken word (times[i])"""
        labels = labels or [None] * len(names)
        def inner(cid):
            return '<div style="display:flex;gap:%dpx;align-items:flex-start;justify-content:center">%s</div>' % (
                gap, "".join(f'<div class="li" id="{cid}_{k}">{self.tile(n, size, labels[k])}</div>' for k, n in enumerate(names)))
        cid = self._place(inner, times[0], zone, x, y)
        self.js.append(f'tl.set("#{cid}", {{opacity: 1}}, 0);')
        for k, t in enumerate(times):
            if t <= 0.05: self.js.append(f'tl.set("#{cid}_{k}", {{opacity: 1}}, 0);'); continue
            self.js.append(f'pop("#{cid}_{k}", {t - 0.06:.3f}, .4, .5);')
            if sfx and t > 0.05: self.sfx(t, "ding", -30)
        self.snaps.append(round(times[-1] + 0.6, 2))
        self._exit(cid, t1)
        return cid

    def conveyor(self, names, t0, t1, y=None, zone=None, size=130, speed=120, sfx=True):
        """a topic-logo lane: one full-width row of the tools in this story, drifting sideways"""
        reps = names * max(2, math.ceil(1200 / ((size + 24) * len(names))) + 1)
        def inner(cid):
            return (f'<div class="lane" style="width:1080px;height:{size + 20}px"><div class="lanein" id="{cid}_in">'
                    + "".join(f'<div style="flex:none">{self.tile(n, size, cls="app dkt")}</div>' for n in reps) + '</div></div>')
        cid = self._place(inner, t0, zone, x=540, y=y)
        self._enter(cid, t0, "unblur"); self._exit(cid, t1)
        span = (size + 24) * len(names)
        self.js.append(f'driver({t0:.3f}, {(t1 or self.D):.3f}, t => {{ q("#{cid}_in").style.transform = `translateX(${{-((t - {t0:.3f}) * {speed}) % {span}}}px)`; }});')
        if sfx: self.sfx(t0, "swish", -32)
        return cid

    def counter(self, to, t0, land, t1=None, frm=0, prefix="", suffix="", label="", zone=None, x=None, y=None,
                size=230, sfx=True):
        """rolling odometer: tabular digits roll from frm to `to` between t0 and land"""
        digits = len(f"{int(max(abs(to), abs(frm))):d}")
        def inner(cid):
            cols = []
            for p in range(digits - 1, -1, -1):
                strip = "".join(f"<b>{d % 10}</b>" for d in range(11))
                cols.append(f'<span class="dg" data-p="{p}"><span class="strip">{strip}</span></span>')
                if p % 3 == 0 and p > 0: cols.append(f'<span class="cm" data-p="{p}">,</span>')
            lab = f'<div class="clab">{_esc(label)}</div>' if label else ""
            return (f'<div class="lg dk" style="padding:34px 56px 30px;border-radius:44px;text-align:center">'
                    f'<div class="num" style="font-size:{size}px;height:{size * 1.12:.0f}px">'
                    f'<span class="pre">{_esc(prefix)}</span>{"".join(cols)}<span class="suf">{_esc(suffix)}</span></div>{lab}</div>')
        cid = self._place(inner, t0, zone, x, y, z=6)
        self._enter(cid, t0 - 0.35, "pop"); self._exit(cid, t1)
        self.js.append(f'odometer("#{cid}", {frm}, {to}, {t0:.3f}, {land:.3f}, {(t1 or self.D):.3f}, {size * 1.12:.1f});')
        if sfx:
            k = 0
            while t0 + k * 0.12 < land - 0.1:
                self.sfx(t0 + k * 0.12, "tick", -40); k += 1
            self.sfx(land, "ding", -29)
        self.snaps.append(round(land + 0.3, 2))
        return cid

    def notifs(self, items, t1=None, zone=None, x=None, y=None, w=980, scale=1.0, sfx=True):
        """iOS-style banners dropping into a stack. items: [(icon or logo name, title, text, t)]"""
        def inner(cid):
            rows = []
            for k, (ic, ttl, txt, t) in enumerate(items):
                glyph = (f'<div class="nic" style="background:{ACC}">{icon(ic, 40, "__ONACC__", 2.2)}</div>' if ic in ICONS
                         else f'<div class="nic" style="background:#fff">{self.logo_svg(ic, 46)}</div>')
                rows.append(f'<div class="ntf lg dk" id="{cid}_{k}" style="width:{w}px">{glyph}<div class="ntx">'
                            f'<div class="ntt">{_esc(ttl)}<span class="now">now</span></div><div class="nts">{_esc(txt)}</div></div></div>')
            return f'<div class="nstack" style="width:{w}px">{"".join(rows)}</div>'
        cid = self._place(inner, items[0][3], zone, x, y, scale=scale)
        self.js.append(f'tl.set("#{cid}", {{opacity: 1}}, 0);')
        for k, it in enumerate(items):
            if it[3] <= 0.05:
                self.js.append(f'tl.fromTo("#{cid}_{k}", {{opacity: .9, y: -8}}, {{opacity: 1, y: 0, duration: .5, ease: "power3.out"}}, 0);'); continue
            self.js.append(f'tl.fromTo("#{cid}_{k}", {{opacity: 0, y: -60, scale: .96, filter: "blur(8px)"}}, '
                           f'{{opacity: 1, y: 0, scale: 1, filter: "blur(0px)", duration: .45, ease: "back.out(1.4)"}}, {it[3] - 0.05:.3f});')
            if sfx and it[3] > 0.05: self.sfx(it[3], "pop", -30)
        self.snaps.append(round(items[-1][3] + 0.5, 2))
        self._exit(cid, t1)
        return cid

    def window(self, t0, t1=None, kind="claude", title=None, prompt="", lines=(), line_times=None, zone=None, x=None,
               y=None, w=980, h=None, sfx=True):
        """app window: kind claude (spinning Claude mark, prompt types, task lines land), terminal, or browser (URL types)"""
        lines = list(lines)
        h = h or 170 + 70 * (len(lines) + 1)
        line_times = line_times or [t0 + 1.2 + 0.4 * k for k in range(len(lines))]
        def inner(cid):
            if kind == "claude":
                head = f'<svg id="{cid}_m" width="34" height="34" viewBox="0 0 24 24">{CLAUDE_PATH}</svg>{_esc(title or "Claude Code")}'
            elif kind == "browser":
                head = f'<div class="url mono">{icon("lock", 22, "rgba(255,255,255,.7)", 2)}<span id="{cid}_p"></span></div>'
            else:
                head = _esc(title or "Terminal")
            body = (f'<div class="ln on"><span class="pr">›</span> <span id="{cid}_p"></span></div>' if kind != "browser" else "")
            body += "".join(f'<div class="ln" id="{cid}_l{k}">{ln}</div>' for k, ln in enumerate(lines))
            return (f'<div class="lg dk win" style="width:{w}px;height:{h}px"><div class="tbar"><i></i><i></i><i></i>'
                    f'<div class="tl mono">{head}</div></div><div class="code mono">{body}</div></div>')
        cid = self._place(inner, t0, zone, x, y)
        self._enter(cid, t0 - 0.1); self._exit(cid, t1)
        if prompt:
            d = min(1.1, 0.045 * len(prompt))
            self.js.append(f'typeText(q("#{cid}_p"), {json.dumps(prompt)}, {t0 + 0.35:.3f}, {d:.3f});')
            if sfx:
                for k in range(int(d / 0.09)): self.sfx(t0 + 0.35 + k * 0.09, "tick", -41)
        for k, t in enumerate(line_times):
            self.js.append(f'tl.fromTo("#{cid}_l{k}", {{opacity: 0, x: -14}}, {{opacity: 1, x: 0, duration: .32, ease: "power2.out"}}, {t:.3f});')
            if sfx: self.sfx(t, "tick", -36)
        if kind == "claude":
            self.js.append(f'tl.fromTo("#{cid}_m", {{rotation: 0, transformOrigin: "50% 50%"}}, {{rotation: 720, duration: {max(1.5, (line_times[-1] if line_times else t0 + 2) - t0):.2f}, ease: "power1.inOut"}}, {t0 + 0.3:.3f});')
        self.snaps.append(round((line_times[-1] if line_times else t0) + 0.5, 2))
        return cid

    def checklist(self, items, t0, t1=None, title="", zone=None, x=None, y=None, w=980, sfx=True):
        """a list that ticks itself off. items: [(text, t)] with t on the spoken word"""
        def inner(cid):
            rows = "".join(f'<div class="ck" id="{cid}_{k}"><svg width="46" height="46" viewBox="0 0 46 46"><circle cx="23" cy="23" r="20" '
                           f'fill="none" stroke="rgba(255,255,255,.28)" stroke-width="2.5"/><circle class="ckf" cx="23" cy="23" r="20" fill="{ACC}" opacity="0"/>'
                           f'<path class="ckp" d="M13 23.5l6.5 6.5L33 16.5" fill="none" stroke="__ONACC__" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
                           f'<span>{_esc(tx)}</span></div>' for k, (tx, _) in enumerate(items))
            hd = f'<div class="cktitle">{_esc(title)}</div>' if title else ""
            return f'<div class="lg" style="width:{w}px;padding:34px 40px;border-radius:40px">{hd}{rows}</div>'
        cid = self._place(inner, t0, zone, x, y)
        self._enter(cid, t0 - 0.1); self._exit(cid, t1)
        for k, (_, t) in enumerate(items):
            self.js.append(f'tick("#{cid}_{k}", {t:.3f});')
            if sfx: self.sfx(t, "tick", -34)
        if sfx and items: self.sfx(items[-1][1] + 0.25, "ding", -31)
        self.snaps.append(round(items[-1][1] + 0.5, 2))
        return cid

    def hub(self, center, nodes, t0, t1=None, zone=None, x=None, y=None, rx=380, ry=250, center_logo=None, sfx=True):
        """an agent/system wired to real tools: spokes draw out, each node connects on its word, packets flow.
        nodes: [(logo name, label, t)]"""
        N = len(nodes)
        def inner(cid):
            W_, H_ = 2 * rx + 220, 2 * ry + 240
            cx, cy = W_ / 2, H_ / 2
            sp, nd = [], []
            for k, (lg, lab, t) in enumerate(nodes):
                a = -math.pi / 2 + 2 * math.pi * k / N
                nx, ny = cx + rx * math.cos(a), cy + ry * math.sin(a)
                ln, ang = math.hypot(nx - cx, ny - cy), math.degrees(math.atan2(ny - cy, nx - cx))
                sp.append(f'<div class="spoke" id="{cid}_s{k}" style="left:{cx}px;top:{cy}px;width:{ln - 84:.0f}px;transform:rotate({ang:.1f}deg)">'
                          f'<i class="pk"></i><i class="pk"></i></div>')
                nd.append(f'<div class="hnode" id="{cid}_n{k}" style="left:{nx - 75:.0f}px;top:{ny - 75:.0f}px">{self.tile(lg, 150, lab)}</div>')
            core = (self.logo_svg(center_logo, 80) if center_logo else icon("spark", 78, ACC2, 1.8))
            return (f'<div style="position:relative;width:{W_:.0f}px;height:{H_:.0f}px">{"".join(sp)}'
                    f'<svg class="hring" id="{cid}_r" style="left:{cx - 150:.0f}px;top:{cy - 150:.0f}px" width="300" height="300"><circle cx="150" cy="150" r="144" fill="none" stroke="rgba(__ACC2RGB__,.4)" stroke-width="2" stroke-dasharray="3 10"/></svg>'
                    f'<div class="lg hubc" id="{cid}_c" style="left:{cx - 125:.0f}px;top:{cy - 125:.0f}px">{core}<div class="hubl">{_esc(center)}</div></div>'
                    f'{"".join(nd)}</div>')
        cid = self._place(inner, t0, zone, x, y)
        self.js.append(f'hub("#{cid}", {N}, {t0:.3f}, {json.dumps([n[2] for n in nodes])}, {(t1 or self.D):.3f});')
        if sfx:
            self.sfx(t0, "pop", -29); self.sfx(t0 + 0.5, "swish", -32)
            for n in nodes: self.sfx(n[2], "ding", -30)
        self._exit(cid, t1)
        self.snaps.append(round(nodes[-1][2] + 0.6, 2))
        return cid

    def chart(self, t0, t1=None, label="", kind="line", values=None, value_label="", zone=None, x=None, y=None, w=980, sfx=True):
        """line: a curve draws upward with a live dot. bars: values [(label, 0..1)] grow in order"""
        h = 470
        def inner(cid):
            head = (f'<div class="chd"><span class="tx" style="font-size:34px">{_esc(label)}</span>'
                    f'<span class="live"><i></i>{_esc(value_label or "Live")}</span></div>')
            if kind == "bars":
                rows = "".join(f'<div class="brow"><span class="blab">{_esc(vv[0])}</span><span class="btrack"><span class="bfill" id="{cid}_b{k}" style="width:{max(vv[1], .02) * 100:.0f}%"></span></span>'
                               + (f'<span class="bval" id="{cid}_v{k}">{_esc(vv[2])}</span>' if len(vv) > 2 else "") + '</div>'
                               for k, vv in enumerate(values or []))
                body = f'<div style="padding:112px 36px 30px">{rows}</div>'
            else:
                pth = "M0 300 C 80 290, 130 270, 190 272 S 300 220, 360 228 S 470 180, 540 150 S 680 110, 720 70 S 800 30, 828 22"
                body = (f'<svg style="position:absolute;left:36px;top:110px;overflow:visible" width="828" height="330">'
                        f'<defs><linearGradient id="{cid}_g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ACC}" stop-opacity=".4"/><stop offset="1" stop-color="{ACC}" stop-opacity="0"/></linearGradient></defs>'
                        f'<g stroke="rgba(255,255,255,.08)"><path d="M0 80H828M0 170H828M0 260H828"/></g>'
                        f'<path id="{cid}_a" d="{pth} L828 330 L0 330 Z" fill="url(#{cid}_g)" opacity="0"/>'
                        f'<path id="{cid}_l" d="{pth}" stroke="{ACC2}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                        f'<circle id="{cid}_d" cx="828" cy="22" r="11" fill="{ACC2}" opacity="0"/><circle id="{cid}_h" cx="828" cy="22" r="11" fill="none" stroke="{ACC2}" stroke-width="3" opacity="0"/></svg>')
            return f'<div class="lg" style="position:relative;width:{w}px;height:{h if kind != "bars" else 150 + 112 * len(values or [])}px;border-radius:40px">{head}{body}</div>'
        cid = self._place(inner, t0, zone, x, y)
        self._enter(cid, t0 - 0.1); self._exit(cid, t1)
        self.js.append(f'chart("#{cid}", "{kind}", {t0:.3f}, {(t1 or self.D):.3f}, {len(values or [])});')
        if sfx: self.sfx(t0 + 0.35, "swish", -32); self.sfx(t0 + 1.4, "ding", -31)
        self.snaps.append(round(t0 + 1.6, 2))
        return cid

    def image(self, src, t0, t1=None, w=900, h=560, caption="", zone=None, x=None, y=None, video=False, kenburns=True, sfx=True):
        """a screenshot, photo, or a GIF/clip (video=True, an mp4) in a glass frame, with a slow Ken Burns drift"""
        name = os.path.basename(src)
        self.assets.add((f"assets/media/{name}", open(src, "rb").read()))
        def inner(cid):
            media = (f'<video id="{cid}_v" src="assets/media/{name}" muted playsinline data-start="{t0 - 0.2:.3f}" '
                     f'data-duration="{((t1 or self.D) - t0 + 0.6):.3f}" data-track-index="{10 + self.n}"></video>' if video
                     else f'<img id="{cid}_v" src="assets/media/{name}">')
            cap = f'<div class="icap">{_esc(caption)}</div>' if caption else ""
            return f'<div class="lg imgf" style="width:{w}px;height:{h}px">{media}</div>{cap}'
        cid = self._place(inner, t0, zone, x, y)
        self._enter(cid, t0 - 0.1); self._exit(cid, t1)
        if kenburns: self.js.append(f'tl.fromTo("#{cid}_v", {{scale: 1.0}}, {{scale: 1.08, duration: {((t1 or self.D) - t0 + .5):.2f}, ease: "none"}}, {t0 - 0.1:.3f});')
        if sfx: self.sfx(t0, "pop", -30)
        return cid

    def gif(self, name, t0, t1=None, style="card", w=760, tilt=-3, caption="", zone=None, x=None, y=None, sfx=True):
        """a reaction GIF/meme (mp4 from fetch_gif.py, in $REELS_GFX/_library/gifs or a path), on the joke's word.
        style "card": a tilted glass sticker in the graphics slot (split layout). Keep it 1-2.5 s.
        style "cut":  a full-screen cutaway (GIF as a band over a blurred copy of itself), 0.8-1.8 s, captions stay on top.
        The clip plays once from its start; the beat is clamped to the clip's length so it never freezes."""
        src = name if os.path.exists(name) else f"{GFX}/_library/gifs/{name}.mp4"
        if not os.path.exists(src): raise SystemExit(f"no gif {name!r}: run fetch_gif.py \"<search>\" --sheet, look, then --pick N --slug {name}")
        import subprocess
        pr = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                             "stream=width,height:format=duration", "-of", "json", src], capture_output=True, text=True)
        meta = json.loads(pr.stdout); vw, vh = meta["streams"][0]["width"], meta["streams"][0]["height"]
        clip = float(meta["format"]["duration"])
        t1 = min(t1 if t1 is not None else t0 + 2.0, t0 + clip - 0.05, self.D)
        fn = os.path.basename(src)
        self.assets.add((f"assets/media/{fn}", open(src, "rb").read()))
        cid = self._id()
        vid = lambda k, extra="": (f'<video id="{cid}_{k}" src="assets/media/{fn}" muted playsinline data-start="{t0 - 0.05:.3f}" '
                                   f'data-duration="{t1 - t0 + 0.4:.3f}" data-track-index="{40 + self.n * 2 + (k == "b")}" {extra}></video>')
        if style == "cut":
            bh = round(1080 * vh / vw)
            self.cutwins.append((t0, t1, 960 + bh / 2))
            self.html.append(f'<div id="{cid}" class="gcut"><div class="gfill">{vid("b")}</div>'
                             f'<div class="gband" style="height:{bh}px;margin-top:{-bh / 2:.0f}px">{vid("a")}</div></div>')
            self.js.append(f'tl.set("#{cid}", {{opacity: 1}}, {t0:.3f}); tl.set("#{cid}", {{opacity: 0}}, {t1:.3f});'
                           f'tl.fromTo("#{cid} .gband", {{scale: 1.12}}, {{scale: 1, duration: .35, ease: "power3.out"}}, {t0:.3f});')
            if sfx: self.sfx(t0, "whoosh", -29); self.sfx(t1, "swish", -33)
        else:
            h = round(w * vh / vw)
            cap = f'<div class="icap">{_esc(caption)}</div>' if caption else ""
            inner = lambda c: (f'<div style="transform:rotate({tilt}deg)"><div class="lg imgf gcard" style="width:{w}px;height:{h}px">'
                               f'{vid("a")}</div>{cap}</div>')
            # reuse placement, but the element id must be the one the videos were named after
            zone = zone or ("slot" if self.layout_at(t0 + 0.01) == "split" else "top")
            cx, cy = self.zones[zone]; cx, cy = x if x is not None else cx, y if y is not None else cy
            self.html.append(f'<div class="pos" style="left:{cx}px;top:{cy}px;z-index:9;transform:translate(-50%,-50%)">'
                             f'<div id="{cid}" class="cmp">{inner(cid)}</div></div>')
            self.js.append(f'tl.fromTo("#{cid}", {{opacity: 0, scale: .6, rotation: {-tilt * 2}}}, {{opacity: 1, scale: 1, rotation: 0, duration: .45, ease: "back.out(1.8)"}}, {t0 - 0.08:.3f});'
                           f'tl.to("#{cid}", {{opacity: 0, scale: .85, duration: .22, ease: "power2.in"}}, {t1 - 0.22:.3f});')
            if sfx: self.sfx(t0, "pop", -29)
        self.snaps.append(round(t0 + 0.5, 2))
        return cid

    def mark(self, t0, t1=None, name="claude", size=260, zone=None, x=None, y=None, label="", sfx=True):
        """bring a brand mark to life: it lands, spins while 'thinking', settles (name: a logo from the library)"""
        def inner(cid):
            svg = (f'<svg id="{cid}_m" width="{size}" height="{size}" viewBox="0 0 24 24">{CLAUDE_PATH}</svg>' if name == "claude"
                   else f'<div id="{cid}_m">{self.logo_svg(name, size)}</div>')
            lab = f'<div class="tx" style="font-size:40px;margin-top:22px;text-align:center">{_esc(label)}</div>' if label else ""
            return f'<div class="glow" style="width:{size * 1.9:.0f}px;height:{size * 1.9:.0f}px"></div>{svg}{lab}'
        cid = self._place(inner, t0, zone, x, y)
        self.js.append(f'pop("#{cid}", {t0 - .05:.3f}, .3, .7);')
        self.js.append(f'tl.fromTo("#{cid}_m", {{rotation: -90, transformOrigin: "50% 50%"}}, {{rotation: 360, duration: {min(3.0, ((t1 or self.D) - t0)):.2f}, ease: "expo.out"}}, {t0:.3f});')
        self._exit(cid, t1)
        if sfx: self.sfx(t0, "pop", -29); self.sfx(t0 + .1, "swish", -33)
        self.snaps.append(round(t0 + 0.8, 2))
        return cid

    def rows(self, title, cols, rows, t0, t1=None, zone=None, x=None, y=None, w=1000, sfx=True):
        """a live table (CRM, leads, orders). rows: [([cell, ...], status or None, t)]; the last column can be a status pill"""
        def inner(cid):
            hd = "".join(f'<span>{_esc(c)}</span>' for c in cols)
            body = "".join(f'<div class="trow" id="{cid}_{k}">' + "".join(f'<span>{_esc(c)}</span>' for c in cells)
                           + (f'<span><b class="pill">{_esc(st)}</b></span>' if st else "") + '</div>' for k, (cells, st, t) in enumerate(rows))
            return (f'<div class="lg dk" style="width:{w}px;padding:30px 34px;border-radius:40px"><div class="ttl">{_esc(title)}<span class="live"><i></i>Live</span></div>'
                    f'<div class="thead">{hd}</div>{body}</div>')
        cid = self._place(inner, t0, zone, x, y)
        self._enter(cid, t0 - 0.1); self._exit(cid, t1)
        for k, (_, _, t) in enumerate(rows):
            self.js.append(f'tl.fromTo("#{cid}_{k}", {{opacity: 0, y: 16, filter: "blur(6px)"}}, {{opacity: 1, y: 0, filter: "blur(0px)", duration: .4, ease: "power3.out"}}, {t:.3f});')
            if sfx: self.sfx(t, "tick", -35)
        self.snaps.append(round(rows[-1][2] + 0.5, 2))
        return cid

    def screen(self, src, t0, t1=None, w=1000, h=620, frame="browser", url="", title="", zone=None, x=None, y=None,
               tilt=(6, -12, -1.5), fit="width", data=None, enter="tilt", media_start=0.0, dark=False, sfx=True):
        """a screenshot or screen recording in a browser/window/phone frame, in 3D. Returns the Screen: chain
        .zoom(t, find=...), .highlight(), .circle(), .arrow(), .box(), .focus(), .popout(), .scroll(), .flat()...
        (reference/screens.md). Capture web pages with capture.mjs; read your own captures with ocr."""
        sid = self._id()
        sc = Screen(sid, src, t0, t1, w=w, h=h, frame=frame, url=url, title=title, fit=fit, tilt=tilt, data=data,
                    media_start=media_start, D=self.D, track=60 + 2 * len(self.screens), sfx=sfx, dark=dark)
        self.assets.add((sc.rel, open(src, "rb").read()))
        zone = zone or ("slot" if self.layout_at(t0 + 0.01) == "split" else "top")
        cx, cy = self.zones[zone]
        self.html.append(sc.html(x if x is not None else cx, y if y is not None else cy))
        sc.enter(t0 - 0.1, enter)
        if t1 is not None and t1 < self.D - 0.05: sc.exit(t1)
        self.screens.append(sc)
        self.snaps.append(round(t0 + 0.9, 2))
        return sc

    def flash(self, t, color="__ACCLRGB__", sfx=True):
        """a soft light hit across the frame, for the one dramatic beat of a section"""
        cid = self._id()
        self.html.append(f'<div id="{cid}" class="flash" style="background:radial-gradient(circle at 50% 42%,rgba({color},.55),rgba({color},0) 62%)"></div>')
        self.js.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: .07}}, {t:.3f}); tl.to("#{cid}", {{opacity: 0, duration: .32, ease: "power2.out"}}, {t + .07:.3f});')
        if sfx: self.sfx(t, "impact", -30)

    def raw(self, html, js=""):
        """escape hatch for a bespoke figure: html is placed in the graphics layer, js runs in the timeline scope"""
        self.html.append(html)
        if js: self.js.append(js)

    def spell(self, phrase, text):
        """fix how the recognizer spelled something, in the captions only ("note ion" -> "Notion", "get a repo" ->
        "GitHub repo"). Timing, r.at() and the QA transcript keep the words as heard."""
        self.fixes.append(([_norm(x) for x in phrase.split()], text))

    # ---------- captions ----------
    def _chunks(self):
        out, cur = [], []
        for k, w in enumerate(self.W):
            gap = w["s"] - self.W[k - 1]["e"] if k else 0
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            cr = self.cap_rule
            at_cut = cr.get("cuts") and k and any(self.W[k - 1]["s"] < c <= w["s"] + 0.05 for c in self.cuts)
            at_cut = at_cut or (k and any(self.W[k - 1]["s"] < x <= w["s"] + 0.05 for a, b, _ in self.cap_classes for x in (a, b)))
            if cur and (len(cur) >= cr["words"] or chars > cr["chars"] or cur[-1]["w"][-1:] in ".,?!" or gap > cr["gap"] or at_cut):
                out.append(cur); cur = []
            cur.append(w)
        if cur: out.append(cur)
        return out

    def _caption_html(self):
        ch = [c for c in self._chunks() if not any(a - 0.05 <= c[0]["s"] < b for a, b in self.cap_mute)]
        html, js = [], []
        idx = {id(w): k for k, w in enumerate(self.W)}
        heard, disp = [_norm(w["w"]) for w in self.W], {}
        for p, text in self.fixes:
            for k in range(len(heard) - len(p) + 1):
                if heard[k:k + len(p)] == p:
                    tail = self.W[k + len(p) - 1]["w"][-1:]
                    disp[k] = text + (tail if tail in ".,?!" else "")
                    for j in range(k + 1, k + len(p)): disp[j] = ""
        prev_t1 = 0.0
        for k, c in enumerate(ch):
            # a chunk never starts before the previous one is done, and stays up until its last word has had
            # 0.18 s on screen (fast speech: "go" at 0.42 s used to vanish because the next chunk took over at 0.42)
            t0 = max(0.0, c[0]["s"] - 0.06, prev_t1, self.cap_rule.get("start", 0.0) if k == 0 else 0.0)
            nxt = ch[k + 1][0]["s"] - 0.06 if k + 1 < len(ch) else self.D
            t1 = max(min(nxt, c[-1]["e"] + 0.7), c[-1]["s"] + 0.18, t0 + 0.2)
            t1 = min([t1] + [a for a, b in self.cap_mute if a > t0 + 0.1])     # a full-screen card cuts the line off
            t1 = min([t1] + [x for a, b, _ in self.cap_classes for x in (a, b) if x > t0 + 0.1])   # and so does a class change
            prev_t1 = t1
            lay = self.layout_at(t0 + 0.2)
            y = self.cap_y[lay]
            for a, b, bottom in self.cutwins:
                if a - 0.05 <= t0 + 0.1 < b: y = min(1480, max(y, round(bottom + 78)))
            spans, cw = [], [w for w in c if disp.get(idx[id(w)], w["w"])]
            for j, w in enumerate(cw):
                shown = disp.get(idx[id(w)], w["w"])
                txt = shown.rstrip(",") if shown.endswith(",") else shown
                key = (_norm(w["w"]) in self.keywords or any(_norm(x) in self.keywords for x in shown.split())
                       or bool(re.match(r"^\$?\d", w["w"])))
                spans.append(f'<span class="cw{" ck2" if key else ""}" id="w{k}_{j}">{_esc(txt)}</span>')
            extra = "".join(f" {c}" for a, b, c in self.cap_classes if a - 0.05 <= t0 + 0.05 < b)
            html.append(f'<div class="cap{extra}" id="cap{k}" style="top:{y - 39}px">{" ".join(spans)}</div>')
            js.append(f'capIn("#cap{k}", {t0:.3f}, {t1:.3f}, {json.dumps([round(w["s"], 3) for w in cw])}, {k});')
        return "".join(html), "\n".join(js)

    # ---------- build ----------
    def build(self):
        zooms = sorted(self.zooms)
        if self.punch:
            amt, skip = self.punch
            on = False
            for c in self.cuts:
                if round(c, 2) in skip: continue
                on = not on
                zooms.append([round(c, 3), 1 + amt if on else 1.0, 0, 0])
            zooms.sort()
        if not self.lay or self.lay[0][0] > 0: self.lay.insert(0, (-1.0, "full"))
        for t, l in self.lay:
            if t > 0: self.snaps.append(round(t + self.morph + 0.1, 2))
        cap_html, cap_js = self._caption_html() if self.captions_on else ("", "")
        cap_js = brandkit.caption_js(self.brand) + "\n" + cap_js        # a caption style redefines capIn (the later one wins)
        sk_css = sk_js = ""
        if self.screens:
            sk_css, sk_js = screen_kit()
            self.js.extend(sc.js() for sc in self.screens)
            for sc in self.screens:
                for t, kind, gain in sc.sfx: self.sfx(t, kind, gain)
        C = dict(D=self.D, lay=self.lay, zoom=zooms, shake=self.shakes, face=self.face, bz=self.band_zoom,
                 fyf=self.fyf, fyb=self.fyb, band=self.band, morph=self.morph, ar=round(self.aspect, 5))
        css = [brandkit.caption_css(self.brand)] + self.css
        html = (TEMPLATE.replace("</style></head>", sk_css + "\n".join(css) + "</style>" + "\n".join(self.head) + "</head>", 1)
                .replace('  <div id="cam">', "".join(self.under) + '  <div id="cam">', 1)
                .replace("\n__CAPS__", "\n" + "".join(self.over) + "__CAPS__", 1)
                .replace("<script>\nconst C = __C__;", (f"<script>{sk_js}</script>\n" if sk_js else "") + "<script>\nconst C = __C__;", 1)
                .replace("__D__", f"{self.D:.3f}").replace("__C__", json.dumps(C))
                .replace("__FX__", "\n".join(self.html)).replace("__CAPS__", cap_html)
                .replace("__JS__", "\n".join(self.js) + "\n" + cap_js))
        html = brandkit.apply(html, self.brand)
        os.makedirs(self.P, exist_ok=True)
        open(f"{self.P}/index.html", "w").write(html)
        for path, data in self.assets:
            os.makedirs(os.path.dirname(f"{self.P}/{path}"), exist_ok=True)
            open(f"{self.P}/{path}", "wb").write(data)
        sfx = sorted(self.sfxs, key=lambda e: e["t"])
        json.dump({"total": self.D, "sections": [], "zooms": [], "fade": False, "sfx": sfx},
                  open(f"{self.RD}/plan.json", "w"), indent=1)
        snaps = sorted({s for s in self.snaps if 0 <= s < self.D})
        open(f"{self.RD}/snaps.txt", "w").write(",".join(f"{s:.2f}" for s in snaps))
        print(f"reel {self.D:.2f}s | {self.n} pieces | {len(sfx)} sfx | {len(zooms)} camera events | layouts {self.lay} | brand {self.brand.get('name')}")
        print("snapshot at:", ",".join(f"{s:.2f}" for s in snaps))


CLAUDE_PATH = ('<path fill="#D97757" d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.2549h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z"/>')

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
__FONTLINK__
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden;background:#000}
#root{position:relative;width:1080px;height:1920px;overflow:hidden;font-family:"__SANS__",sans-serif;color:#fff;-webkit-font-smoothing:antialiased}
.abs{position:absolute}
.tx{font-family:"__SANS__",sans-serif;font-weight:600;letter-spacing:-.015em;text-shadow:0 2px 18px rgba(0,0,0,.55),0 1px 3px rgba(0,0,0,.45)}
.sf{font-family:"__SERIF__",serif;font-style:italic;font-weight:400;color:__ACC2__;text-shadow:0 2px 18px rgba(0,0,0,.5),0 1px 2px rgba(0,0,0,.35)}
.mono{font-family:"__MONO__",monospace}
.hd{line-height:1.08}.hd.wrap{white-space:normal}.hd > span + span{margin-left:.2em}
.shade{position:absolute;pointer-events:none;border-radius:50%;background:radial-gradient(closest-side,rgba(0,0,0,.6),rgba(0,0,0,.32) 55%,rgba(0,0,0,0));filter:blur(22px);z-index:-1}
.pos{position:absolute}
.cmp{position:relative;opacity:0}
/* camera */
#frost{position:absolute;inset:-80px;opacity:0;overflow:hidden}
#frostv{position:absolute;filter:blur(44px) saturate(1.25) brightness(.42)}
#frostv video,#camv video{width:100%;height:100%;display:block;object-fit:fill}
#slotbg{position:absolute;inset:0;opacity:0;pointer-events:none;
  background:radial-gradient(120% 60% at 50% 0%,rgba(__ACCRGB__,.10),rgba(0,0,0,0) 60%),linear-gradient(180deg,rgba(0,0,0,.25),rgba(0,0,0,0) 30%,rgba(0,0,0,.35))}
#cam{position:absolute;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.5)}
#camv{position:absolute}
#camrim{position:absolute;inset:0;border-radius:inherit;pointer-events:none;box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.24)}
#capline{position:absolute;left:84px;right:84px;height:2px;top:952px;opacity:0;background:linear-gradient(90deg,rgba(__ACC2RGB__,0),rgba(__ACC2RGB__,.75),rgba(__ACC2RGB__,0))}
#fx{position:absolute;inset:0}
.flash{position:absolute;inset:0;opacity:0;pointer-events:none;mix-blend-mode:screen;z-index:20}
/* liquid glass, calm */
.lg{position:relative;isolation:isolate;overflow:hidden;--tint:.34;
  background:linear-gradient(165deg,rgba(255,255,255,.10),rgba(255,255,255,.03) 45%,rgba(255,255,255,.05)),rgba(16,16,20,var(--tint));
  -webkit-backdrop-filter:blur(16px) saturate(150%);backdrop-filter:blur(16px) saturate(150%);
  box-shadow:0 18px 44px rgba(0,0,0,.32),0 2px 6px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.22)}
.lg::before{content:"";position:absolute;inset:0;border-radius:inherit;padding:1.5px;pointer-events:none;
  background:linear-gradient(140deg,rgba(255,255,255,.44),rgba(255,255,255,.07) 35%,rgba(255,255,255,0) 60%,rgba(255,255,255,.13));
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude}
.lg.dk{--tint:.5}
/* captions: the "soft" style by default (each word rises out of a blur as it is spoken, keywords in the accent
   font); brand.py adds the brand's size, weight and caption style after this */
.cap{position:absolute;left:30px;right:30px;text-align:center;opacity:0;z-index:30;
  font-family:"__SANS__";font-weight:600;font-size:70px;line-height:1.1;letter-spacing:-.01em;white-space:nowrap;
  text-shadow:0 2px 16px rgba(0,0,0,.6),0 0 2px rgba(0,0,0,.55),0 1px 1px rgba(0,0,0,.35)}
.cw{display:inline-block;opacity:0}
.ck2{font-family:"__SERIF__",serif;font-style:italic;font-weight:400;font-size:1.3em;line-height:.85;color:__ACC2__;letter-spacing:0}
/* tiles */
.tilew{display:flex;flex-direction:column;align-items:center}
.app{background:#fff;display:flex;align-items:center;justify-content:center;box-shadow:0 14px 34px rgba(0,0,0,.35),inset 0 0 0 1px rgba(0,0,0,.06)}
.app.dkt{background:rgba(255,255,255,.95)}
.tlab{margin-top:14px;font-weight:600;font-size:32px;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.li{opacity:0}
.lane{overflow:hidden;-webkit-mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}
.lanein{display:flex;gap:24px;padding:10px 0}
/* counter */
.num{display:flex;align-items:flex-start;justify-content:center;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.12;letter-spacing:-.03em;text-shadow:0 4px 24px rgba(0,0,0,.35)}
.dg{display:inline-block;overflow:hidden;height:1.12em;width:.66em;position:relative;-webkit-mask:linear-gradient(transparent,#000 14%,#000 86%,transparent)}
.strip{position:absolute;left:0;top:0;display:flex;flex-direction:column;width:100%}
.strip b{height:1.12em;display:block;text-align:center;font-weight:700}
.cm{display:inline-block;width:.3em}
.pre,.suf{color:__ACC2__}
.clab{margin-top:8px;font-weight:500;font-size:38px;letter-spacing:.04em;color:rgba(255,255,255,.72)}
/* notifications */
.nstack{display:flex;flex-direction:column;gap:18px}
.ntf{display:flex;align-items:center;gap:26px;padding:26px 30px;border-radius:40px;opacity:0}
.nic{width:96px;height:96px;border-radius:26px;flex:none;display:flex;align-items:center;justify-content:center}
.ntx{flex:1;min-width:0}.ntt{font-weight:700;font-size:38px;display:flex;justify-content:space-between}
.now{font-weight:500;font-size:28px;color:rgba(255,255,255,.5)}.nts{font-weight:500;font-size:33px;color:rgba(255,255,255,.75);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* windows */
.win{border-radius:30px}
.tbar{height:70px;display:flex;align-items:center;gap:12px;padding:0 26px;border-bottom:1px solid rgba(255,255,255,.08)}
.tbar i{width:16px;height:16px;border-radius:50%;background:rgba(255,255,255,.22)}
.tbar .tl{margin-left:12px;font-size:30px;color:rgba(255,255,255,.8);display:flex;align-items:center;gap:12px;flex:1}
.url{flex:1;height:44px;border-radius:22px;background:rgba(255,255,255,.07);display:flex;align-items:center;gap:10px;padding:0 18px;font-size:24px}
.code{padding:22px 32px;font-size:34px;line-height:1.75;color:rgba(255,255,255,.9)}
.code .ln{opacity:0;white-space:nowrap}.code .ln.on{opacity:1}
.pr{color:__ACC2__}.ok{color:__OK__}.dim{color:rgba(255,255,255,.5)}
/* checklist */
.cktitle{font-weight:700;font-size:46px;margin-bottom:18px}
.ck{display:flex;align-items:center;gap:24px;font-weight:600;font-size:42px;padding:14px 0;color:rgba(255,255,255,.55)}
/* hub */
.spoke{position:absolute;height:3px;margin-top:-1.5px;transform-origin:0 50%;background:linear-gradient(90deg,rgba(255,255,255,.12),rgba(255,255,255,.4))}
.pk{position:absolute;top:50%;width:13px;height:13px;margin:-6.5px 0 0 -6.5px;border-radius:50%;opacity:0;background:__ACCL__;box-shadow:0 0 14px 5px rgba(__ACCRGB__,.6)}
.hnode{position:absolute;opacity:0}
.hubc{position:absolute;width:260px;height:260px;border-radius:74px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;opacity:0}
.hubl{font-weight:700;font-size:34px;text-align:center;line-height:1.1;padding:0 14px}
.hring{position:absolute;opacity:0}
/* charts, tables, images */
.chd{position:absolute;left:36px;right:36px;top:30px;display:flex;align-items:center;justify-content:space-between}
.live{display:inline-flex;align-items:center;gap:9px;font-size:28px;font-weight:700;color:__OK__;margin-left:16px}
.live i{width:11px;height:11px;border-radius:50%;background:__OK__;box-shadow:0 0 10px __OK__}
.brow{display:flex;align-items:center;gap:22px;height:112px}.blab{width:230px;font-weight:600;font-size:38px}
.bval{width:230px;text-align:right;font-weight:700;font-size:40px;color:__ACC2__;opacity:0}
.btrack{flex:1;height:26px;border-radius:13px;background:rgba(255,255,255,.08);position:relative;overflow:hidden}
.bfill{position:absolute;left:0;top:0;bottom:0;border-radius:9px;background:linear-gradient(90deg,__ACC2__,__ACC__);transform-origin:0 50%}
.ttl{font-weight:700;font-size:46px;display:flex;align-items:center;margin-bottom:16px}
.thead,.trow{display:grid;grid-template-columns:1.4fr 1fr 1fr;align-items:center;gap:14px}
.thead{font-weight:600;font-size:28px;color:rgba(255,255,255,.5);padding:8px 0;border-bottom:1px solid rgba(255,255,255,.1)}
.trow{font-weight:600;font-size:35px;padding:20px 0;border-bottom:1px solid rgba(255,255,255,.06);opacity:0}
.pill{font-size:27px;font-weight:700;padding:8px 18px;border-radius:16px;background:rgba(__ACCRGB__,.2);color:__ACCL__}
.imgf{border-radius:36px}.imgf img,.imgf video{width:100%;height:100%;object-fit:cover;display:block}
.icap{margin-top:18px;text-align:center;font-weight:600;font-size:38px;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.gcut{position:absolute;inset:0;opacity:0;z-index:25;background:#000;overflow:hidden}
.gfill{position:absolute;inset:-60px;filter:blur(40px) brightness(.45) saturate(1.2)}.gfill video{width:100%;height:100%;object-fit:cover}
.gband{position:absolute;left:0;right:0;top:50%;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.5)}.gband video{width:100%;height:100%;object-fit:cover;display:block}
.gcard{border-radius:30px}
.glow{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(closest-side,rgba(__ACCRGB__,.35),rgba(__ACCRGB__,0));z-index:-1}
</style></head>
<body><div id="root" data-composition-id="reel" data-start="0" data-duration="__D__" data-width="1080" data-height="1920">
  <div id="frost"><div id="frostv"><video id="vfrost" src="base.mp4" muted playsinline data-start="0" data-duration="__D__" data-track-index="0"></video></div></div>
  <div id="slotbg"></div>
  <div id="cam"><div id="camv"><video id="vcam" src="base.mp4" muted playsinline data-start="0" data-duration="__D__" data-track-index="1"></video></div><div id="camrim"></div></div>
  <div id="capline"></div>
  <div id="fx">
__FX__
  </div>
__CAPS__
</div>
<script>
const C = __C__;
const tl = gsap.timeline({ paused: true });
const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
function inUp(el, t, o = {}) { tl.fromTo(el, { opacity: 0, y: o.y ?? 30, x: o.x ?? 0, scale: o.s ?? .96, filter: "blur(12px)" }, { opacity: 1, y: 0, x: 0, scale: 1, filter: "blur(0px)", duration: o.d ?? .6, ease: "power3.out" }, t); }
function outUp(el, t, d = .4) { tl.to(el, { opacity: 0, y: -16, filter: "blur(10px)", duration: d, ease: "power2.in" }, t); }
function pop(el, t, s = .6, d = .5) { tl.fromTo(el, { opacity: 0, scale: s }, { opacity: 1, scale: 1, duration: d, ease: "back.out(1.7)" }, t); }
function enter(el, t, k) {   // varied entrances: no two pieces in a row arrive the same way
  if (k === "up") return inUp(el, t);
  if (k === "left") return inUp(el, t, { x: -70, y: 0 });
  if (k === "right") return inUp(el, t, { x: 70, y: 0 });
  if (k === "drop") return tl.fromTo(el, { opacity: 0, y: -70, rotation: -2, filter: "blur(10px)" }, { opacity: 1, y: 0, rotation: 0, filter: "blur(0px)", duration: .6, ease: "back.out(1.5)" }, t);
  if (k === "unblur") return tl.fromTo(el, { opacity: 0, filter: "blur(20px)", scale: 1.04 }, { opacity: 1, filter: "blur(0px)", scale: 1, duration: .6, ease: "power2.out" }, t);
  return pop(el, t, .82, .55);
}
function draw(el, t, d = .6, ease = "power2.inOut", to = 0) { const n = el.getTotalLength(); gsap.set(el, { strokeDasharray: n + " " + n }); tl.fromTo(el, { strokeDashoffset: n }, { strokeDashoffset: n * to, duration: d, ease }, t); }
function typeText(el, s, t, d) { tl.set(el, { textContent: "" }, 0); for (let i = 1; i <= s.length; i++) tl.set(el, { textContent: s.slice(0, i) }, t + d * i / s.length); }
function loop(el, from, to, t0, t1, period, delay = 0) { const n = Math.max(1, Math.floor((t1 - t0 - delay) / period)); tl.fromTo(el, from, { ...to, duration: period, repeat: n - 1, ease: to.ease || "none" }, t0 + delay); }
function driver(t0, t1, fn) { const p = { v: 0 }; fn(t0); tl.to(p, { v: 1, duration: Math.max(.01, t1 - t0), ease: "none", onUpdate: () => fn(t0 + p.v * (t1 - t0)) }, t0); }
function bez(x1, y1, x2, y2) { return x => { if (x <= 0) return 0; if (x >= 1) return 1; let u = x;
  for (let i = 0; i < 12; i++) { const bx = 3*(1-u)*(1-u)*u*x1 + 3*(1-u)*u*u*x2 + u*u*u - x, dx = 3*(1-u)*(1-u)*x1 + 6*(1-u)*u*(x2-x1) + 3*u*u*(1-x2); if (Math.abs(dx) < 1e-6) break; u = Math.max(0, Math.min(1, u - bx/dx)); }
  return 3*(1-u)*(1-u)*u*y1 + 3*(1-u)*u*u*y2 + u*u*u; }; }
const zE = bez(.72, 0, .22, 1.10), mE = bez(.76, 0, .24, 1);

// ---------- camera: layout morph (full <-> split), zoom / punch / reframe, all pure functions of t ----------
function layAt(t) { let m = 0; for (const [tt, l] of C.lay) { if (tt > t) break; const g = l === "split" ? 1 : 0, u = (t - tt) / C.morph; m = u >= 1 ? g : m + (g - m) * mE(u); } return m; }
function zoomAt(t) { let s = 1, x = 0; for (const [tt, ss, d, xx] of C.zoom) { if (tt > t) break; if (d === 0) { s = ss; x = xx; } else { const u = (t - tt) / d, k = u >= 1 ? 1 : zE(u); s += (ss - s) * k; x += (xx - x) * k; } } return [s, x]; }
function shakeAt(t) { let dx = 0, dy = 0; for (const [tt, a] of C.shake) { const u = t - tt; if (u < 0 || u > .32) continue; const e = Math.exp(-u / .09); dx += a * e * Math.sin(u * 83); dy += a * .7 * e * Math.cos(u * 61); } return [dx, dy]; }
const cam = q("#cam"), camv = q("#camv"), camrim = q("#camrim"), frost = q("#frost"), frostv = q("#frostv"), fx = q("#fx"), slotbg = q("#slotbg"), capline = q("#capline");
const [BX, BY, BW, BH, BR] = C.band;
function camera(t) {
  const m = layAt(t), [zs, zx] = zoomAt(t);
  const L = 0 + (BX - 0) * m, T = 0 + (BY - 0) * m, Wd = 1080 + (BW - 1080) * m, Ht = 1920 + (BH - 1920) * m;
  cam.style.left = L + "px"; cam.style.top = T + "px"; cam.style.width = Wd + "px"; cam.style.height = Ht + "px"; cam.style.borderRadius = (BR * m) + "px";
  const AR = C.ar || 16 / 9;
  let vh = (1920 + (BH * C.bz - 1920) * m) * zs; vh = Math.max(vh, Ht, Wd / AR);   // portrait sources still cover the band
  const vw = vh * AR, fy = C.fyf + (C.fyb - C.fyf) * m;
  let lx = Wd * (.5 + zx) - vw * C.face[0], ty = Ht * fy - vh * C.face[1];
  lx = Math.min(0, Math.max(Wd - vw, lx)); ty = Math.min(0, Math.max(Ht - vh, ty));
  camv.style.left = lx + "px"; camv.style.top = ty + "px"; camv.style.width = vw + "px"; camv.style.height = vh + "px";
  frost.style.opacity = m; slotbg.style.opacity = m; camrim.style.opacity = m; capline.style.opacity = m * .9;
  const fh = Math.max(2080, 1240 / AR), fw = fh * AR; frostv.style.width = fw + "px"; frostv.style.height = fh + "px"; frostv.style.left = (620 - fw * C.face[0]) + "px"; frostv.style.top = "0px";
  const [sx, sy] = shakeAt(t); fx.style.transform = `translate(${sx}px, ${sy}px)`;
}
driver(0, C.D, camera);

// ---------- captions: chunk rises in, each word lights on its onset ----------
function capIn(id, t0, t1, ws, k) {
  // visibility is two instant sets that never overlap; the entrance only moves, so out-of-order seeks
  // (parallel render workers) can't leave a short chunk stuck on screen
  // (a chunk that starts at 0 must not also get a hide-at-0: two sets at the same instant resolve unreliably)
  if (t0 > 0.001) tl.set(id, { opacity: 0 }, 0);
  tl.set(id, { opacity: 1 }, t0); tl.set(id, { opacity: 0 }, t1);
  // each word: one tween only (opacity, rise, unblur), never longer than the time until the chunk ends
  ws.forEach((s, j) => { const w = id.replace("#cap", "#w") + "_" + j, a = Math.max(t0, s - .04);
    tl.fromTo(w, { opacity: 0, y: 12, filter: "blur(10px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: Math.max(.05, Math.min(.28, t1 - a - .02)), ease: "power2.out" }, a); });
  // the chunk blurs softly out at its end (the only tween on the chunk's filter)
  const d = Math.min(.14, (t1 - t0) * .3), last = ws[ws.length - 1] + .3;
  if (t1 - d > last) tl.fromTo(id, { filter: "blur(0px)" }, { filter: "blur(8px)", duration: d, ease: "power1.in" }, t1 - d);
}
// ---------- odometer: each place rolls only while every lower place is rolling past 9 ----------
function odometer(id, frm, to, t0, land, t1, cell) {
  const places = qa(id + " .dg"), commas = qa(id + " .cm"), big = Math.abs(to) >= 10000;
  const ease = big ? bez(.65, 0, .35, 1) : bez(.16, 1, .3, 1);
  const val = t => frm + (to - frm) * ease(Math.max(0, Math.min(1, (t - t0) / (land - t0))));
  driver(t0 - .4, t1, t => { const v = val(t), dv = Math.abs(v - val(t - 1 / 30));
    const lead = Math.max(1, Math.floor(Math.log10(Math.max(1, v))) + 1);
    places.forEach(el => { const p = +el.dataset.p, P = Math.pow(10, p), rem = v % P;
      const pos = Math.floor(v / P) % 10 + Math.max(0, Math.min(1, rem - (P - 1)));
      el.firstChild.style.transform = `translateY(${-pos * cell}px)`;
      const sp = dv / P; el.firstChild.style.filter = sp > .5 ? `blur(${Math.min(7, sp * 1.6).toFixed(1)}px)` : "none";
      const on = p < lead ? 1 : Math.max(0, Math.min(1, (v - P * .92) / (P * .08))); el.style.width = (on * .66) + "em"; el.style.opacity = on; });
    commas.forEach(el => { const p = +el.dataset.p, on = v >= Math.pow(10, p) ? 1 : 0; el.style.width = (on * .3) + "em"; el.style.opacity = on; });
  });
  tl.fromTo(id + " .num", { scale: 1 }, { scale: 1.04, duration: .14, yoyo: true, repeat: 1, ease: "sine.inOut" }, land);
}
function tick(id, t) {
  tl.to(id + " .ckf", { opacity: 1, duration: .18 }, t); draw(q(id + " .ckp"), t + .02, .3, "power2.out");
  tl.to(id, { color: "#fff", duration: .2 }, t); tl.fromTo(id + " svg", { scale: .7 }, { scale: 1, duration: .4, ease: "back.out(2.5)" }, t);
}
function hub(id, N, t0, times, t1) {
  tl.set(id, { opacity: 1 }, 0);
  tl.fromTo(id + "_c", { opacity: 0, scale: .8, filter: "blur(14px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: .7, ease: "expo.out" }, t0);
  tl.to(id + "_r", { opacity: 1, duration: .6 }, t0 + .2); tl.fromTo(id + "_r", { rotation: 0, transformOrigin: "50% 50%" }, { rotation: 140, duration: t1 - t0, ease: "none" }, t0);
  for (let k = 0; k < N; k++) {
    tl.fromTo(id + "_s" + k, { scaleX: 0 }, { scaleX: 1, duration: .5, ease: "power3.inOut" }, t0 + .45 + k * .08);
    tl.fromTo(id + "_n" + k, { opacity: 0, scale: .7 }, { opacity: .35, scale: .9, duration: .45, ease: "power3.out" }, t0 + .6 + k * .08);
    tl.to(id + "_n" + k, { opacity: 1, scale: 1, duration: .5, ease: "back.out(1.8)" }, times[k] - .06);
    qa(id + "_s" + k + " .pk").forEach((pk, j) => loop(pk, { left: "4%", opacity: 0 }, { left: "96%", opacity: 1, ease: "power1.in" }, times[k] + .1, t1, 1.25, j * .62));
  }
}
function chart(id, kind, t0, t1, n) {
  if (kind === "bars") { for (let k = 0; k < n; k++) { tl.fromTo(id + "_b" + k, { scaleX: 0 }, { scaleX: 1, duration: .9, ease: "power3.out" }, t0 + .4 + k * .6);
    if (q(id + "_v" + k)) tl.fromTo(id + "_v" + k, { opacity: 0, x: 14 }, { opacity: 1, x: 0, duration: .35, ease: "power2.out" }, t0 + .9 + k * .6); } return; }
  draw(q(id + "_l"), t0 + .3, 1.2, "power2.out"); tl.to(id + "_a", { opacity: 1, duration: .8 }, t0 + .6);
  pop(id + "_d", t0 + 1.4, .2, .35); loop(id + "_h", { attr: { r: 11 }, opacity: .8 }, { attr: { r: 34 }, opacity: 0 }, t0 + 1.5, t1, 1.0);
}
__JS__
function lens() {
  const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", 0); svg.setAttribute("height", 0); svg.style.position = "absolute"; document.body.appendChild(svg);
  qa(".lg").forEach((el, k) => {
    const w = el.offsetWidth, h = el.offsetHeight; if (!w || !h) return;
    const r = Math.min(parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0, h / 2, w / 2), b = Math.min(20, h * .22), S = 1;
    const c = document.createElement("canvas"); c.width = w * S; c.height = h * S; const g = c.getContext("2d"), im = g.createImageData(c.width, c.height);
    for (let py = 0; py < c.height; py++) for (let px = 0; px < c.width; px++) {
      const x = (px + .5) / S - w / 2, y = (py + .5) / S - h / 2, ix = Math.abs(x) - (w / 2 - r), iy = Math.abs(y) - (h / 2 - r);
      const d = -(Math.hypot(Math.max(ix, 0), Math.max(iy, 0)) + Math.min(Math.max(ix, iy), 0) - r);
      let dx = 0, dy = 0;
      if (d >= 0 && d < b) { let nx, ny; if (ix > 0 && iy > 0) { const l = Math.hypot(ix, iy); nx = ix / l; ny = iy / l; } else if (ix > iy) { nx = 1; ny = 0; } else { nx = 0; ny = 1; }
        const m = Math.pow(1 - d / b, 2.4); dx = -Math.sign(x) * nx * m; dy = -Math.sign(y) * ny * m; }
      const i = (py * c.width + px) * 4; im.data[i] = 128 + dx * 127; im.data[i + 1] = 128 + dy * 127; im.data[i + 2] = 128; im.data[i + 3] = 255;
    }
    g.putImageData(im, 0, 0);
    const f = document.createElementNS(NS, "filter"); f.setAttribute("id", "lgf" + k); f.setAttribute("color-interpolation-filters", "sRGB");
    ["x", "y"].forEach(a => f.setAttribute(a, "0")); ["width", "height"].forEach(a => f.setAttribute(a, "100%"));
    const fi = document.createElementNS(NS, "feImage"); fi.setAttribute("href", c.toDataURL()); fi.setAttribute("x", 0); fi.setAttribute("y", 0);
    fi.setAttribute("width", w); fi.setAttribute("height", h); fi.setAttribute("preserveAspectRatio", "none"); fi.setAttribute("result", "m");
    const dm = document.createElementNS(NS, "feDisplacementMap"); dm.setAttribute("in", "SourceGraphic"); dm.setAttribute("in2", "m");
    dm.setAttribute("scale", Math.min(32, h * .22)); dm.setAttribute("xChannelSelector", "R"); dm.setAttribute("yChannelSelector", "G");
    f.appendChild(fi); f.appendChild(dm); svg.appendChild(f);
    const bf = `url(#lgf${k}) blur(${el.classList.contains("dk") ? 20 : 16}px) saturate(150%)`;
    el.style.backdropFilter = bf; el.style.webkitBackdropFilter = bf;
  });
}
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(lens);
tl.to({}, { duration: C.D }, 0);
window.__timelines = window.__timelines || {};
window.__timelines["reel"] = tl;
</script></body></html>'''
