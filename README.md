# where-rag-breaks

> 古典的RAG（chunk + embed + top-k）が「どの情報チャネルで壊れるか」を、正解ラベルつきの合成コーパスで測るベンチマーク。
>
> A benchmark that measures **which information channels break classical RAG** (chunk + embed + top-k), using a synthetic corpus with automatically-derived ground truth.

**ステータス / Status: P0 作業中。図3枚はまだ出ていません。**
**現時点の測定は「検索プローブ」（LLM 未使用）のみ / So far only the retrieval probe (no LLM) has been run.**

---

## 日本語

### これは何か

実務の文書QAでは、答えが**本文テキスト以外のチャネル**に入っていることが多い。セルの塗り色、数式、グラフの中の数値、スキャンPDF、図の空間配置、版の差分、複数ファイルの合計、発表者ノート、パスワード付きファイル。

古典的RAGはこれらを**チャンク化の時点で落とす**。落ちたことに気づく仕組みもない。結果、モデルは与えられたチャンクから自信満々に間違える。

このリポジトリは、その現象を**誰でも再現できる形**で示す。合成コーパスなので正解ラベルが自動で手に入り、罠の種類と難易度を設計できる。

### 測り方

同じコーパス・同じモデルで3つの実装を走らせ、**情報チャネル別**の正答率とコストを比較する。

| アーム | 索引 | 検索 |
|---|---|---|
| **A `classical`** | チャンク + 埋め込み + BM25 | top-k（k をスイープ） |
| **B `agentic`** | カタログ + Markdown ミラー | モデルが `grep` / `ls` / `read` で自分で探す |
| **C `hybrid`** | 両方 | A でファイル候補を絞ってから B |

11の情報チャネル: `text` `format` `formula` `chart_only` `chart_native` `scanned` `layout` `version` `cross_file` `hidden` `locked`

### 一度反証された話（このリポジトリの作り方そのもの）

`formula` チャネルの初版は「合計値をファイルのどこにも書かない」という罠だった。
**Arm A はこれを 10/10 で突破した。** SPEC §2 が定める反証条件そのものである。

原因は Arm A の手抜きではなかった。モデルは数式を読んで意味を理解し、数量×単価を
12行ぶん計算し、別シートの税率を掛けて正解していた。全問をソースファイルから
独立に再計算して照合済みで、採点バグでもない。

**集計結果だけを隠しても、入力が読める形で残っていれば現代のモデルは再計算する。**
かといって抽出器から数式を落とせば H2 は「成立」するが、それは SPEC §4-1 が禁じる
「抽出器に意図的な穴」であり、禁止されている勝ち方である。

そこで難易度の軸を「計算の複雑さ」から「**何が抽出不能か**」へ組み替えた。

| 難易度 | 罠の機構 |
|---|---|
| 1 | 初版のまま。**コントロールとして意図的に残している**（罠を積んだだけではないことを示すため） |
| 2 | 明細を 240〜320 行にし、入力が top-k の窓に入らないようにする |
| 3 | サマリの数式セルに旧版から計算した**陳腐化したキャッシュ値**を注入する |

