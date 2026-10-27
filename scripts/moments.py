import json, os, re, sys
# moments.py <work> [--keep 12-15,17-18]
#
# Finds reel candidates in a long-form talking-head video. It does the counting; you do the judging.
#   <work>/words.jsonl  word timestamps (tools/stt2)        required
#   <work>/env.txt      10 ms loudness envelope (tools/audio) optional, adds an energy score
#   <work>/takes.json   {"keep": [[first_word, last_word], ...]}  optional: only these word ranges are considered
#                       (the clean takes, when a long-form edit already threw out the flubs)
# Writes <work>/reels/moments.md: every sentence numbered with its time, then the ranked candidates with
# a score breakdown. Read the whole sentence list yourself before trusting the ranking.
#
# --keep 12-15,17-18 prints the keep.json for those sentences (drop a sentence to cut it out of the reel):
#   python3 moments.py "$WORK" --keep 12-15,17-18 > "$WORK/reels/01-slug/keep.json"
SP = sys.argv[1]
W = [json.loads(l) for l in open(f"{SP}/words.jsonl") if l.strip()]
E = [float(x) for x in open(f"{SP}/env.txt")] if os.path.exists(f"{SP}/env.txt") else None

kept = list(range(len(W)))
if os.path.exists(f"{SP}/takes.json"):
    kept = [i for k in json.load(open(f"{SP}/takes.json"))["keep"] for i in range(k[0], k[1] + 1)]

# ---------- sentences over the kept words ----------
FINAL = ".?!"
sents, cur = [], []
for n, i in enumerate(kept):
    cur.append(i)
    w = W[i]["w"].strip()
    nxt_gap = (W[kept[n + 1]]["s"] - W[i]["e"]) if n + 1 < len(kept) else 9
    jump = n + 1 < len(kept) and kept[n + 1] != i + 1          # a dropped take sits between these words
    if w[-1:] in FINAL or (jump and w[-1:] in ",") or nxt_gap > 1.6:
        sents.append(cur); cur = []
if cur: sents.append(cur)

def runs(idx):
    """consecutive word-index runs -> keep ranges"""
    out = []
    for i in idx:
        if out and i == out[-1][1] + 1: out[-1][1] = i
        else: out.append([i, i])
    return out

def speech_len(idx):
    """rough reel length: word spans, with pauses squeezed to 0.35 s the way reel_cut.py will"""
    t = 0.0
    for a, b in zip(idx, idx[1:] + [None]):
        t += W[a]["e"] - W[a]["s"]
        if b is not None: t += min(max(0, W[b]["s"] - W[a]["e"]), 0.35)
    return t

def text(idx): return " ".join(W[i]["w"].strip() for i in idx)
def mmss(t): return f"{int(t // 60)}:{t % 60:05.2f}"

# ---------- features ----------
HOOK = re.compile(r"\b(you|your|most|nobody|no one|everyone|stop|never|secret|truth|mistake|wrong|actually|problem|"
                  r"why|how|what if|imagine|here's|biggest|best|worst|only|free|money|million|billion|thousand|"
                  r"hours?|seconds?|minutes?|days?|cost|pennies|cheaper|faster|replace|fired|hire|hiring)\b", re.I)
STORY = re.compile(r"\b(i built|i made|i own|i started|i tried|i learned|we chose|last year|my business|my client|my first|"
                   r"when i|i realized|i didn't|i don't|i used to)\b", re.I)
DANGLING = re.compile(r"^(and|so|but|because|that|this|it|they|which|also|or|then|um|uh)\b", re.I)
TRAIL = re.compile(r"\b(and|so|but|because|the|a|to|of|with|um|uh|like)\W*$", re.I)
FILLER = re.compile(r"^(um|uh|uh-huh|hmm),?$", re.I)
NUM = re.compile(r"(\$?\d[\d,.]*\s?(%|k|m|b)?|\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|billion|half)\b)", re.I)

def proper_nouns(idx):
    out = set()
    for a, b in zip(idx, idx[1:]):
        w = W[b]["w"].strip().strip(".,?!")
        prev = W[a]["w"].strip()
        if w[:1].isupper() and prev[-1:] not in FINAL and w not in ("I", "I'm", "I've", "I'll", "I'd"):
            out.add(w)
    return out

gmean = None
if E:
    _srt = sorted(E); VOICED = max(-60.0, min(-30.0, _srt[int(0.9 * (len(_srt) - 1))] - 20.0))   # same rule as reel_cut.py
    voiced = [x for x in E if x > VOICED]
    gmean = sum(voiced) / max(1, len(voiced))
def energy(idx):
    if not E: return 0.0
    a, b = int(W[idx[0]]["s"] * 100), int(W[idx[-1]]["e"] * 100)
    v = [x for x in E[a:b] if x > VOICED]
    return (sum(v) / len(v) - gmean) if v else -6.0

