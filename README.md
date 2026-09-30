# where-rag-breaks

> 古典的RAG（chunk + embed + top-k）が「どの情報チャネルで壊れるか」を、正解ラベルつきの合成コーパスで測るベンチマーク。
>
> A benchmark that measures **which information channels break classical RAG** (chunk + embed + top-k), using a synthetic corpus with automatically-derived ground truth.

[日本語](#日本語) ・ [English](#english)

---

## 日本語

### 結論

1. **古典的RAGは、答えが本文以外にあると決まった形で壊れる。** 塗り色・グラフ画像・暗号化ファイルなど 11 チャネル中 8 つで、テキストから読める段は全問正解、読めない段は全滅した。全体の正答率は 0.45 で、正解より誤答のほうが多い。
2. **エージェント型は 0.92 まで上がるが、万能ではない。** 「答えに届かない」損失は解決する一方、「古い値が読めてしまう」損失では古典的RAGより確実に騙される。「分からない」と言わせる設計が効くのは古典的RAGだけだった。
3. **コーパスを 50 倍にしても、壊れたのはエージェントではなかった。** 壊れたのは「検索で絞ってからエージェントに渡す」方式のほうで、約 1,500 ファイルから正答率が落ち、コストは約 2 倍になった。

![チャネル別の正答率（3アーム）](results/compare-3arms/figures/channel_heatmap.png)

### 何をどう測ったか

実務の文書QAでは、答えが**本文テキスト以外**に入っていることが多い。古典的RAGはそれをチャンク化の時点で落とし、落としたことに気づく仕組みもない。この現象を、誰でも再現できる形で測った。

同じコーパス・同じモデル（`claude-sonnet-5`）で 3 つの実装に同じ 66 問を解かせる。

| アーム | 索引 | 検索 |
|---|---|---|
| **A `classical`** | チャンク + 埋め込み + BM25 | top-k |
| **B `agentic`** | カタログ + Markdown ミラー | モデルが `grep` / `read` / `run_python` / `view_image` で自分で探す |
| **C `hybrid`** | 両方 | A でファイル候補を 20 件に絞ってから B |

コーパスは合成で、答えの置き場所が違う **11 の情報チャネル**を持つ: 本文（`text`）、セルの塗り色（`format`）、数式（`formula`）、グラフ画像（`chart_only`）、グラフ定義（`chart_native`）、スキャンPDF（`scanned`）、図の空間配置（`layout`）、版の差分（`version`）、複数ファイルの集計（`cross_file`）、発表者ノート（`hidden`）、パスワード付きファイル（`locked`）。

各チャネルは 3 段の難易度を持つ。

| 段 | 位置づけ |
|---|---|
| **1 コントロール** | 同じ答えがテキストからも読める。古典的RAGが解けて当然の段 |
| **2 到達不能** | 答えがそのチャネル固有の場所にしかない |
| **3 囮つき** | 答えは到達不能で、かつ、もっともらしい間違った値が読める位置にある |

**コントロール段がこの設計の肝である。** ここが全問正解である限り、「罠を積んで baseline を潰しただけ」ではないと言える。

### 分かったこと

**1. 古典的RAGは、機構の違うチャネルで同じ形に壊れる**

| アーム | 正答率 | 純スコア（正−誤） | 1問あたりコスト | 1問あたり秒 |
|---|---|---|---|---|
| **A `classical`** | 0.449 | **−0.076** | $0.014 | 22.2 |
| **B `agentic`** | **0.919** | +0.843 | $0.047 | 32.5 |
| **C `hybrid`** ※ | **0.919** | +0.838 | $0.039 | 29.1 |

311 ファイル・強制回答・N=3。Arm A はコントロール段が 11 チャネルすべてで 1.00、到達不能の段は 9 チャネルで 0.00 だった。塗り色・グラフ画像・空間配置・暗号化・ファイル横断集計は互いに別の機構なのに、8 チャネルがぴったり同じ正答率（0.333）に並ぶ。コントロール段が満点なので、原因は抽出器でも検索でもない。

※ P3 の hybrid は絞り込みに抜け道があった状態の数字（[作り方](#作り方)を参照）。

**2. エージェントは「届かない」を解決するが、「古い値」にはより確実に騙される**

| 損失の型 | 古典的RAG | エージェント |
|---|---|---|
| 答えに到達できない（塗り色、画像、暗号化など） | 壊れる | **解決する**（8 チャネルで 0.00 → 1.00） |
| 古い答えが読めてしまう（陳腐化したキャッシュ値、旧版） | ときどき気づく | **より確実に騙される** |

`formula` の囮つきの段で、エージェントが囮を答えた率は 0.67（古典的RAGは 0.50）、`version` では 0.44（同 0.17）。ライブラリで「正しく」開いて得たキャッシュ値を信じ、旧版を指す目次を素直に辿るためである。

**3. 棄権が効くのは古典的RAGだけ**

「分からない」と答えてよい設定にすると、古典的RAGの純スコアは **−0.076 → +0.288** と負から正に反転し、コストは半分になる。エージェントは 0.843 のまま変わらない。道具で何かを取得できた以上、常に「見つけた」と思っているからである。

**4. 規模を大きくして壊れたのは、検索で絞る方式のほうだった**

![コーパス規模と正答率・コスト・時間](results/p4-scaling/figures/scaling.png)

| ファイル数 | classical | agentic | hybrid | hybrid の上限 | agentic $/問 | hybrid $/問 |
|---|---|---|---|---|---|---|
| 151 | 0.439 | 0.939 | 0.939 | 1.000 | 0.040 | 0.035 |
| 311 | 0.449 | 0.924 | 0.939 | 0.970 | 0.045 | 0.042 |
| 1,524 | 0.455 | 0.939 | **0.848** | 0.833 | 0.039 | **0.080** |
| 7,956 | 0.455 | 0.909 | **0.818** | 0.848 | 0.044 | **0.068** |

同じ 66 問を、埋め草の量だけ変えたコーパスで測った（強制回答・N=1）。破線と「hybrid の上限」は、LLM を呼ばずに測った「hybrid の候補に正解ファイルがすべて入る設問の割合」。

- **agentic は 7,956 ファイルでも崩れない。** 設問は文書コードを含み、エージェントは全問で grep から探し始めるので、規模が探索の難しさにならない。
- **hybrid の正答率は、絞り込みの上限に張り付いて落ちる。** パスワード規則の文書のように「関係はあるが質問と似ていない文書」が候補から落ちる。
- **hybrid の失敗は高くつく。** 両方が正解した問題ではコストは同じで、差は、答えが候補に無い問題で上限まで探し続けることから来る。

「コーパスが大きくなるほど hybrid が有利になる」という当初の仮説（H3）は、このコーパスでは支持されなかった。

詳しい数字と図は [docs/findings.md](docs/findings.md)、設計の経緯は [SPEC.md](SPEC.md) §14。

### 作り方

**課題設定（何を測るか、仮説と反証条件）、設計の判断、結果の採否は作者が行い、実装・測定の実行・文書の下書きには AI コーディング支援（Claude Code）を使った。**

AI が書いたコードと数字をそのまま信じないために、次の規律を先に決めて守った。

- **反証されたら仕様を直す。結果に合わせて評価を曲げない。** `formula` と `version` は初版の罠を古典的RAGに突破され、罠のほうを作り直した（SPEC §14-1, §14-6）。
- **LLM を呼ぶ前に、LLM を使わない検査で確かめる。** 検索プローブと規模プローブで、罠や規模が本当に効いているかを先に測る。
- **比較の公平性を崩す穴は、見つけたら記録して測り直す。** 実行者の MCP 設定や自動メモリがアームに混入していた件、hybrid の絞り込みに抜け道があった件などを見つけ、塞いだうえで該当の run を破棄した（SPEC §14-4, §14-9、[破棄した run](results/discarded-20260930-leaky-hybrid/README.md)）。
- **採点基準を結果を見てから変えない。** 変更は [docs/scoring-changes.md](docs/scoring-changes.md) にすべて記録する。

### 既知の限界

- **合成コーパスでの結果である。** 実データ（IR資料など）での検証は未実施（SPEC §9）。
- **設問数が少ない。** 1 チャネル 6 問（1 段あたり 2 問）。チャネル単位の傾向は安定しているが、段ごとの細かい順序までは主張できない。
- **モデルは 1 種類**（`claude-sonnet-5`）。
- **規模の測定は N=1**、設問は一意な文書コードを含む。識別子の無い設問では、規模の結論が変わる余地がある。
- 311 ファイルの測定（P1〜P3）は、自動メモリの索引が全アームの文脈に入った状態で行った。全アームに等しく入り、正解は含まないので、比較の結論は変わらないと判断している（SPEC §14-9）。

### 再現方法

前提: [uv](https://docs.astral.sh/uv/) と Python 3.12。

```bash
git clone https://github.com/nabeofchanKo/where-rag-breaks.git
cd where-rag-breaks
uv sync --system-certs

# コーパスを生成する（同じ seed ならバイト単位で同じものができる）
uv run python -m gen --seed 42 --files 250 --questions 6 --out corpus/

# 答えがファイル名やカタログに漏れていないか検査する
uv run python -m eval.leak_check --corpus corpus/

# テスト（決定性など。LLM は呼ばない）
uv run pytest

# 検索側だけを測る（LLM 未使用）
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32

# アームを走らせて採点し、図を出す（LLM を呼ぶ。認証が要る）
uv run python -m eval.run --corpus corpus/ --arms classical --k 8
uv run python -m eval.score --run results/<run_id>
uv run python -m eval.report --run results/<run_id>
```

コーパス生成とテストは認証なしで動く。LLM を呼ぶ手順の既定は `WRB_AUTH=cli`（`claude` CLI のログイン認証）で、API の従量課金は発生しない。コーパスの既定は日本語で、`--locale en` で英語も生成できる（ファイル名は常に ASCII）。

| 文書 | 内容 |
|---|---|
| [SPEC.md](SPEC.md) | 仕様と、設計を変えた経緯（§14 改訂履歴） |
| [docs/findings.md](docs/findings.md) | 測定結果の詳細 |
| [docs/environment-notes.md](docs/environment-notes.md) | 実装中に踏んだ環境の罠（9 件） |
| [docs/next-steps.md](docs/next-steps.md) | 残作業と引き継ぎ |

### ライセンス

MIT

---

## English

### Findings

1. **Classical RAG breaks in one consistent way when the answer is not in the body text.** In 8 of 11 channels (cell fill colors, chart images, encrypted files and so on) it got every question whose answer was also readable as text, and none of the rest. Overall accuracy was 0.45, with more wrong answers than right ones.
2. **An agent lifts that to 0.92 but is not uniformly better.** It fixes answers that cannot be reached, yet it is fooled more reliably than classical RAG when a stale value is readable. Letting the system say "I don't know" helped classical RAG only.
3. **Growing the corpus 50-fold did not break the agent.** What broke was narrowing by retrieval before handing over to the agent: accuracy fell from about 1,500 files on, at roughly twice the cost.

![Accuracy by channel, three arms](results/compare-3arms/figures/channel_heatmap.png)

### What was measured, and how

In real document QA the answer often lives **outside the body text**. Classical RAG drops it at chunking time and has no way to notice. This repository measures that in a form anyone can reproduce.

Three implementations answer the same 66 questions on the same corpus with the same model (`claude-sonnet-5`).

| Arm | Index | Retrieval |
|---|---|---|
| **A `classical`** | chunks + embeddings + BM25 | top-k |
| **B `agentic`** | catalog + markdown mirror | the model searches with `grep` / `read` / `run_python` / `view_image` |
| **C `hybrid`** | both | A narrows to 20 candidate files, then B |

The corpus is synthetic and has **eleven information channels** that differ in where the answer sits: body text (`text`), cell fill color (`format`), formulas (`formula`), chart images (`chart_only`), chart definitions (`chart_native`), scanned PDFs (`scanned`), spatial layout (`layout`), differences between revisions (`version`), sums across files (`cross_file`), presenter notes (`hidden`) and password-protected files (`locked`).

Each channel has three tiers.

| Tier | Role |
|---|---|
| **1 control** | The same answer is also readable as text. Classical RAG should get it |
| **2 unreachable** | The answer exists only in the channel-specific place |
| **3 decoy** | Unreachable, and a plausible wrong value sits where it can be read |

**The control tier is what makes the design hold.** As long as it scores perfectly, the result is not just a baseline buried under traps.

### What we found

**1. Classical RAG fails the same way across unrelated channels**

| Arm | accuracy | penalized (right − wrong) | cost/question | s/question |
|---|---|---|---|---|
| **A `classical`** | 0.449 | **−0.076** | $0.014 | 22.2 |
| **B `agentic`** | **0.919** | +0.843 | $0.047 | 32.5 |
| **C `hybrid`** † | **0.919** | +0.838 | $0.039 | 29.1 |

311 files, forced mode, N=3. Arm A scored 1.00 on the control tier in all eleven channels and 0.00 on the unreachable tier in nine. Fill colors, chart images, spatial layout, encryption and cross-file sums are unrelated mechanisms, yet eight channels land on exactly the same accuracy (0.333). Since the control tier is perfect, neither the extractor nor retrieval is the cause.

† P3's hybrid row was measured with a leak in its narrowing step (see [How this was built](#how-this-was-built)).

**2. The agent fixes "unreachable" and is fooled more reliably by "stale"**

| Kind of loss | Classical RAG | Agent |
|---|---|---|
| The answer cannot be reached (fill color, image, encryption) | breaks | **fixes it** (0.00 → 1.00 in eight channels) |
| A stale answer is readable (outdated cached value, old revision) | sometimes notices | **fooled more reliably** |

On the decoy tier of `formula` the agent gave the decoy 0.67 of the time (classical RAG 0.50); on `version`, 0.44 (against 0.17). It trusts the cached value that a library returns when opening the file "properly", and it follows a table of contents that points at the old revision.

**3. Abstention helps classical RAG only**

Allowed to answer "I don't know", classical RAG's penalized score flips from **−0.076 to +0.288** and its cost halves. The agent stays at 0.843: having fetched something with a tool, it always believes it found the answer.

**4. At scale, it was narrowing by retrieval that broke**

![Corpus size versus accuracy, cost and time](results/p4-scaling/figures/scaling.png)

| files | classical | agentic | hybrid | hybrid ceiling | agentic $/q | hybrid $/q |
|---|---|---|---|---|---|---|
| 151 | 0.439 | 0.939 | 0.939 | 1.000 | 0.040 | 0.035 |
| 311 | 0.449 | 0.924 | 0.939 | 0.970 | 0.045 | 0.042 |
| 1,524 | 0.455 | 0.939 | **0.848** | 0.833 | 0.039 | **0.080** |
| 7,956 | 0.455 | 0.909 | **0.818** | 0.848 | 0.044 | **0.068** |

The same 66 questions on corpora that differ only in how much filler they hold (forced mode, N=1). The dashed line and the "hybrid ceiling" column are measured without an LLM: the share of questions whose answer files all make it into hybrid's candidates.

- **The agent holds up at 7,956 files.** Every question carries a document code and the agent opens every question with a grep, so size does not make the search harder.
- **Hybrid's accuracy falls along its narrowing ceiling.** Documents that are related to the question but not similar to it, such as the one holding a password rule, drop out of the candidates.
- **Hybrid's failures are expensive.** On questions both arms got right the cost is the same; the gap comes from searching to the turn limit when the answer is not among the candidates.

The original hypothesis that hybrid pulls ahead as the corpus grows (H3) is not supported on this corpus.

Full numbers and figures are in [docs/findings.en.md](docs/findings.en.md); the design history is in [SPEC.md](SPEC.md) section 14 (Japanese).

### How this was built

**The author set the problem (what to measure, the hypotheses and what would falsify them), made the design decisions and decided which results to accept. Implementation, running the measurements and drafting the documents were done with AI coding assistance (Claude Code).**

To avoid taking AI-written code and numbers on trust, these rules were fixed first and kept.

- **When falsified, fix the spec; never bend the evaluation to fit the result.** Classical RAG beat the first versions of the `formula` and `version` traps, and the traps were rebuilt (SPEC 14-1, 14-6).
- **Check without an LLM before calling one.** A retrieval probe and a scale probe measure whether a trap or a corpus size actually bites.
- **Record every gap that skews the comparison, then re-measure.** The runner's MCP settings and auto memory leaking into the arms, and a leak in hybrid's narrowing, were found, closed, and the affected runs discarded (SPEC 14-4, 14-9, [discarded runs](results/discarded-20260930-leaky-hybrid/README.md)).
- **Never change scoring after seeing results.** Every change is logged in [docs/scoring-changes.md](docs/scoring-changes.md).

### Known limits

- **The corpus is synthetic.** Validation on real data such as investor-relations filings has not been done (SPEC 9).
- **Few questions.** Six per channel, two per tier. Channel-level patterns are stable; the ordering of individual tiers is not something these numbers can claim.
- **One model** (`claude-sonnet-5`).
- **The scaling runs are N=1**, and every question carries a unique document code. Without such identifiers the scaling conclusion could differ.
- The 311-file runs (P1 to P3) were made with the runner's auto-memory index present in every arm's context. It was the same for all arms and holds no answers, so we judge the comparison unaffected (SPEC 14-9).

### Reproducing it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
git clone https://github.com/nabeofchanKo/where-rag-breaks.git
cd where-rag-breaks
uv sync --system-certs

# Generate the corpus (the same seed yields byte-identical output)
uv run python -m gen --seed 42 --files 250 --questions 6 --out corpus/

# Check that no answer leaked into a filename or the catalog
uv run python -m eval.leak_check --corpus corpus/

# Tests (determinism and more; no LLM)
uv run pytest

# Measure retrieval alone (no LLM)
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32

# Run an arm, score it and draw the figures (calls the LLM; needs credentials)
uv run python -m eval.run --corpus corpus/ --arms classical --k 8
uv run python -m eval.score --run results/<run_id>
uv run python -m eval.report --run results/<run_id>
```

Corpus generation and the tests need no credentials. The LLM steps default to `WRB_AUTH=cli` (the `claude` CLI login), which incurs no metered API billing. The corpus is Japanese by default; `--locale en` generates an English one (filenames are always ASCII).

| Document | Contents |
|---|---|
| [SPEC.md](SPEC.md) | The specification and why the design changed (section 14, Japanese) |
| [docs/findings.en.md](docs/findings.en.md) | The findings in detail |
| [docs/environment-notes.md](docs/environment-notes.md) | Environment traps hit along the way (Japanese) |
| [docs/next-steps.md](docs/next-steps.md) | Remaining work and handoff (Japanese) |

### License

MIT