経緯は [PR #1 のコメント](https://github.com/nabeofchanKo/where-rag-breaks/pull/1#issuecomment-5826732933)
に測定値つきで残してある。**反証されたら仕様を直す。結果に合わせて評価を曲げない。**

### 現時点でわかっていること（検索プローブ・LLM 未使用）

LLM を呼ぶ前に、**検索側だけ**を切り出して測れる。課金ゼロで完全に決定的なので、
チャネル設計が効いているかをここで先に確認する。

`--seed 42 --files 120 --questions 12`（日本語コーパス、120ファイル、960チャンク、
BM25 + BGE-m3 の RRF 融合）:

| チャネル | 難易度 | k | file_recall | source_coverage | answer_literal | decoy_literal |
|---|---|---|---|---|---|---|
| `text` | 1–3 | 4〜32 | 1.000 | 0.21–0.56 | **1.000** | 0.000 |
| `formula` | 1 (control) | 4〜32 | 1.000 | 0.667 | 0.000 | 0.000 |
| `formula` | 2 (窓超え) | 4 → 32 | 1.000 | **0.136 → 0.374** | 0.000 | 0.000 |
| `formula` | 3 (陳腐化) | 4〜32 | 1.000 | 0.667 | 0.000 | **1.000** |

- `file_recall` … 上位 k に答えのあるファイルが入った割合
- `source_coverage` … 対象ファイルのチャンクのうち窓に入った割合
- `answer_literal` … 上位 k の本文に正解文字列がそのまま現れた割合
- `decoy_literal` … 囮（陳腐化した値）が窓に入った割合

読み方:

- **どのチャネルも検索は失敗していない。** `file_recall` は全条件で 1.000。正しい
  ファイルは k=4 で確実に引けている。
- **難易度2 は窓が足りない。** 対象ファイルは 20〜24 チャンクあるのに、k=32 まで
  上げても 37% しか載らない。明細全体は原理的に見えない。
- **難易度3 は囮だけが見えている。** 正解は 0%、陳腐化した値は 100% 窓に入る。
  値を読んだだけのパイプラインは、もっともらしく整合した古い数字を掴む。

> ⚠️ **この数字を過大に読まないこと。** `answer_literal` が 0 でも、モデルが
> 計算で導ける可能性は残る（実際、難易度1 はそれで突破された）。これは
> 「答えがそのままの形では存在しない」ことの証拠であって、「答えられない」ことの
> 証明ではない。実際の正答率は Arm A を走らせて測る。

再現:

```bash
uv run python -m gen --seed 42 --files 120 --questions 12 --out corpus/
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32
```

### 公平性のためのルール

このベンチマークの価値は**公平な比較**にある。設計上の約束:

- **Arm A を steel-man する** — hybrid retrieval（BM25 + dense）、構造を見たチャンク分割、チャネルごとの最良 k で評価。手を抜いた baseline は叩かない
- **設問ごとの特別扱いを禁止** — どのアームも設問IDを見てはいけない
- **答えの漏洩を自動検査** — ファイル名・カタログ・プロンプトに答えが出ていないか `eval/leak_check.py` で検査
- **N=3 回実行** — 1発取りの数字を結論にしない（平均と min/max を併記）
- **アーム間でモデル・温度を揃える**

詳細は [SPEC.md](SPEC.md) を参照。

### セットアップ

前提: [uv](https://docs.astral.sh/uv/) と Python 3.12。

```bash
git clone https://github.com/nabeofchanKo/where-rag-breaks.git
cd where-rag-breaks
uv sync --system-certs
```

> **`--system-certs` について**: アンチウイルスが TLS を傍受する環境（企業PCなど）では、これが無いと `uv sync` が失敗する。傍受されていない環境では付けても害はない。

LLM を呼ぶ手順（`eval/run.py`）だけ認証が要る。コーパス生成と決定性テストは**認証不要**で動く。

```bash
cp .env.example .env   # 必要に応じて値を埋める
```

### 使い方

```bash
# コーパスを生成する（既定は日本語コーパス。--locale en で英語）
uv run python -m gen --seed 42 --files 20 --out corpus/

# 答えがファイル名やカタログに漏れていないか検査する
uv run python -m eval.leak_check --corpus corpus/

# 決定性テスト（同 seed で2回生成してバイト一致するか）
uv run pytest

# 検索側だけを測る（LLM 未使用・課金ゼロ）
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32

# アームを走らせる（LLM を呼ぶ。認証が要る）
uv run python -m eval.run --corpus corpus/ --arms classical --k 4,8,16
uv run python -m eval.score --run results/<run_id>
```

Windows でこのリポジトリを動かすときに踏んだ罠は
[docs/environment-notes.md](docs/environment-notes.md) にまとめてある。

### コーパスの言語

既定は**日本語**（`--locale ja`）。`--locale en` で英語コーパスも生成できる。

**ファイル名・フォルダ名は常に ASCII** にしている。Windows のファイルシステムは日本語名を NFD 正規化するため、Python の NFC リテラルで `os.path.join` すると `exists() == False` になるという既知の罠がある。中身だけを日本語にすることで、この罠を踏まずに日本語資料を扱える。

### ライセンス

MIT

---

## English

### What this is

In real-world document QA, the answer often lives in a channel **other than the body text**: cell fill colors, spreadsheet formulas, numbers inside chart images, scanned PDFs, spatial arrangement in diagrams, diffs between revisions, sums across many files, presenter notes, password-protected files.

Classical RAG drops all of these **at chunking time**, with no mechanism to notice the loss. The model then answers confidently and wrongly from the chunks it was given.

This repository demonstrates that failure in a **reproducible** form. Because the corpus is synthetic, ground truth comes for free, and the traps can be designed by type and difficulty.

### How it measures

Three implementations run over the same corpus with the same model. Accuracy and cost are reported **per information channel**.

| Arm | Index | Retrieval |
|---|---|---|
| **A `classical`** | chunks + embeddings + BM25 | top-k (k is swept) |
| **B `agentic`** | catalog + markdown mirror | the model searches with `grep` / `ls` / `read` |
| **C `hybrid`** | both | A narrows the file candidates, then B |

Eleven channels: `text` `format` `formula` `chart_only` `chart_native` `scanned` `layout` `version` `cross_file` `hidden` `locked`

### The part that got falsified (and why that matters)

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

### What we know so far (retrieval probe, no LLM)

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

### Fairness rules

The value of this benchmark rests entirely on the comparison being fair:

- **Steel-man Arm A** — hybrid retrieval (BM25 + dense), structure-aware chunking, evaluated at the best `k` per channel. Beating up a strawman baseline proves nothing
- **No per-question special-casing** — no arm may look at the question ID
- **Automated leak checking** — `eval/leak_check.py` verifies the answer never appears in a filename, the catalog, or a prompt
- **N=3 runs** — never conclude from a single run (mean plus min/max are both reported)
- **Identical model and temperature across arms**

See [SPEC.md](SPEC.md) (Japanese) for the full design.

### Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
git clone https://github.com/nabeofchanKo/where-rag-breaks.git
cd where-rag-breaks
uv sync --system-certs
```

> **On `--system-certs`**: on machines where antivirus software intercepts TLS, `uv sync` fails without it. It is harmless elsewhere.

Only the LLM-invoking step (`eval/run.py`) needs credentials. Corpus generation and the determinism tests run with **no credentials at all**.

### Usage

```bash
# Generate the corpus (Japanese by default; --locale en for English)
uv run python -m gen --seed 42 --files 20 --out corpus/

# Check that no answer leaked into a filename or the catalog
uv run python -m eval.leak_check --corpus corpus/

# Determinism test: generate twice with the same seed, assert byte equality
uv run pytest

# Measure retrieval alone (no LLM, no cost)
uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32

# Run the arms (calls the LLM; needs credentials)
uv run python -m eval.run --corpus corpus/ --arms classical --k 4,8,16
uv run python -m eval.score --run results/<run_id>
```

The Windows-specific traps hit while building this are written up in
[docs/environment-notes.md](docs/environment-notes.md).

### Corpus language

The default corpus is **Japanese** (`--locale ja`); `--locale en` produces an English one.

**Filenames and folder names are always ASCII.** Windows normalizes Japanese filenames to NFD, so an `os.path.join` built from Python's NFC literals yields `exists() == False`. Keeping only the *content* Japanese avoids that trap entirely.

### License

MIT
