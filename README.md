# where-rag-breaks

> 古典的RAG（chunk + embed + top-k）が「どの情報チャネルで壊れるか」を、正解ラベルつきの合成コーパスで測るベンチマーク。
>
> A benchmark that measures **which information channels break classical RAG** (chunk + embed + top-k), using a synthetic corpus with automatically-derived ground truth.

**ステータス / Status: P0（足場 + `text` `formula` の2チャネル + Arm A）作業中。図と数値はまだありません。**

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
```

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
```

### Corpus language

The default corpus is **Japanese** (`--locale ja`); `--locale en` produces an English one.

**Filenames and folder names are always ASCII.** Windows normalizes Japanese filenames to NFD, so an `os.path.join` built from Python's NFC literals yields `exists() == False`. Keeping only the *content* Japanese avoids that trap entirely.

### License

MIT
