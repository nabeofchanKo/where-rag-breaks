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

### 現時点でわかっていること（検索プローブ・LLM 未使用）

LLM を呼ぶ前に、**検索側だけ**を切り出して測れる。課金ゼロで完全に決定的なので、
チャネル設計が効いているかをここで先に確認する。

`--seed 42 --files 120 --questions 10`（日本語コーパス、120ファイル、540チャンク、
BM25 + BGE-m3 の RRF 融合）:

| チャネル | k | file_recall | answer_literal | answer_literal_corpus |
|---|---|---|---|---|
| `text` | 4 / 8 / 16 / 32 | 1.000 | 1.000 | 1.000 |
| `formula` | 4 / 8 / 16 / 32 | **1.000** | **0.000** | **0.000** |

- `file_recall` … 上位 k に答えのあるファイルが入った割合
- `answer_literal` … 上位 k の本文に正解文字列がそのまま現れた割合
- `answer_literal_corpus` … コーパス全体の抽出テキストに現れる割合（k 非依存）

読み方: **`formula` は検索が失敗しているのではない。** 正しいファイルは k=4 で
100% 引けている。それでも答えが手に入らないのは、抽出テキストのどこにも
答えが存在しないから。k を 32 に上げても、コーパス全体を見ても 0%。
これが「チャンク化の時点で落ちる」ということの、検索側から見た姿である。

> ⚠️ **この数字を過大に読まないこと。** `answer_literal` が 0 でも、モデルが
> 数量と単価から**計算で導ける**可能性は残る。これは「答えがそのままの形では
> 存在しない」ことの証拠であって、「答えられない」ことの証明ではない。
> 実際の正答率は Arm A を走らせて測る。

再現:

```bash
uv run python -m gen --seed 42 --files 120 --questions 10 --out corpus/
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

### What we know so far (retrieval probe, no LLM)

The retrieval side can be measured on its own, before any LLM is involved. It costs
nothing and is fully deterministic, which makes it the right place to check whether
the channel design actually bites.

`--seed 42 --files 120 --questions 10` (Japanese corpus, 120 files, 540 chunks,
BM25 + BGE-m3 fused with RRF):

| Channel | k | file_recall | answer_literal | answer_literal_corpus |
|---|---|---|---|---|
| `text` | 4 / 8 / 16 / 32 | 1.000 | 1.000 | 1.000 |
| `formula` | 4 / 8 / 16 / 32 | **1.000** | **0.000** | **0.000** |

- `file_recall` — a chunk from a file that holds the answer made it into the top k
- `answer_literal` — the answer string appears verbatim in the retrieved text
- `answer_literal_corpus` — it appears anywhere in the extracted corpus (k-independent)

How to read it: **`formula` is not a retrieval failure.** The right file is retrieved
100% of the time at k=4. The answer is still unavailable because it exists nowhere in
the extracted text — not at k=32, not across the whole corpus. That is what "dropped
at chunking time" looks like from the retrieval side.

> ⚠️ **Do not over-read this.** `answer_literal` of 0 leaves open that the model can
> still *derive* the answer from the quantities and unit prices. This is evidence that
> the answer does not exist in literal form, not proof that it cannot be answered.
> Actual accuracy requires running Arm A.

Reproduce:

```bash
uv run python -m gen --seed 42 --files 120 --questions 10 --out corpus/
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
