"""brand: the look of a reel (colours, fonts, caption style) as data, so any creator can plug in their own.

A brand is a JSON file (see brands/*.json and reference/brand.md). reelkit builds every reel with colour and font
tokens (__ACC__, __SANS__ ...) and swaps them for the brand's values when it writes index.html.

    from brand import load
    b = load("bold")                      # a preset name from brands/, a path to a .json, or None
    b = load(None)                        # $REELS_BRAND, else <work>/brand.json, else the "studio" preset

Fields (anything left out comes from the studio preset):
  colors.accent        fills: icon chips, check marks, chart areas, screen annotations
  colors.accent_text   accent words and keywords, numbers, chart lines (readable on dark footage)
  colors.accent_light  glows, data packets, status pills
  colors.on_accent     icons drawn on an accent fill
  colors.success       live dots, "ok" lines
  colors.marker        the highlighter on screenshots
  fonts.sans / sans_weights           every label, title and caption (a Google Fonts family)
  fonts.accent / accent_italic / accent_weight / accent_scale   the one accent phrase in a title or hook
  fonts.mono / mono_weights           code windows and URLs
  captions.style       soft (words rise out of a blur, keywords in the accent font) | bold (big caps, words pop) |
                       box (karaoke: the spoken word sits on an accent box)
  captions.size / weight / upper      caption type
"""
import copy, json, os

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS = os.path.join(SKILL, "brands")
DEFAULT = "studio"


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _read(name_or_path):
    p = name_or_path
    if not (p.endswith(".json") or os.path.sep in p):
        p = os.path.join(BRANDS, f"{p}.json")
    if not os.path.exists(p):
        names = sorted(f[:-5] for f in os.listdir(BRANDS) if f.endswith(".json"))
        raise SystemExit(f"no brand {name_or_path!r}: use one of {', '.join(names)} or a path to a brand .json")
    return json.load(open(p))


def load(spec=None, work=None):
    """spec: a preset name, a path, a dict, or None ($REELS_BRAND, then <work>/brand.json, then the default)"""
    base = _read(DEFAULT)
    if spec is None:
        spec = os.environ.get("REELS_BRAND")
        if not spec and work and os.path.exists(os.path.join(work, "brand.json")):
            spec = os.path.join(work, "brand.json")
    if spec is None: return base
    over = spec if isinstance(spec, dict) else _read(spec)
    if isinstance(over, dict) and over.get("extends"): base = _merge(base, _read(over["extends"]))
    return _merge(base, over)


def _rgb(hexc):
    h = hexc.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def font_link(b):
    f = b["fonts"]
    fams = []
    def fam(name, weights=None, italic=False):
        n = name.replace(" ", "+")
        w = sorted(set(weights or [400]))
        if italic: fams.append(f"family={n}:ital,wght@" + ";".join([f"0,{x}" for x in w] + [f"1,{x}" for x in w]))
        else: fams.append(f"family={n}:wght@" + ";".join(str(x) for x in w))
    fam(f["sans"], f.get("sans_weights", [500, 600, 700, 800]))
    if f["accent"] != f["sans"]: fam(f["accent"], [f.get("accent_weight", 400)], f.get("accent_italic", True))
    if f["mono"] not in (f["sans"], f["accent"]): fam(f["mono"], f.get("mono_weights", [500, 700]))
    return ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            f'<link href="https://fonts.googleapis.com/css2?{"&".join(fams)}&display=block" rel="stylesheet">')


def tokens(b):
    c, f = b["colors"], b["fonts"]
    return {
        "__FONTLINK__": font_link(b),
        "__ACCRGB__": _rgb(c["accent"]), "__ACC2RGB__": _rgb(c["accent_text"]), "__ACCLRGB__": _rgb(c["accent_light"]),
        "__MARKRGB__": _rgb(c.get("marker", c["accent_text"])),
        "__ACC__": c["accent"], "__ACC2__": c["accent_text"], "__ACCL__": c["accent_light"],
        "__ONACC__": c["on_accent"], "__OK__": c["success"],
        "__SANS__": f["sans"], "__SERIF__": f["accent"], "__MONO__": f["mono"],
    }


