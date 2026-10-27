import json, math, re, sys
# reel_cut.py <work> <reel dir>
#
# Turns a list of kept word ranges into envelope-snapped cuts that never clip a word, with tightened pauses.
#   in:  <work>/words.jsonl, <work>/env.txt, <reel>/keep.json  {"keep": [[first_word, last_word(, start(, end))], ...]}
#        Ranges play in the order listed, so a reel may reorder lines. A third/fourth value pins a cut time
#        (source seconds) where the word timestamps are known to be off.
#   out: <reel>/edl.json    frame segments for render_reel
#        <reel>/words.json  every kept word on the reel timeline: [{"i", "w", "s", "e"}], for captions and beats
#        <reel>/cuts.json   reel times of every jump cut (auto punch-ins)
# "validation problems" must print 0. A clipped word ending is the most noticeable mistake a reel can have.
SP, RD = sys.argv[1], sys.argv[2]
W = [json.loads(l) for l in open(f"{SP}/words.jsonl") if l.strip()]
RAW = [float(x) for x in open(f"{SP}/env.txt")]
KJ = json.load(open(f"{RD}/keep.json"))
KEEP = KJ["keep"]
FR = 1001 / 30000
n = len(RAW)
SRC_END = n / 100 - 0.2

# Levels are relative to this recording's own speech, so quiet and loud mics cut the same way. REF is the 90th
# percentile of the 10 ms envelope (loud speech); a studio lav at REF -24 dB gives ACT -44 / DECAY -51.
# keep.json "levels": {"act": -44, "decay": -51} pins them by hand.
_srt = sorted(RAW)
REF = _srt[int(0.9 * (len(_srt) - 1))]
ACT = max(-60.0, min(-30.0, REF - 20.0))   # clearly speaking
DECAY = ACT - 7.0                          # the voice has faded into the room
ACT, DECAY = KJ.get("levels", {}).get("act", ACT), KJ.get("levels", {}).get("decay", DECAY)
QUIET = ACT - 2.0                          # a cut point must be at least this quiet
GAP_MERGE = 30                # gaps under 0.30 s are inside a phrase
PAD_TAIL, PAD_LEAD = 0.24, 0.10   # reels: a little tighter than long-form (0.30 / 0.15), still after the full decay
MIN_SIL = 0.40                # pauses longer than this get shortened (long-form: 0.80)
END_HOLD = 0.35               # room after the last word (long-form holds 1 s for a fade; reels loop)
# keep.json "pace": {"pad_tail", "pad_lead", "min_sil"} tightens a reel that feels slow. Shorter tails also drop the
# inhale before the next line.
PACE = KJ.get("pace", {})
PAD_TAIL, PAD_LEAD, MIN_SIL = PACE.get("pad_tail", PAD_TAIL), PACE.get("pad_lead", PAD_LEAD), PACE.get("min_sil", MIN_SIL)

# ---------- speech phrases from the envelope ----------
runs, i = [], 0
while i < n:
    if RAW[i] > ACT:
        j = i
        while j < n and RAW[j] > ACT: j += 1
        runs.append([i, j]); i = j
    else: i += 1
utts = []
for r in runs:
    if utts and r[0] - utts[-1][1] < GAP_MERGE: utts[-1][1] = r[1]
    else: utts.append(list(r))
utts = [u for u in utts if u[1] - u[0] >= 7]
core = [u[:] for u in utts]
for k, u in enumerate(utts):
    lo = core[k - 1][1] if k > 0 else 0
    hi = core[k + 1][0] if k + 1 < len(core) else n
    while u[0] - 1 > lo and RAW[u[0] - 1] > DECAY: u[0] -= 1
    while u[1] < hi - 1 and RAW[u[1]] > DECAY: u[1] += 1
U = [(a / 100, b / 100) for a, b in utts]

def fr(t): return max(0, min(n - 1, int(round(t * 100))))
def local_min(t0, t1): return min(range(fr(t0), fr(t1) + 1), key=lambda i: RAW[i]) / 100
def utt_index_ending_after(t):
    for k, (a, b) in enumerate(U):
        if b > t: return k
    return len(U) - 1

