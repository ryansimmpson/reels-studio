# scenes.py: full-screen explainer scenes ("takeovers") for reelkit reels.
# A couple of times in a longer reel, take the entire screen for an animation that explains the point with shapes,
# logos, text and imagery, while the speaker's voice carries on underneath.
#
#   from scenes import Scenes
#   sc = Scenes(r)                                  # r = reelkit Reel
#   A = sc.takeover(t0, t1)                         # returns the panel id; build its inside with r.raw(...)
#   r.raw(f'<div id="{A}" class="tko"><div class="tkg"></div>' + sc.row(240, sc.head("Three tools", "I use daily"), A + "_t") + ... + '</div>')
#   sc.show(f"#{A}_t", t)                           # fade-up (or kind="pop") a piece on its word
#
# The panel is a frosted dark layer (z 3) over the speaker in the graphics layer; captions (z 30) stay on top. Run the
# underlying layout as "full" so captions sit at y 1300, and keep scene content in y 220-1220 (clear of the caption
# line and the 380 px bottom safe zone). Give each piece an id and its own entrance; nothing idles.
CSS = '''
.tko{position:absolute;inset:0;z-index:3;opacity:0;overflow:hidden;background:rgba(11,8,6,.9);-webkit-backdrop-filter:blur(48px) saturate(1.2);backdrop-filter:blur(48px) saturate(1.2)}
.tkg{position:absolute;inset:0;background:radial-gradient(ellipse 85% 40% at 50% 0%,rgba(__ACCRGB__,.15),rgba(__ACCRGB__,0) 70%),radial-gradient(rgba(255,255,255,.05) 1.6px,transparent 1.7px) 0 0/34px 34px}
.ab{position:absolute}
.tki{display:inline-block;opacity:0}
.tkh{font-family:"__SANS__",sans-serif;font-weight:600;font-size:58px;white-space:nowrap}
.tkh .sf{font-size:1.42em;margin-left:.15em}
'''


class Scenes:
    def __init__(self, reel):
        self.r = reel
        reel.raw(f"<style>{CSS.replace('1.42em', f'{reel.acc_scale:.2f}em')}</style>")

    def takeover(self, t0, t1, sfx=True):
        """a full-screen scene from t0 to t1 (fades in 0.12 s early, out over the last 0.3 s); returns its id"""
        r = self.r
        cid = r._id()
        r.js.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: .32, ease: "power2.out"}}, {t0 - 0.12:.3f});')
        r.js.append(f'tl.to("#{cid}", {{opacity: 0, duration: .3, ease: "power2.in"}}, {t1 - 0.3:.3f});')
        if sfx: r.sfx(t0 - 0.1, "whoosh", -29); r.sfx(t1 - 0.28, "swish", -34)
        r.snaps.append(round(t0 + 0.5, 2))
        return cid

    @staticmethod
    def head(text, accent=""):
        """scene title: the brand's sans at 58 px plus an accent phrase (put it in a row)"""
        return f'<div class="tkh"><span class="tx">{text}</span>' + (f'<span class="sf">{accent}</span>' if accent else "") + '</div>'

    @staticmethod
    def row(top, inner, cid=None, h=None):
        """a full-width row, centred without transforms (GSAP owns transform on the inner piece). The inner piece
        starts hidden (.tki): reveal it with show(), or tl.set(opacity 1) when its children enter on their own"""
        hh = ";height:%dpx" % h if h else ""
        idattr = ' id="%s"' % cid if cid else ""
        return (f'<div class="ab" style="left:0;right:0;top:{top}px;text-align:center{hh}">'
                f'<div class="tki"{idattr}>{inner}</div></div>')

    def show(self, sel, t, kind="up"):
        """enter a piece on its word: "up" (rise out of a blur) or "pop" (scale with overshoot)"""
        if kind == "pop":
            self.r.js.append(f'tl.fromTo("{sel}", {{opacity: 0, scale: .7}}, {{opacity: 1, scale: 1, duration: .45, ease: "back.out(1.9)"}}, {t - 0.08:.3f});')
        else:
            self.r.js.append(f'tl.fromTo("{sel}", {{opacity: 0, y: 30, filter: "blur(8px)"}}, {{opacity: 1, y: 0, filter: "blur(0px)", duration: .45, ease: "power3.out"}}, {t - 0.1:.3f});')
