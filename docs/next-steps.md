# 引き継ぎ — 次にやること

> **新しいセッションへ**: このファイルと [`SPEC.md`](../SPEC.md)（特に §14 改訂履歴）、
> [`README.md`](../README.md) を読めば続きから始められる。
> 「P5 進めて」と言われたら下の P5 節を、ほかの残作業なら該当節をそのまま実行すればよい。
>
> 最終更新: 2026-09-30

---

## いまどこまで終わっているか

| フェーズ | 状態 |
|---|---|
| P0 足場 + `text` `formula` + Arm A | ✅ 完了（[PR #1](https://github.com/nabeofchanKo/where-rag-breaks/pull/1)） |
| P1 全11チャネル | ✅ 完了（[PR #2](https://github.com/nabeofchanKo/where-rag-breaks/pull/2) / [#3](https://github.com/nabeofchanKo/where-rag-breaks/pull/3)） |
| P2 Arm B（agentic） | ✅ 完了（[PR #4](https://github.com/nabeofchanKo/where-rag-breaks/pull/4)） |
| P3 Arm C（hybrid）+ ヒートマップ | ✅ 完了（[PR #5](https://github.com/nabeofchanKo/where-rag-breaks/pull/5)） |
| 棄権モードを3アームで揃える | ✅ 完了（[PR #6](https://github.com/nabeofchanKo/where-rag-breaks/pull/6)） |
| P4 スケーリング（H3 の判定） | ✅ 完了（[PR #7](https://github.com/nabeofchanKo/where-rag-breaks/pull/7)、SPEC §14-9） |
| **P5 実データ検証（任意）** | ⬜ **未着手** |

H1・H2 は支持された。**H3 はこのコーパスでは支持されなかった**。破綻点はあるが、
壊れるのは agentic ではなく hybrid の絞り込み（1,524 ファイルから候補に正解が揃わない
設問が増え、正答率がその上限に張り付く）。設問が一意な識別子を含むので、agentic は
grep 一発で届き、規模が難しさにならない。詳細は SPEC §14-9。

### 手元の状態

- 結果はすべて `results/` にコミット済み
- コーパスは `.gitignore`（`corpus/` `corpus-*/`）。置いてあるもの:

  | 場所 | コマンド | ファイル数 | 指紋 |
  |---|---|---|---|
  | `corpus-150/` | `--seed 42 --files 150 --questions 6` | 151 | `a49be9ee3572ffd1` |
  | `corpus/` | `--seed 42 --files 250 --questions 6` | 311 | `3d28964b9fdb6089` |
  | `corpus-1000/` | `--seed 42 --files 1000 --questions 6` | 1,524 | `748e0d483fadac0a` |
  | `corpus-5000/` | `--seed 42 --files 5000 --questions 6` | 7,956 | `299f0c22d0bb93f3` |

  `corpus/` は P4 で**作り直した**（P2/P3 のエージェントが `files/` に一時ファイルを
  残していた）。指紋は `python -m eval.scale_probe` の出力でも確かめられる
- 埋め込みは `.cache/embeddings/` にキャッシュ済み。**7,956 ファイルの初回計算は
  CPU で約 2 時間強**かかった（別の計算と並行した実測）
- Arm C の作業ディレクトリは `~/.cache/wrb-ws/<ハッシュ>`（設問ごとに作り直す）
- 認証は `WRB_AUTH=cli`（既定）。契約プランの枠を使い、API 従量課金は発生しない

### ★ `uv run` には `--no-sync` を付ける

この機では `uv run` が依存の同期を試みて、AVG の TLS 傍受で PyPI への接続に失敗する
（`invalid peer certificate: UnknownIssuer`）。環境はできているので
**`uv run --no-sync python -m ...`** で回すこと。

### 既存の結果 run

| run | 内容 |
|---|---|
| `p1-seed42-ja-k8` | Arm A × 11チャネル × 2モード × N=3（`version` は**旧設計**なので使わない） |
| `p1-version-v2-k8` | Arm A × `version`（新設計）× 2モード × N=3 |
| `p2-agentic-forced` / `p2-agentic-abstain` | Arm B × 11チャネル × N=3 |
| `p3-hybrid-v2` | Arm C × 11チャネル × 2モード × N=3（物理的な絞り込み。P3 の比較はこれを使う） |
| `p3-hybrid-forced` / `p3-hybrid-abstain` | 旧 Arm C（絞り込みに抜け道があった。置き換え済み・記録として残す） |
| `compare-3arms` | P1〜P3 を重ねた図とレポート |
| `p4-n{150,311,1000,5000}-{classical,agentic,hybrid}` | P4 本番（強制回答・N=1。311 の classical は P1 を流用） |
| `p4-scaling` | P4 の図（`scaling.png`）とレポート |
| `probe-p4-scaling` | 規模プローブ（LLM 未使用） |
| `p4-pilot-n5000-agentic` | 所要時間の見積り専用（結論に使わない） |
| `probe-p1-seed42-ja` | 検索プローブ（LLM 未使用） |
| `discarded-20260925-nonhermetic` / `discarded-20260930-leaky-hybrid` | 破棄した run（理由つき） |

P3 の比較図の再生成コマンド（`--also` は後の run が同じ (アーム, チャネル, モード) を上書きし、
上書きは必ず標準出力に出る）:

```bash
uv run --no-sync python -m eval.report \
  --run results/p1-seed42-ja-k8 \
  --also results/p1-version-v2-k8 \
  --also results/p2-agentic-forced --also results/p2-agentic-abstain \
  --also results/p3-hybrid-v2 \
  --out results/compare-3arms
```

P4 の図の再生成コマンド:

```bash
uv run --no-sync python -m eval.scaling \
  --point 151  results/p4-n150-classical results/p4-n150-agentic results/p4-n150-hybrid \
  --point 311  results/p1-seed42-ja-k8 results/p1-version-v2-k8 \
               results/p4-n311-agentic results/p4-n311-hybrid \
  --point 1524 results/p4-n1000-classical results/p4-n1000-agentic results/p4-n1000-hybrid \
  --point 7956 results/p4-n5000-classical results/p4-n5000-agentic results/p4-n5000-hybrid \
  --probe results/probe-p4-scaling/scale_probe_raw.csv \
  --out results/p4-scaling
```

道具を使う run の後の監査:

```bash
uv run --no-sync python -m eval.hermetic_audit --corpus corpus-1000/ --since 2026-09-30T00:00:00Z
uv run --no-sync python -m eval.hermetic_audit --corpus corpus-1000/ --hybrid
```

「正解ファイルへの言及」と「別設問のコード」が 0 でなければ、中身を確かめるまで
その run を結論に使わない（自分で書いた一時ファイルの誤検知もありうる）。

---

## 残作業（どれも任意）

### A. 識別子の無い設問で H3 を測る

P4 の結論は「設問が一意な文書コードを含む」コーパスでのもの。内容の記述でしか文書を
特定できない設問では、agentic の探索が規模とともに重くなり、H3 が成り立つ余地がある。
**設問を変える＝仕様の変更なので、LLM を回す前に SPEC を改訂して記録すること。**
規模プローブ（`eval/scale_probe.py`）の `b_key_path_hits` が規模とともに増える設計に
なっているかを、LLM を呼ぶ前に確かめる。

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
   （道具なしのアームが使った / 道具ありのアームが使っていない、の両方を検出）。
   道具を使う run の後は **`eval/hermetic_audit.py` でセッション記録を監査**し、
   **コーパスの指紋が生成時と一致するか**も確かめる（P4 で 5 つの穴が見つかった）
5. **N=3 とばらつき併記。** 1発取りの数字を結論にしない。
   N を下げるならレポートに明記する
6. **LLM を呼ぶ前に、LLM 不要の検査で確かめる。** 検索プローブと
   カバレッジ検査で、これまでに 2 回、数時間ぶんの無駄と誤った結論を防いでいる
7. **会話は日本語、コミットメッセージは英語、README は日英併記**

## 環境の罠

[`docs/environment-notes.md`](environment-notes.md) に9件記録してある。
特にこの Windows 機では **AVG が `SSLKEYLOGFILE` を設定しており、
対策しないと Python の HTTPS がトレースバック無しで即死する**。
`arms/llm.py` の `bootstrap()` が全入口の先頭で対処しているので、
**新しいエントリポイントを作ったら必ず `bootstrap()` を呼ぶこと。**