def apply(text, b):
    for k, v in tokens(b).items(): text = text.replace(k, v)
    return text


def accent_scale(b):
    return float(b["fonts"].get("accent_scale", 1.42))


# ---------- caption styles ----------
CAP_BOLD_JS = """
// caption style "bold": big caps, each word pops in on its onset, the line cuts out clean
function capIn(id, t0, t1, ws, k) {
  if (t0 > 0.001) tl.set(id, { opacity: 0 }, 0);
  tl.set(id, { opacity: 1 }, t0); tl.set(id, { opacity: 0 }, t1);
  ws.forEach((s, j) => { const w = id.replace("#cap", "#w") + "_" + j, a = Math.max(t0, s - .03);
    tl.fromTo(w, { opacity: 0, scale: .62, y: 10 }, { opacity: 1, scale: 1, y: 0, duration: Math.max(.05, Math.min(.18, t1 - a - .02)), ease: "back.out(1.7)" }, a); });
}
"""
CAP_BOX_JS = """
// caption style "box": the whole line shows, the word being spoken sits on an accent box
function capIn(id, t0, t1, ws, k) {
  if (t0 > 0.001) tl.set(id, { opacity: 0 }, 0);
  tl.set(id, { opacity: 1 }, t0); tl.set(id, { opacity: 0 }, t1);
  tl.fromTo(id, { y: 14, scale: .97 }, { y: 0, scale: 1, duration: Math.min(.18, (t1 - t0) * .5), ease: "power3.out" }, t0);
  ws.forEach((s, j) => { const w = id.replace("#cap", "#w") + "_" + j, el = q(w), key = el && el.classList.contains("ck2");
    const on = Math.max(t0, s - .03), off = j + 1 < ws.length ? Math.max(on + .05, ws[j + 1] - .03) : t1;
    tl.set(w, { opacity: 1 }, t0);
    tl.set(w, { backgroundColor: "rgba(__ACCRGB__,1)", color: "__ONACC__" }, on);
    tl.set(w, { backgroundColor: "rgba(__ACCRGB__,0)", color: key ? "__ACC2__" : "#ffffff" }, off); });
}
"""


def caption_css(b):
    c = b["captions"]
    st = c.get("style", "soft")
    css = [f'.cap{{font-size:{c.get("size", 70)}px;font-weight:{c.get("weight", 600)}{";text-transform:uppercase" if c.get("upper") else ""}}}',
           f'.sf{{font-style:{"italic" if b["fonts"].get("accent_italic", True) else "normal"};font-weight:{b["fonts"].get("accent_weight", 400)}}}']
    if st == "bold":
        css.append('.cap .cw{margin:0 .05em}.cap{letter-spacing:0;line-height:1.04;text-shadow:0 4px 0 rgba(0,0,0,.45),0 0 22px rgba(0,0,0,.55),0 1px 2px rgba(0,0,0,.6)}'
                   '.ck2{font-family:"__SANS__",sans-serif;font-style:normal;font-weight:900;font-size:1.08em;line-height:1;color:__ACC2__;letter-spacing:0}')
    elif st == "box":
        css.append('.cap{line-height:1.25}.cap .cw{padding:.02em .16em .06em;border-radius:.2em;margin:0 -.04em}'
                   '.ck2{font-family:"__SANS__",sans-serif;font-style:normal;font-weight:inherit;font-size:1em;line-height:inherit;color:__ACC2__;letter-spacing:inherit}')
    else:
        if not b["fonts"].get("accent_italic", True):
            css.append(f'.ck2{{font-style:normal;font-weight:{b["fonts"].get("accent_weight", 400)}}}')
    return "\n".join(css)


def caption_js(b):
    return {"bold": CAP_BOLD_JS, "box": CAP_BOX_JS}.get(b["captions"].get("style", "soft"), "")
