# Findings in detail

> The long form behind the summary in the [README](../README.md). Design history is in [SPEC.md](../SPEC.md) section 14 (Japanese).
> 日本語: [findings.md](findings.md)

## One rule across every channel: each has a control tier

Every channel has **three tiers**, graded not by how hard the arithmetic is but by
**what cannot be extracted**.

| Tier | What it is |
|---|---|
| **1 control** | the same answer is also readable as plain text. Classical RAG is expected to get this |
| **2 unreachable** | the answer exists only in that channel's medium |
| **3 decoyed** | the answer is unreachable *and* a plausible wrong value is readable instead |

**Tier 1 is the load-bearing part of this design.** As long as it stays pinned at
1.000, the benchmark has evidence that it did not simply stack traps until the
baseline lost. If tier 1 ever drops, that is a signal the extractor or the retriever
is broken, not that a trap worked.

Tier 3 decoys are registered in `Item.decoys` at generation time, and scoring reports
`decoy_rate` — **the share of answers that were wrong in the specific way the trap
predicted**. Being wrong and being wrong on cue are counted separately.

| Channel | Where the answer lives | Tier 3 decoy |
|---|---|---|
| `text` | a body paragraph | (baseline) |
| `format` | a cell's fill colour | a salient note on a different row |
| `formula` | a formula and its range | a stale cached value |
| `chart_only` | a number inside a chart image | a company-wide total in the body text |
| `chart_native` | chart series names over a hidden sheet | a differently-ordered listing note |
| `scanned` | an image-only PDF | the previous lot number on the cover note |
| `layout` | spatial arrangement in a diagram | an alphabetical occupant roster |
| `version` | the substantive diff between editions | **the old edition's value** (tier 2 is decoyed too) |
| `cross_file` | a sum across N files | a roll-up that missed one case |
| `hidden` | a pptx presenter note | the previous deal's discount in the body |
| `locked` | inside a password-protected file | a preliminary figure on the cover note |

> ★ **In `format`, `layout` and `chart_native` tier 3, the answer string itself does
> appear in the extracted text.** The record numbers are in the table; the names are in
> the roster. What is hidden is not the string but which one it is. "The answer is
> extractable" therefore does not mean the trap failed.

## Arm A results (eleven channels)

![channel_heatmap](../results/p1-seed42-ja-k8/figures/channel_heatmap.png)

396 calls (66 questions x k=8 x 2 abstention modes x N=3), `claude-sonnet-5`,
BM25 + BGE-m3 fused with RRF, over a 311-file / 591-chunk corpus. Full write-up in
[`results/p1-seed42-ja-k8/report.md`](../results/p1-seed42-ja-k8/report.md).

**Forced mode (abstention not permitted)**

| Tier | Result |
|---|---|
| 1 control | **1.00 on all eleven channels** |
| 2 unreachable | **0.00 on nine of eleven** |
| 3 decoyed | 0.00 on nine of eleven (`formula` alone at 0.50) |

**Eight channels land on exactly 0.333, which is 6/18**: the control tier and
nothing else. Fill colour, chart images, spatial arrangement, encryption and
cross-file aggregation are entirely unrelated mechanisms that fail in the same
shape — and with every control tier at 1.00, neither the extractor nor the
retriever can be the cause.

Variance across repeats is **zero** on every channel (min = max = mean, N=3).

**Detectable loss versus undetectable loss**

![channel_heatmap_abstain](../results/p1-seed42-ja-k8/figures/channel_heatmap_abstain_ok.png)

Allowing abstention splits the channels into three kinds.

| Kind | Channels | Behaviour |
|---|---|---|
| **Notices and declines** | `chart_native` `chart_only` `layout` `locked` `scanned` | answer_rate 0.333, **precision 1.000**. It knows when it cannot see |
| **Distrusts the question itself** | `format` `hidden` | answer_rate **0.000**. The question names a property the model cannot verify, so it declines even the control tier |
| **Does not notice** | `cross_file` `formula` | answers 50–67% of the time and half of those are wrong |

The third kind is the dangerous one. `cross_file` sums whichever of the ten files
made it into the window and never registers that the rest are missing.

**Scoring disclosure**

- LLM judge overrode exact match **0 times** (the "premises of X" alias added after
  P0 removed the only disagreement there was)
- **23 answers** matched a decoy and skipped the judge
- **20 answers** refused in prose while leaving `abstained` false; scored as wrong per
  the output contract, so `penalized` is lower than reality by that much
- **Verifiability**: total `tool_results` 0, calls with `num_turns != 1` 0

**★ Read `version` out of this table.** It scores 1.00 here only because the path
said `current/`. It was rebuilt and re-measured separately, below.