S = []
for k, idx in enumerate(sents):
    t = text(idx)
    S.append(dict(k=k, idx=idx, t0=W[idx[0]]["s"], t1=W[idx[-1]]["e"], text=t, len=speech_len(idx),
                  hook=len(HOOK.findall(t)), story=bool(STORY.search(t)), num=len(NUM.findall(t)),
                  names=proper_nouns(idx), dangling=bool(DANGLING.match(t)), trail=bool(TRAIL.search(t)),
                  fill=sum(1 for i in idx if FILLER.match(W[i]["w"].strip())), q=t.rstrip().endswith("?")))

# ---------- --keep mode ----------
if "--keep" in sys.argv:
    spec = sys.argv[sys.argv.index("--keep") + 1]
    chosen = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        chosen += list(range(int(a), int(b or a) + 1))
    idx = [i for k in chosen for i in S[k]["idx"]]
    print(json.dumps({"sentences": spec, "keep": runs(idx), "text": text(idx), "est_len": round(speech_len(idx), 1)}, indent=1))
    sys.exit(0)

# ---------- candidate windows ----------
LO, HI, SWEET = 18.0, 62.0, (28.0, 48.0)
cands = []
for i in range(len(S)):
    tot, j = 0.0, i
    while j < len(S) and tot + S[j]["len"] <= HI:
        tot += S[j]["len"] + 0.3
        if tot >= LO:
            win = S[i:j + 1]
            first, last = win[0], win[-1]
            names = set().union(*[s["names"] for s in win])
            sc = {}
            sc["hook"] = min(3, first["hook"]) * 1.2 + (1.5 if first["q"] else 0) + (1.2 if first["story"] else 0) \
                         + (1.0 if first["num"] else 0) + (0.8 if first["len"] <= 7 else 0)
            sc["standalone"] = -2.5 if first["dangling"] else 1.0
            sc["payoff"] = (-2.0 if last["trail"] else 0.8) + (0.6 if last["len"] <= 9 else 0)
            sc["density"] = min(3.0, sum(s["hook"] for s in win) * 0.25 + sum(s["num"] for s in win) * 0.5 + len(names) * 0.35)
            sc["story"] = 1.0 if any(s["story"] for s in win) else 0
            sc["energy"] = max(-2, min(2, sum(energy(s["idx"]) for s in win) / len(win) * 0.6))
            sc["length"] = 1.0 if SWEET[0] <= tot <= SWEET[1] else (0 if tot < SWEET[0] else -0.5)
            sc["filler"] = -0.6 * sum(s["fill"] for s in win)
            cands.append(dict(a=i, b=j, len=tot, score=sum(sc.values()), sc=sc, names=sorted(names)))
        j += 1

cands.sort(key=lambda c: -c["score"])
picked = []
for c in cands:
    overlap = any(min(c["b"], p["b"]) - max(c["a"], p["a"]) + 1 > 0.35 * (c["b"] - c["a"] + 1) for p in picked)
    if not overlap: picked.append(c)
    if len(picked) == 15: break

os.makedirs(f"{SP}/reels", exist_ok=True)
out = [f"# Reel candidates for {os.path.basename(SP.rstrip('/'))}", "",
       f"{len(S)} sentences from {len(kept)} kept words. Lengths are rough reel lengths after pause trimming.", "",
       "## Ranked windows", ""]
for n, c in enumerate(picked, 1):
    win = S[c["a"]:c["b"] + 1]
    br = " ".join(f"{k} {v:+.1f}" for k, v in c["sc"].items())
    out.append(f"### {n}. sentences {c['a']}-{c['b']}  ~{c['len']:.0f}s  score {c['score']:.1f}  [{mmss(win[0]['t0'])}]")
    out.append(f"{br}" + (f"  | names: {', '.join(c['names'][:8])}" if c["names"] else ""))
    out.append(f"> **Opens:** {win[0]['text']}")
    out.append(f"> **Ends:** {win[-1]['text']}")
    out.append("")
out += ["## Every sentence", "", "`[n] source-time ~len | text` (D = starts with a dangling word, T = trails off, F = filler)", ""]
for s in S:
    flags = ("D" if s["dangling"] else "") + ("T" if s["trail"] else "") + ("F" if s["fill"] else "")
    out.append(f"[{s['k']}] {mmss(s['t0'])} ~{s['len']:.1f}s {flags:3}| {s['text']}")
open(f"{SP}/reels/moments.md", "w").write("\n".join(out) + "\n")
print(f"{len(S)} sentences, {len(cands)} windows -> {SP}/reels/moments.md")
for n, c in enumerate(picked[:8], 1):
    print(f"{n:2}. s{c['a']}-{c['b']} ~{c['len']:.0f}s score {c['score']:.1f} | {S[c['a']]['text'][:90]}")
