import os, sys
# reel_template.py <reel dir> <graphics project dir>
# An example reel script. Copy it to <reel dir>/reel.py and rewrite every beat for your moment: each time comes from
# r.at("spoken words") in YOUR transcript, so the phrases below are placeholders, not something to keep.
# The example moment: a creator explains how they film a month of content in one day (about 40 s).
# Declare layouts first: a component picks its zone from the layout at its start.
sys.path.insert(0, os.path.expanduser("~/.claude/skills/reels-studio/scripts"))
from reelkit import Reel

RD, P = sys.argv[1], sys.argv[2]
r = Reel(RD, P, brand=None,                                   # None: $REELS_BRAND, <work>/brand.json, else "studio"
         keywords=["month", "one day", "batch", "posts"],     # 3-5 words that carry the reel: captions highlight them
         face=(0.51, 0.40))                                   # where the face sits in the source frame (0-1)
at = r.at

# ---------- layout: switch every 6-10 s; graphics live in split, the hook and payoff lines stay full-frame ----------
r.layout(0, "split")                                   # frame 0 is already split and packed (scroll-stop)
r.layout(at("here's the thing") - 0.3, "full")
r.layout(at("first I") - 0.3, "split")
r.layout(at("and that's how") - 0.3, "full")
r.auto_punch(0.12)                                     # punch in/out on every jump cut
r.push(at("and that's how"), 1.10, 1.4)                # the payoff line

# ---------- hook: a text hook plus a figure on frame 0 ----------
r.hook("A month of content", "in one day", until=at("here's the thing") - 0.4, y=262)
r.counter(30, 0.0, 1.2, at("here's the thing") - 0.4, label="posts", y=620)

# ---------- full: the context line (captions and camera only on this shot) ----------
r.gif("mind-blown", at("every single day"), style="cut")   # a meme cutaway (fetch it first: fetch_gif.py, pipeline.md 3b)

# ---------- the steps, each ticking off on its word ----------
r.checklist([("Plan every idea", at("plan")), ("Film it all at once", at("film")), ("Edit in batches", at("edit"))],
            at("first I"), at("the tools") - 0.2, title="The batch day", y=520)

# ---------- the tools they name: real logos on their words ----------
r.title("The", "tools", at("the tools") - 0.1, at("and that's how") - 0.4, y=300)
r.logos(["notion", "capcut", "canva"], [at("notion"), at("capcut"), at("canva")], t1=at("and that's how") - 0.4, y=620)

r.build()