## Rebuilding and re-measuring `version`

`version` scored 1.00 at every tier in the run above, because of the path. Arm A
labels each chunk with its origin, so `[policies/current/VR-4879_policy.docx ::
Article 3]` reveals which edition is current before any content is compared. Every
cited evidence string pointed at `current/`.

Dropping provenance would "fix" it, but provenance is what lets the arm cite
evidence at all and is ordinary practice, so removing it is the deliberate hole
SPEC section 4-1 rules out. **The trap was changed instead.**

Tiers 2 and 3 now place both editions in one directory under document control
numbers (`_D6345`), and which one is current is recoverable only from the revision
date inside the document. Deliberately not `_ed1`/`_ed2` — the ordering in a
sequence number is itself the answer. The revision date sits under its own heading,
so structure-aware chunking puts it in a **different chunk** from the clause being
asked about.

Re-measurement ([`results/p1-version-v2-k8/`](../results/p1-version-v2-k8/), 36 calls, N=3):

| Tier | Layout | forced | decoy_rate | abstain_ok answer_rate |
|---|---|---|---|---|
| 1 control | path reveals the edition | **1.000** | 0.000 | 1.000 |
| 2 | only the revision date distinguishes them | **0.500** | **0.500** | **0.000** |
| 3 | as above, old edition ranks higher | 0.833 | 0.000 | **0.000** |

The trap now bites: at tier 2 half the answers are the superseded value. Under
abstention it answers nothing at tiers 2 and 3, so this is a **detectable** loss.