def dip_cut(j, horizon=0.5):
    """cut inside continuous speech after word j: first near-silent valley after the word's middle"""
    t = W[j]["e"]
    lo = fr(max(W[j]["s"] + 0.5 * (W[j]["e"] - W[j]["s"]), t - 0.15)); hi = fr(t + horizon)
    peak = max(RAW[fr(W[j]["s"]):fr(t) + 1] or [RAW[fr(t)]])
    def valley(g):
        best = g
        for h in range(g, min(g + 15, hi)):
            if RAW[h] > RAW[g] + 8: break
            if RAW[h] < RAW[best]: best = h
        return best / 100
    for deep in (True, False):
        for g in range(lo + 1, hi):
            ok = RAW[g] <= QUIET if deep else RAW[g] <= peak - 9
            if ok and RAW[g] <= RAW[g - 1] and RAW[g] <= RAW[g + 1] and max(RAW[g + 1:g + 13]) >= RAW[g] + 6:
                return valley(g)
    return min(range(lo, fr(t + 0.2)), key=lambda i: RAW[i]) / 100

def dip_start(i):
    mid = W[i]["s"] + 0.5 * (W[i]["e"] - W[i]["s"])
    lo, hi = fr(W[i]["s"] - 0.25), fr(min(mid, W[i]["s"] + 0.15))
    for deep in (True, False):
        c = [g for g in range(lo + 1, hi) if RAW[g] <= RAW[g - 1] and RAW[g] <= RAW[g + 1] and (RAW[g] <= QUIET if deep else True)]
        if c: return min(c[-3:], key=lambda g: RAW[g]) / 100
    return local_min(W[i]["s"] - 0.10, W[i]["s"] + 0.03)

def keep_end(j):
    t = W[j]["e"]
    final = W[j]["w"].strip()[-1:] in ".?!,"
    k = utt_index_ending_after(t - 0.03); a, b = U[k]
    if a > t - 0.05: k = max(0, k - 1); a, b = U[k]
    if b - t <= (0.65 if final else 0.35):
        nxt = U[k + 1][0] if k + 1 < len(U) else b + 5
        e_ = min(b + PAD_TAIL, b + (nxt - b) * 0.6)
        lo = min(max(b + 0.10, e_ - 0.05), e_)          # next phrase can start right after: keep the window non-empty
        return local_min(lo, max(lo, e_ + 0.02)), "pause"
    return dip_cut(j), "dip"

def keep_start(i):
    t = W[i]["s"]
    k = utt_index_ending_after(t + 0.05); a, b = U[k]
    if a >= t - 0.10:
        prev = U[k - 1][1] if k > 0 else 0
        return max(a - PAD_LEAD, prev + (a - prev) * 0.4), "pause"
    return dip_start(i), "dip"

# 1) one segment per keep range (ranges that continue straight on are one piece)
MERGED = []
for kk in KEEP:
    kk = list(kk) + [None] * (4 - len(kk))
    if MERGED and kk[0] == MERGED[-1][1] + 1 and MERGED[-1][3] is None and kk[2] is None:
        MERGED[-1][1] = kk[1]; MERGED[-1][3] = kk[3]
    else: MERGED.append(kk)
segs = []
for kk in MERGED:
    s_, sk = (kk[2], "manual") if kk[2] is not None else keep_start(kk[0])
    e_, ek = (kk[3], "manual") if kk[3] is not None else keep_end(kk[1])
    segs.append([s_, e_, sk, ek])

# 2) shorten pauses between phrases inside a segment (never inside a phrase)
tight = []
for s_, e_, sk, ek in segs:
    # phrases overlapping the segment, clipped to it: a segment that starts or ends on a dip cut sits inside a
    # phrase, and skipping that phrase would leave its following pause untouched (seconds of silence)
    inside = [(max(a, s_), min(b, e_)) for a, b in U if b > s_ + 0.02 and a < e_ - 0.02]
    cur, ck = s_, sk
    for (a1, b1), (a2, b2) in zip(inside, inside[1:]):
        if a2 - b1 > MIN_SIL:
            tight.append([cur, b1 + PAD_TAIL, ck, "pause"]); cur, ck = a2 - PAD_LEAD, "pause"
    tight.append([cur, e_, ck, ek])

# 3) frames: phrase ends round up, phrase starts round down. Pieces that sit back to back in the source
#    (a sliver of silence apart, same order) stay one continuous shot.
out = []
for s_, e_, sk, ek in tight:
    s2 = math.floor(s_ / FR) if sk == "pause" else round(s_ / FR)
    e2 = math.ceil(e_ / FR) if ek == "pause" else round(e_ / FR)
    if e2 - s2 < 4: continue
    if out and 0 <= s2 - out[-1][1] <= 6:
        out[-1][1] = max(out[-1][1], e2); out[-1][3] = ek; continue
    out.append([s2, e2, sk, ek])
