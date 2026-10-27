# Finding the moments

`scripts/moments.py` counts; you judge. It numbers every sentence and ranks 20–60 s windows on hook words, numbers, named things, a first-person story, loudness and a clean ending. The ranking is a shortlist, not an answer. Read the whole sentence list in `reels/moments.md` before you pick. (The scoring words are English; for other languages, read and judge by hand.)

## What makes a reel moment

A reel is one idea with a turn in it. Look for these, in this order:

1. **A story with a result.** A problem, what the speaker did, what happened, ideally a number at the end ("from 2,000 followers to 40,000 in a summer").
2. **A contrarian line.** "Most people stretch wrong", "you don't need a fancy camera". It works as a hook on its own.
3. **A concrete how-to.** Three steps, a kit list, "here's the exact recipe". Lists turn into checklists and logo rows.
4. **A number that lands.** Money, time saved, reps, followers, cost per month. Every spoken number gets a counter.
5. **An analogy that clicks.** It needs a figure that shows it.

Skip general intros, "in this video I'll…", channel housekeeping, sponsor reads, and anything that only makes sense with the earlier minutes.

## The shape of a reel (25–60 s, best 30–45)

| Part | Length | Job |
|---|---|---|
| Hook | 0–3 s | The first line has to stop the scroll on its own: a problem, a claim or a number. Frame 0 is already packed (hook title plus a figure). |
| Setup | 3–12 s | Why it matters: the pain, the stakes. |
| Turn | the middle | What changed, what they did, the steps. The densest graphics go here. |
| Payoff | the last 3–8 s | The result or the one-line takeaway, full-frame with a slow push-in. |

- **Reordering is allowed.** Moving the strongest line to the front is often the edit.
- **Cut inside sentences freely** to drop fillers ("you know", "um", false starts). `keep.json` takes any word ranges, in any order.
- **A dangling opener** ("And so…", "But…", "That's why…") needs its first word cut, or a different start.
- **The last word must be a real ending:** a full stop, not "and". A reel that ends on its payoff loops well.

## When there is no great spoken hook

If the moment's best line still isn't a scroll-stopper in its first 2 seconds, don't force a weak spoken opener. Add a hook the speaker never said:

- **Text hook:** `r.hook("…", "accent")` on frame 0 for 2-3 s, over whatever they're saying. Max 8 words. It can be a claim ("Your warm-up is the problem"), a number teaser ("2k → 40k followers"), a question ("What does one bad hire cost?") or a call-out ("Runners over 40"). Pull it from the reel's own payoff or numbers, never a promise the reel doesn't keep. No "the secret", no "here's what nobody tells you", no "this changes everything".
- **Visual hook:** put the payoff's best figure on frame 0 and hold it 1.5-2.5 s, a cold open before the story (the landed counter, a finished list, a before/after). Pass `t0=0` to most components and they're on screen at frame 0. Show it again when the speaker says it, so the payoff still lands.
- **Both together** work well: a text hook on top, the visual teaser in the slot.
- When the spoken hook IS strong, the text hook just labels it. Don't stack a different claim on top.

## Cut it up

Before locking `keep.json`:
1. **Find the best 1-3 s line in the whole moment** and open on it, even if it was said in the middle.
2. **Drop generic lines** that would fit any video.
3. **Bridge jumps with the speaker's own words** from nearby in the long-form.
4. **Trim inside sentences:** fillers, "you know", restarts, "and so", a trailing "right?".
5. **Read the keep list top to bottom as one script.** If a line needs a line that was cut, fix it.

## Workflow

```bash
python3 moments.py "$WORK"                                     # -> $WORK/reels/moments.md
python3 moments.py "$WORK" --keep 154-156,159-160 > keep.json   # a starting keep list from sentence numbers
```

Then edit `keep.json` by word index. Show the user the shortlist before cutting: for each reel, the hook line, the payoff line, the length, one sentence on why it works, and 2-3 hook options with the one you'd use. They pick.
