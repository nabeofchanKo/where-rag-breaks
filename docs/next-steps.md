# 引き継ぎ — 次にやること

> **新しいセッションへ**: このファイルと [`SPEC.md`](../SPEC.md)（特に §14 改訂履歴）、
> [`README.md`](../README.md) を読めば続きから始められる。
> 「P4 進めて」「P5 進めて」と言われたら、下の該当節をそのまま実行すればよい。
>
> 最終更新: 2026-09-29

---

## いまどこまで終わっているか

| フェーズ | 状態 |
|---|---|
| P0 足場 + `text` `formula` + Arm A | ✅ 完了（[PR #1](https://github.com/nabeofchanKo/where-rag-breaks/pull/1)） |
| P1 全11チャネル | ✅ 完了（[PR #2](https://github.com/nabeofchanKo/where-rag-breaks/pull/2) / [#3](https://github.com/nabeofchanKo/where-rag-breaks/pull/3)） |
| P2 Arm B（agentic） | ✅ 完了（[PR #4](https://github.com/nabeofchanKo/where-rag-breaks/pull/4)） |
| P3 Arm C（hybrid）+ ヒートマップ | ✅ 完了（[PR #5](https://github.com/nabeofchanKo/where-rag-breaks/pull/5)） |
| 棄権モードを3アームで揃える | ✅ 完了（[PR #6](https://github.com/nabeofchanKo/where-rag-breaks/pull/6)） |
| **P4 スケーリング（H3 の判定）** | ⬜ **未着手** |
| **P5 実データ検証（任意）** | ⬜ **未着手** |

H1・H2 は支持された。**H3 は未判定**（311ファイルでは agentic にまだ余裕があり、
hybrid の優位はコスト 17%・時間 10% にとどまる）。

### 手元の状態

- `main` はクリーン。すべての結果は `results/` にコミット済み
- `corpus/` は `.gitignore`。いま置いてあるのは
  `--seed 42 --files 250 --questions 6`（指紋 `3d28964b9fdb6089`、311ファイル）
- 埋め込みは `.cache/embeddings/` にキャッシュ済み（コーパスを作り直すと再計算）
- 認証は `WRB_AUTH=cli`（既定）。契約プランの枠を使い、API 従量課金は発生しない

### 既存の結果 run

| run | 内容 |
|---|---|
| `p1-seed42-ja-k8` | Arm A × 11チャネル × 2モード × N=3（`version` は**旧設計**なので使わない） |
| `p1-version-v2-k8` | Arm A × `version`（新設計）× 2モード × N=3 |
| `p2-agentic-forced` / `p2-agentic-abstain` | Arm B × 11チャネル × N=3 |
| `p3-hybrid-forced` / `p3-hybrid-abstain` | Arm C × 11チャネル × N=3 |
| `compare-3arms` | 上をすべて重ねた図とレポート |
| `probe-p1-seed42-ja` | 検索プローブ（LLM 未使用） |
| `discarded-20260925-nonhermetic` | 破棄した run（理由つき） |

比較図の再生成コマンド:

```bash
uv run python -m eval.report \
  --run results/p1-seed42-ja-k8 \
  --also results/p1-version-v2-k8 \
  --also results/p2-agentic-forced --also results/p2-agentic-abstain \
  --also results/p3-hybrid-forced  --also results/p3-hybrid-abstain \
  --out results/compare-3arms
```

`--also` は**後の run が同じ (アーム, チャネル, モード) を上書きする**。
上書きは必ず標準出力に出るので、意図しない上書きが起きたら気づける。

---

## P4 — スケーリング（H3 の判定）

**目的**: SPEC §2 の H3「hybrid はコーパスが大きくなるほど agentic 単体より
有利になる。破綻点が存在する」を判定し、`scaling.png` を出す。

### ★ 最初に決めること（SPEC §12-6 が未決のまま）

**5,000ファイル規模で Arm B / C を素直に回すと破産する。** 実測値から見積もると:

| 規模 | Arm A | Arm B | Arm C |
|---|---|---|---|
| 1問あたり | 約23秒 / $0.014 | 約33〜53秒 / $0.05 | 約29〜36秒 / $0.04 |

5,000ファイルでは Arm B の探索がさらに伸びるので、**1問あたり数分**を見込むべき。
66問 × 3アーム × N=3 を素直に回すと十数時間。以下を人間に決めてもらうこと。

1. **規模**: SPEC は 50 / 500 / 5,000。5,000 を 2,000 に落とすかどうか
2. **問題数**: 大規模では 1チャネル 2問（計22問）に絞ってよい（SPEC §8 P4 が明記）
3. **反復**: 大規模では N=1 にするか（SPEC §5-4 は N=3 必須だが、
   P4 は「破綻点の特定」が目的なので N=1 でも傾向は見える。**N を下げたら
   レポートに明記すること**）
4. **予算上限**: 時間と金額の上限。超えたら止める

推奨の初期案（約3〜4時間）:

```
50ファイル   : 66問 × 3アーム × N=1 = 198呼出
500ファイル  : 66問 × 3アーム × N=1 = 198呼出
2,000ファイル: 22問 × 3アーム × N=1 =  66呼出
```

### 手順

```bash
# 1. 規模ごとにコーパスを作る（--files で総ファイル数を指定）
uv run python -m gen --seed 42 --files 50   --questions 6 --out corpus-50/
uv run python -m gen --seed 42 --files 500  --questions 6 --out corpus-500/
uv run python -m gen --seed 42 --files 2000 --questions 2 --out corpus-2000/

# 2. 漏洩検査（規模ごとに必ず）
uv run python -m eval.leak_check --corpus corpus-50/

# 3. Arm B/C はカタログとミラーが要る（run が無ければ自動で作るが、
#    大規模では先に作っておくと時間が読める）
uv run python -m ingest.build --corpus corpus-50/

# 4. アームを回す（例）
uv run python -m eval.run --corpus corpus-50/ --arms classical --k 8 \
    --modes forced --repeats 1 --run-id p4-n50-classical
uv run python -m eval.run --corpus corpus-50/ --arms agentic \
    --modes forced --repeats 1 --run-id p4-n50-agentic
uv run python -m eval.run --corpus corpus-50/ --arms hybrid --k 20 \
    --modes forced --repeats 1 --run-id p4-n50-hybrid

# 5. 採点
uv run python -m eval.score --run results/p4-n50-classical --corpus corpus-50/
```

### ★ 注意点（踏むと痛い）

- **`--corpus` を取り違えないこと。** 採点は `--corpus` の `questions.jsonl` を
  見るので、別規模のコーパスを渡すと qid が合わず壊れる
- **埋め込みのキャッシュは規模ごとに別。** 500 / 2,000 ファイルでは初回の
  埋め込み計算に数十分かかる。先に検索プローブを流すとキャッシュが温まる
- **`--k` を省略しない。** Arm A / C では既定が `4,8,16` で3倍走る。
  Arm B は `sweeps_k=False` なので自動的に畳まれる
- **長時間 run は必ず監視に異常終了の検出を入れる。** 一度、1呼出目で
  クラッシュしたまま気づかず放置しかけた
- **実行が落ちても `raw.jsonl` から再開できる。** 同じ `--run-id` で再実行すれば
  記録済みの行はスキップされる。ただし**コーパスが同一であることを
  指紋で確認してから**再開すること

### `scaling.png` はまだ無い

`eval/report.py` には `channel_heatmap` / `cost_accuracy` / `abstention_map` しか
無い。P4 では **`scaling.png`（横軸=ファイル数、縦軸=正答率、アームごとの線）**を
足す必要がある。複数 run をまとめる仕組み（`--also`）は既にあるので、
`meta.json` の `corpus.n_files_written` を横軸に使えばよい。

---

## P5 — 実データ検証（任意・小規模）

**目的**: 「合成データだから作為的」という批判に、小規模でも実データで答える。

SPEC §9 のとおり **上場企業のIR資料** を使う。XBRL があるので**正解ラベルを
機械的に作れる**のが決め手（手ラベリング不要）。

- 決算短信(PDF) → `scanned` に近い
- 決算説明会資料 → `chart_only` が自然に存在する
- 補足資料(Excel) → `formula` `format`
- 前期比較 → `version`
- 複数社 → `cross_file`

### ★ 必ず守ること

**資料そのものをリポジトリに入れない。** URL リストとダウンローダを置き、
利用者が自分で取得する形にする（SPEC §9）。

### 手順の骨子

1. `data/ir_sources.yaml` に「企業 / 書類種別 / URL / 取得日」を列挙
2. `ingest/fetch_ir.py` でダウンロード（`corpus-ir/files/` へ）
3. XBRL から正解ラベルを作る → `corpus-ir/questions.jsonl`（`Item` 形式）
4. `eval/leak_check.py` を通す
5. 既存の `eval/run.py` / `eval/score.py` / `eval/report.py` がそのまま使える
   （アームはコーパスの出自を知らないので、合成でも実データでも動く）

---

## このプロジェクトで守ってきた規律（引き継ぎ時に崩さないこと）

1. **反証されたら仕様を直す。結果に合わせて評価を曲げない。**
   実際に2回起きている（`formula` と `version`）。経緯は SPEC §14 に残してある
2. **各チャネルに「コントロール段」（難易度1）を置く。** ここが 1.00 で
   ある限り「罠を積んで baseline を潰しただけではない」と言える
3. **採点基準を結果を見てから変えない。** 変えたら
   [`docs/scoring-changes.md`](scoring-changes.md) に必ず記録する
4. **アームの実行環境は密閉する。** `tool_results` の検査が双方向に入っている
   （道具なしのアームが使った / 道具ありのアームが使っていない、の両方を検出）
5. **N=3 とばらつき併記。** 1発取りの数字を結論にしない。
   N を下げるならレポートに明記する
6. **LLM を呼ぶ前に、LLM 不要の検査で確かめる。** 検索プローブと
   カバレッジ検査で、これまでに 2 回、数時間ぶんの無駄と誤った結論を防いでいる
7. **会話は日本語、コミットメッセージは英語、README は日英併記**

## 環境の罠

[`docs/environment-notes.md`](environment-notes.md) に7件記録してある。
特にこの Windows 機では **AVG が `SSLKEYLOGFILE` を設定しており、
対策しないと Python の HTTPS がトレースバック無しで即死する**。
`arms/llm.py` の `bootstrap()` が全入口の先頭で対処しているので、
**新しいエントリポイントを作ったら必ず `bootstrap()` を呼ぶこと。**