# room after the last word, but only while the room stays quiet: a hold that runs into the next sentence leaks words
# ("value. And so for"). Stop 2 frames before the envelope rises past the decay level.
hold = 0
while hold < round(END_HOLD / FR) and out[-1][1] + hold + 3 < int(SRC_END / FR):
    t_ = (out[-1][1] + hold + 1) * FR
    if max(RAW[fr(t_):fr(t_ + 2 * FR) + 1]) > DECAY + 4: break
    hold += 1
out[-1][1] += hold

# 4) validate every cut against the waveform
def lvl(t0, t1): return max(RAW[fr(t0):max(fr(t0) + 1, fr(t1))])
def inside_phrase(t): return any(a + 0.02 < t < b - 0.02 for a, b in U)
problems = []
for k, (s2, e2, sk, ek) in enumerate(out):
    te, ts = e2 * FR, s2 * FR
    if k < len(out) - 1 and ek == "pause" and (inside_phrase(te) or lvl(te - 0.04, te) > QUIET):
        problems.append(f"seg{k} END   {int(te // 60)}:{te % 60:05.2f} {lvl(te - .04, te):5.0f} dB inside={inside_phrase(te)}")
    if sk == "pause" and (inside_phrase(ts) or lvl(ts, ts + 0.04) > QUIET):
        problems.append(f"seg{k} START {int(ts // 60)}:{ts % 60:05.2f} {lvl(ts, ts + .04):5.0f} dB inside={inside_phrase(ts)}")

# 5) the reel timeline: every kept word with its reel time
cum, c = [], 0
for s2, e2, _, _ in out: cum.append(c); c += e2 - s2
total = c * FR
kept = [i for kk in MERGED for i in range(kk[0], kk[1] + 1)]
firsts = {kk[0] for kk in MERGED}       # a range's first word may be stamped early, before a pinned start
words, missing = [], []
for i in kept:
    hit = None
    for (s2, e2, _, _), c0 in zip(out, cum):
        a_, b_ = s2 * FR, e2 * FR
        # SpeechTranscriber folds a pause into the next word's start, so a word can "start" before the shot
        # that holds it: if most of it lies inside the shot, it starts at the shot's first frame
        if a_ - 0.05 <= W[i]["s"] < b_ or (W[i]["s"] < a_ < W[i]["e"] - 0.08) or (i in firsts and W[i]["s"] < a_ < W[i]["e"] + 0.4):
            hit = c0 * FR + max(0.0, W[i]["s"] - a_); seg_end = c0 * FR + (e2 - s2) * FR; break
    if hit is None: missing.append(i); continue
    words.append(dict(i=i, w=W[i]["w"].strip(), s=round(hit, 3), e=round(min(seg_end, hit + (W[i]["e"] - W[i]["s"])), 3)))
cuts = [round(c0 * FR, 3) for c0 in cum[1:]]

json.dump({"frame": [1001, 30000], "segments": [[s, e] for s, e, _, _ in out], "kinds": [[a, b] for _, _, a, b in out]},
          open(f"{RD}/edl.json", "w"))
json.dump(words, open(f"{RD}/words.json", "w"), indent=0)
json.dump({"total": round(total, 3), "cuts": cuts}, open(f"{RD}/cuts.json", "w"))

FILL = re.compile(r"^(um|uh|uhm|hmm)[,.]?$", re.I)
fillers = [f"{w['w']}@{w['s']:.2f}" for w in words if FILL.match(w["w"])]
fillers += [f"you know@{a['s']:.2f}" for a, b in zip(words, words[1:]) if a["w"].lower() == "you" and b["w"].lower().startswith("know,")]
print(f"segments {len(out)}  reel length {total:.2f}s  jump cuts {len(cuts)}  words {len(words)}  levels act {ACT:.0f} / decay {DECAY:.0f} dB")
print("validation problems:", len(problems))
for p in problems: print("  ", p)
dips = [(k, ek, sk) for k, (s2, e2, sk, ek) in enumerate(out) if ek == "dip" or sk == "dip"]
if dips:
    print("cuts inside continuous speech (word timestamps drift here; qa.py's re-transcription is the real check):")
    for k, ek, sk in dips:
        s2, e2 = out[k][0] * FR, out[k][1] * FR
        if sk == "dip": print(f"   seg{k} START {s2:.2f}  (pin with a 3rd value)")
        if ek == "dip": print(f"   seg{k} END   {e2:.2f}  (pin with a 4th value)")
if missing: print("words outside every segment (timestamps off? pin a cut):", missing[:20])
if fillers: print("fillers still in the reel:", ", ".join(fillers))
if total > 90: print("WARNING: over 90 s. Reels and TikToks land best at 25-60 s.")
print(" ".join(w["w"] for w in words))