> ⚠️ **Tier 3 (0.833) scores above tier 2 (0.500), inverting the intended ordering.**
> Each tier rests on 2 questions x 3 repeats = 6 observations, so the ordering is not
> established at this sample size. Claiming a difficulty order would need more
> questions per channel (SPEC section 3-2's eventual target of 10 gives 3–4 per tier).

> **On the two corpora**: the eleven-channel table above comes from corpus
> `098d2e5f77e1c9a9`, this re-measurement from `3d28964b9fdb6089`. They differ only
> in the `version` files plus 12 redistributed distractors; the question files of the
> other ten channels are **byte-identical**, because each channel draws from its own
> RNG namespace.


## Three-arm comparison (P3)

![3 arms](../results/compare-3arms/figures/channel_heatmap.png)

Same corpus, same model, forced mode, N=3.

| Arm | accuracy | penalized | cost/question | s/question | tool calls |
|---|---|---|---|---|---|
| **A `classical`** | 0.449 | **−0.076** | $0.014 | 22.2 | 0 |
| **B `agentic`** | **0.919** | +0.843 | $0.047 | 32.5 | 6.6 |
| **C `hybrid`** | **0.934** | +0.869 | **$0.036** | 36.3 | 5.7 |

- **Classical RAG's penalized score is negative** (−0.076): more wrong answers than
  right ones, the same sign as the −11 measurement SPEC section 1 starts from.
- **Agentic and hybrid are nearly tied on accuracy** (0.919 against 0.934; one question
  is 0.015, so the gap is one question), with hybrid **23% cheaper** and 12% slower.
- **H3 (hybrid pulls ahead as the corpus grows; a break-even point exists) cannot be
  decided from this.** See P4 below.
- The original P3 hybrid runs (`p3-hybrid-forced` / `p3-hybrid-abstain`) were measured
  with a leaky narrowing step (found in P4, SPEC 14-9). Re-measured with physical
  narrowing, forced accuracy went from 0.919 to 0.934, so the leak had not inflated it.
  The row above is the re-measurement (`p3-hybrid-v2`).

## Scaling (P4): deciding H3

![scaling](../results/p4-scaling/figures/scaling.png)

The same 66 questions, on four corpora that differ only in how much filler they hold
(forced mode, N=1; classical at 311 files is P1's N=3). The dashed line is measured
without an LLM: the share of questions whose answer files all make it into hybrid's
candidates, which caps hybrid's accuracy.

| files | classical | agentic | hybrid | hybrid ceiling | agentic $/q | hybrid $/q |
|---|---|---|---|---|---|---|
| 151 | 0.439 | 0.939 | 0.939 | 1.000 | 0.040 | 0.035 |
| 311 | 0.449 | 0.924 | 0.939 | 0.970 | 0.045 | 0.042 |
| 1,524 | 0.455 | 0.939 | **0.848** | 0.833 | 0.039 | **0.080** |
| 7,956 | 0.455 | 0.909 | **0.818** | 0.848 | 0.044 | **0.068** |

**H3 is not supported on this corpus. There is a break point, but it is hybrid that breaks.**

- **Agentic holds up at 7,956 files.** Every question carries a document code
  (`PRJ-1234` and so on) and the agent opens all 66 questions with a grep. At most 11
  files match a code at any size, so size does not make the search harder
- **Hybrid drops from 1,524 files on, and its accuracy tracks its narrowing ceiling.**
  Of the 12 questions it missed at 7,956 files, 8 never had all their answer files among
  the candidates. The typical case is `locked`: the document holding the password rule
  shares little vocabulary with the question, so it never makes the top 20. Dropping
  **documents that are related but not similar** is the weak spot of narrowing by
  similarity
- **And hybrid's failures are expensive.** On questions both arms got right, cost and
  time are the same, so narrowing saves nothing. The gap comes from hybrid searching to
  its turn limit when the answer is not among its candidates ($0.17 and 116 s per
  question, against $0.06 and 49 s for agentic)
- This holds for a corpus whose questions carry a unique identifier. For questions that
  can only locate a document by describing its content, H3 may still hold (untested,
  SPEC 14-9)

Around the P4 runs we found and closed five gaps that would have skewed the comparison
(a leak in hybrid's narrowing, how companion files were capped, the CLI injecting the
user's auto memory, agents' scratch files persisting in the corpus, and hard links in the
workspace). SPEC 14-9 has the details and the check of earlier results; discarded runs
are in [`results/discarded-20260930-leaky-hybrid/`](../results/discarded-20260930-leaky-hybrid/README.md).

## What abstention changes (three arms, two modes)

![abstention](../results/compare-3arms/figures/abstention_map.png)

| Arm | Mode | accuracy | penalized | answer rate | precision | cost | s |
|---|---|---|---|---|---|---|---|
| `classical` | forced | 0.449 | **−0.076** | 0.975 | 0.461 | $0.014 | 22.2 |
| `classical` | **abstain** | 0.333 | **+0.288** | 0.379 | **0.880** | **$0.006** | 13.9 |
| `agentic` | forced | 0.919 | +0.843 | 0.995 | 0.924 | $0.047 | 32.5 |
| `agentic` | abstain | 0.909 | +0.843 | 0.975 | 0.933 | $0.050 | 53.0 |
| `hybrid` | forced | 0.934 | +0.869 | 1.000 | 0.934 | $0.036 | 36.3 |
| `hybrid` | abstain | 0.944 | +0.889 | 1.000 | 0.944 | $0.039 | 33.0 |

**The single most valuable thing you can give classical RAG is permission to say
"I don't know."** The penalized score flips from **−0.076 to +0.288**. Accuracy
itself falls (0.449 → 0.333), but precision among answered rises from 0.461 to
**0.880** and the cost **halves** ($0.014 → $0.006), because it stops generating
once it knows it cannot see.

**Abstention buys the agent almost nothing.** Its penalized score is 0.843 either
way, because its answer rate barely moves (0.995 → 0.975): having retrieved
*something* with its tools, it always believes it found the answer.

The figure shows exactly that. Orange (classical) hugs the left — declining —
while blue and green (agentic, hybrid) sit against the right edge, always answering.

**The one place the agent goes negative is `version`** (penalized −0.111, answer
rate 1.000, decoy rate 0.556). It never notices it is holding a superseded edition,
so being allowed to abstain does not save it. On `chart_native` it does abstain
properly (answer rate 0.722, precision 1.000) — so it is not that it *cannot*
decline, only that staleness is invisible to it.

> Practical reading: **if you are keeping classical RAG, implement abstention
> first** — it beats accuracy work. **If you are switching to an agent, do not rely
> on abstention.** Detecting staleness needs a separate mechanism (comparing
> revision dates, recomputing cached values).

## Comparing Arm B (agentic) — the agent is not uniformly better

![arm comparison](../results/compare-3arms/figures/channel_heatmap.png)

Arm B indexes with a **catalog plus a markdown mirror** and does its own searching
through `list_files` / `read_file` / `grep` / `run_python` / `view_image`.
198 calls (66 questions, forced mode, N=3).

★ **The mirror is built with exactly the same extractor as Arm A.** Privileging
ingestion would make it impossible to tell whether the agent found something or
the preprocessor handed it over. Arm B's strength is meant to be its tools.

**Unreachable answers: the agent solves them**

Eight channels go from 0.00 under Arm A to 1.00 under Arm B. Fill colours through
openpyxl, chart images through `view_image`, encrypted archives by assembling the
password rule from two documents and opening the zip with `pyzipper`, ten-file sums
by opening all ten and adding them up.

**But where a stale answer is readable, the agent does worse**

| Channel | accuracy A→B | decoy rate A→B |
|---|---|---|
| `formula` tier 3 (stale cache) | 0.50 → **0.17** | 0.50 → **0.67** |
| `version` tier 3 (index points at the old edition) | 0.83 → **0.00** | 0.17 → **0.44** |

Following the traces makes the reason plain.

- **`formula`**: the agent opens the workbook "properly" with openpyxl and trusts
  the cached value `data_only=True` hands back. Arm A sees the cached value and the
  formula side by side in extracted text and sometimes recomputes.
  **Reading the file correctly is what lends the stale number its authority.**
- **`version`**: the index points at the old edition, so the agent follows it and
  reads the superseded document — six times out of six. Chunk retrieval never
  follows a pointer, so it cannot fail this way.

Which gives:

| Kind of loss | Classical RAG | Agent |
|---|---|---|
| **Cannot reach the answer** | breaks | **solves it** |
| **A stale answer is readable** | sometimes notices | **more reliably fooled** |

"Drop RAG and use an agent" is right about the first row and **backwards about the
second**.

**Cost**

Arm B runs $0.02–0.08 and 24–125 s per question, against roughly $0.005 and 23 s for
Arm A — **4 to 16 times the cost and time** for the difference above.

## The part that got falsified (and why that matters)

The first version of the `formula` channel hid only one thing: the total was
written nowhere in the file. **Arm A scored 10/10 against it** — precisely the
falsification condition SPEC section 2 lays out.

The cause was not a lazy Arm A. The model read the formulas, multiplied quantity by
unit price across twelve rows, and pulled the tax rate from another sheet. Every
answer was re-derived independently from the source workbooks, so it was not a
scoring bug either.

**Hiding the aggregate is not enough when the inputs remain readable; a modern model
just recomputes.** Stripping formulas out of the extractor would "restore" H2, but
that is the deliberate hole SPEC section 4-1 forbids — a win that does not count.

So the difficulty axis moved from "how hard is the arithmetic" to "what cannot be
extracted at all":

| Tier | Trap mechanism |
|---|---|
| 1 | unchanged, **kept on purpose as a control** — evidence that traps were not simply stacked until the baseline lost |
| 2 | the detail sheet grows to 240–320 rows, so the inputs cannot fit in the top-k window |
| 3 | **stale cached values** computed from a previous revision are injected into the summary's formula cells |

The full write-up with measurements lives in
[the PR #1 comment](https://github.com/nabeofchanKo/where-rag-breaks/pull/1#issuecomment-5826732933).
**When the design is falsified, fix the design — never bend the evaluation to fit the result.**

## What we know so far (retrieval probe, no LLM)

The retrieval side can be measured on its own, before any LLM is involved. It costs
nothing and is fully deterministic, which makes it the right place to check whether
the channel design actually bites.

`--seed 42 --files 120 --questions 12` (Japanese corpus, 120 files, 960 chunks,
BM25 + BGE-m3 fused with RRF):

| Channel | Tier | k | file_recall | source_coverage | answer_literal | decoy_literal |
|---|---|---|---|---|---|---|
| `text` | 1–3 | 4–32 | 1.000 | 0.21–0.56 | **1.000** | 0.000 |
| `formula` | 1 (control) | 4–32 | 1.000 | 0.667 | 0.000 | 0.000 |
| `formula` | 2 (window) | 4 → 32 | 1.000 | **0.136 → 0.374** | 0.000 | 0.000 |
| `formula` | 3 (stale) | 4–32 | 1.000 | 0.667 | 0.000 | **1.000** |

- `file_recall` — a chunk from a file holding the answer made it into the top k
- `source_coverage` — share of the target file's chunks that fit in the window
- `answer_literal` — the answer string appears verbatim in the retrieved text
- `decoy_literal` — the decoy (the stale value) is inside the window

How to read it:

- **Retrieval never fails.** `file_recall` is 1.000 everywhere; the right file is
  found reliably at k=4.
- **Tier 2 is a window problem.** The target file is 20–24 chunks; even at k=32 only
  37% of it fits. The full line-item table is unreachable by construction.
- **Tier 3 shows only the decoy.** The answer is never visible, the stale value always
  is. A pipeline that reads values picks up a plausible, internally consistent, wrong
  number.

> ⚠️ **Do not over-read this.** `answer_literal` of 0 still leaves room for the model
> to *derive* the answer — tier 1 was beaten exactly that way. This is evidence the
> answer does not exist in literal form, not proof that it cannot be answered. Actual
> accuracy requires running Arm A.

Reproduce:

```bash
uv run python -m gen --seed 42 --files 120 --questions 12 --out corpus/
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32
```
