# 実行レポート — `p1-seed42-ja-k8`

## 実行条件

- モデル: `claude-sonnet-5`  認証: `cli`
- コーパス: seed `42` / locale `ja` / generator_version `2`
- アーム: agentic, classical, hybrid
- 重ねた run: p1-seed42-ja-k8, p1-version-v2-k8, p2-agentic-forced, p2-agentic-abstain, p3-hybrid-v2（同じアーム×チャネルが重複した場合は後の run を採用）
- k: [8]  モード: ['forced', 'abstain_ok']  反復: 3
- CLI の固定オーバーヘッド（この run から推定）: **0 トークン/呼出**

### 索引の構成

```json
{
  "classical": {
    "n_chunks": 591,
    "chunk_chars": 1200,
    "overlap_chars": 200,
    "embedding_model": "BAAI/bge-m3",
    "retrieval": "bm25 + dense (RRF)",
    "reranker": null
  }
}
```

### 密閉性の検証（SPEC §4-2）

- ツールが結果を返した回数: **4977**（Arm A は 0 でなければ無効）
- 往復が 1 回で終わらなかった呼出: **792**

### 採点

- LLM judge: `未使用`
- judge が exact match を覆した件数: **0**
- 囮に一致したため judge にかけなかった件数: **0**

採点基準に対する事後変更は [`docs/scoring-changes.md`](../../docs/scoring-changes.md) を参照。

## 図

![channel_heatmap](figures/channel_heatmap.png)
![channel_heatmap_abstain_ok](figures/channel_heatmap_abstain_ok.png)
![cost_accuracy](figures/cost_accuracy.png)
![abstention_map](figures/abstention_map.png)

## チャネル × 難易度（= 罠の機構）

| arm       | mode       | channel      |   difficulty |   total |   correct |   incorrect |   answered |   accuracy |   penalized |   answer_rate |   precision |   decoy_rate |
|:----------|:-----------|:-------------|-------------:|--------:|----------:|------------:|-----------:|-----------:|------------:|--------------:|------------:|-------------:|
| agentic   | abstain_ok | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | chart_native |            2 |   6.000 |     2.000 |       0.000 |      2.000 |      0.333 |       0.333 |         0.333 |       1.000 |      nan     |
| agentic   | abstain_ok | chart_native |            3 |   6.000 |     5.000 |       0.000 |      5.000 |      0.833 |       0.833 |         0.833 |       1.000 |        0.000 |
| agentic   | abstain_ok | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | chart_only   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | chart_only   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | cross_file   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | cross_file   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | format       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | format       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | format       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | formula      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | formula      |            3 |   6.000 |     3.000 |       3.000 |      6.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| agentic   | abstain_ok | hidden       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | hidden       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | hidden       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | layout       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | layout       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | locked       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | locked       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | scanned      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | scanned      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | scanned      |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | version      |            2 |   6.000 |     2.000 |       4.000 |      6.000 |      0.333 |      -0.333 |         1.000 |       0.333 |        0.667 |
| agentic   | abstain_ok | version      |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        1.000 |
| agentic   | forced     | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | chart_native |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | chart_native |            3 |   6.000 |     5.000 |       1.000 |      6.000 |      0.833 |       0.667 |         1.000 |       0.833 |        0.000 |
| agentic   | forced     | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | chart_only   |            2 |   6.000 |     5.000 |       1.000 |      6.000 |      0.833 |       0.667 |         1.000 |       0.833 |      nan     |
| agentic   | forced     | chart_only   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | cross_file   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | cross_file   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | format       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | format       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | format       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | formula      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | formula      |            3 |   6.000 |     1.000 |       5.000 |      6.000 |      0.167 |      -0.667 |         1.000 |       0.167 |        0.667 |
| agentic   | forced     | hidden       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | hidden       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | hidden       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | layout       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | layout       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | locked       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | locked       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | scanned      |            1 |   6.000 |     5.000 |       0.000 |      5.000 |      0.833 |       0.833 |         0.833 |       1.000 |      nan     |
| agentic   | forced     | scanned      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | scanned      |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | version      |            2 |   6.000 |     4.000 |       2.000 |      6.000 |      0.667 |       0.333 |         1.000 |       0.667 |        0.333 |
| agentic   | forced     | version      |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        1.000 |
| classical | abstain_ok | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | chart_native |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | chart_native |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | chart_only   |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | chart_only   |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | cross_file   |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | cross_file   |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.000 |
| classical | abstain_ok | format       |            1 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | format       |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | format       |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | formula      |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | formula      |            3 |   6.000 |     0.000 |       3.000 |      3.000 |      0.000 |      -0.500 |         0.500 |       0.000 |        0.500 |
| classical | abstain_ok | hidden       |            1 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | hidden       |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | hidden       |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | layout       |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | layout       |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | locked       |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | locked       |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | scanned      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | scanned      |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |      nan     |
| classical | abstain_ok | scanned      |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| classical | abstain_ok | version      |            2 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | version      |            3 |   6.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | forced     | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | chart_native |            2 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |      nan     |
| classical | forced     | chart_native |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.167 |
| classical | forced     | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | chart_only   |            2 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |      nan     |
| classical | forced     | chart_only   |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.000 |
| classical | forced     | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | cross_file   |            2 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |      nan     |
| classical | forced     | cross_file   |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.000 |
| classical | forced     | format       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | format       |            2 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |      nan     |
| classical | forced     | format       |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        1.000 |
| classical | forced     | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | formula      |            2 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |      nan     |
| classical | forced     | formula      |            3 |   6.000 |     3.000 |       3.000 |      6.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| classical | forced     | hidden       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | hidden       |            2 |   6.000 |     0.000 |       5.000 |      5.000 |      0.000 |      -0.833 |         0.833 |       0.000 |      nan     |
| classical | forced     | hidden       |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.667 |
| classical | forced     | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | layout       |            2 |   6.000 |     0.000 |       5.000 |      5.000 |      0.000 |      -0.833 |         0.833 |       0.000 |      nan     |
| classical | forced     | layout       |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.500 |
| classical | forced     | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | locked       |            2 |   6.000 |     0.000 |       5.000 |      5.000 |      0.000 |      -0.833 |         0.833 |       0.000 |      nan     |
| classical | forced     | locked       |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.000 |
| classical | forced     | scanned      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | scanned      |            2 |   6.000 |     0.000 |       5.000 |      5.000 |      0.000 |      -0.833 |         0.833 |       0.000 |      nan     |
| classical | forced     | scanned      |            3 |   6.000 |     0.000 |       6.000 |      6.000 |      0.000 |      -1.000 |         1.000 |       0.000 |        0.500 |
| classical | forced     | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| classical | forced     | version      |            2 |   6.000 |     3.000 |       3.000 |      6.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| classical | forced     | version      |            3 |   6.000 |     5.000 |       0.000 |      5.000 |      0.833 |       0.833 |         0.833 |       1.000 |        0.000 |
| hybrid    | abstain_ok | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | chart_native |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | chart_native |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | chart_only   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | chart_only   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | cross_file   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | cross_file   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | format       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | format       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | format       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | formula      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | formula      |            3 |   6.000 |     1.000 |       5.000 |      6.000 |      0.167 |      -0.667 |         1.000 |       0.167 |        0.833 |
| hybrid    | abstain_ok | hidden       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | hidden       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | hidden       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | layout       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | layout       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | locked       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | locked       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | scanned      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | scanned      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | scanned      |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | version      |            2 |   6.000 |     3.000 |       3.000 |      6.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| hybrid    | abstain_ok | version      |            3 |   6.000 |     3.000 |       3.000 |      6.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| hybrid    | forced     | chart_native |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | chart_native |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | chart_native |            3 |   6.000 |     5.000 |       1.000 |      6.000 |      0.833 |       0.667 |         1.000 |       0.833 |        0.167 |
| hybrid    | forced     | chart_only   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | chart_only   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | chart_only   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | cross_file   |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | cross_file   |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | cross_file   |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | format       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | format       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | format       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | formula      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | formula      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | formula      |            3 |   6.000 |     1.000 |       5.000 |      6.000 |      0.167 |      -0.667 |         1.000 |       0.167 |        0.833 |
| hybrid    | forced     | hidden       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | hidden       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | hidden       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | layout       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | layout       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | layout       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | locked       |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | locked       |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | locked       |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | scanned      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | scanned      |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | scanned      |            3 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | text         |            1 |   9.000 |     9.000 |       0.000 |      9.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | text         |            2 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | text         |            3 |   3.000 |     3.000 |       0.000 |      3.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | version      |            1 |   6.000 |     6.000 |       0.000 |      6.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | version      |            2 |   6.000 |     4.000 |       2.000 |      6.000 |      0.667 |       0.333 |         1.000 |       0.667 |        0.333 |
| hybrid    | forced     | version      |            3 |   6.000 |     1.000 |       5.000 |      6.000 |      0.167 |      -0.667 |         1.000 |       0.167 |        0.833 |

`decoy_rate` は囮（陳腐化したキャッシュ値など）をそのまま答えた割合。
囮のある設問だけが母数で、NaN は囮のない段。

## チャネルごとの最良 k（SPEC §4-1）

| arm       | mode       | channel      |       k |   total |   correct |   incorrect |   answered |   accuracy |   penalized |   answer_rate |   precision |   decoy_rate |
|:----------|:-----------|:-------------|--------:|--------:|----------:|------------:|-----------:|-----------:|------------:|--------------:|------------:|-------------:|
| agentic   | abstain_ok | chart_native | nan     |  18.000 |    13.000 |       0.000 |     13.000 |      0.722 |       0.722 |         0.722 |       1.000 |        0.000 |
| agentic   | abstain_ok | chart_only   | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | cross_file   | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | format       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | formula      | nan     |  18.000 |    15.000 |       3.000 |     18.000 |      0.833 |       0.667 |         1.000 |       0.833 |        0.500 |
| agentic   | abstain_ok | hidden       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | layout       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | locked       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | scanned      | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | abstain_ok | text         | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | abstain_ok | version      | nan     |  18.000 |     8.000 |      10.000 |     18.000 |      0.444 |      -0.111 |         1.000 |       0.444 |        0.556 |
| agentic   | forced     | chart_native | nan     |  18.000 |    17.000 |       1.000 |     18.000 |      0.944 |       0.889 |         1.000 |       0.944 |        0.000 |
| agentic   | forced     | chart_only   | nan     |  18.000 |    17.000 |       1.000 |     18.000 |      0.944 |       0.889 |         1.000 |       0.944 |        0.000 |
| agentic   | forced     | cross_file   | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | format       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | formula      | nan     |  18.000 |    13.000 |       5.000 |     18.000 |      0.722 |       0.444 |         1.000 |       0.722 |        0.667 |
| agentic   | forced     | hidden       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | layout       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | locked       | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| agentic   | forced     | scanned      | nan     |  18.000 |    17.000 |       0.000 |     17.000 |      0.944 |       0.944 |         0.944 |       1.000 |        0.000 |
| agentic   | forced     | text         | nan     |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| agentic   | forced     | version      | nan     |  18.000 |    10.000 |       8.000 |     18.000 |      0.556 |       0.111 |         1.000 |       0.556 |        0.444 |
| classical | abstain_ok | chart_native |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | abstain_ok | chart_only   |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | abstain_ok | cross_file   |   8.000 |  18.000 |     6.000 |       6.000 |     12.000 |      0.333 |       0.000 |         0.667 |       0.500 |        0.000 |
| classical | abstain_ok | format       |   8.000 |  18.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | formula      |   8.000 |  18.000 |     6.000 |       3.000 |      9.000 |      0.333 |       0.167 |         0.500 |       0.667 |        0.500 |
| classical | abstain_ok | hidden       |   8.000 |  18.000 |     0.000 |       0.000 |      0.000 |      0.000 |       0.000 |         0.000 |       0.000 |        0.000 |
| classical | abstain_ok | layout       |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | abstain_ok | locked       |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | abstain_ok | scanned      |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | abstain_ok | text         |   8.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | abstain_ok | version      |   8.000 |  18.000 |     6.000 |       0.000 |      6.000 |      0.333 |       0.333 |         0.333 |       1.000 |        0.000 |
| classical | forced     | chart_native |   8.000 |  18.000 |     6.000 |      12.000 |     18.000 |      0.333 |      -0.333 |         1.000 |       0.333 |        0.167 |
| classical | forced     | chart_only   |   8.000 |  18.000 |     6.000 |      12.000 |     18.000 |      0.333 |      -0.333 |         1.000 |       0.333 |        0.000 |
| classical | forced     | cross_file   |   8.000 |  18.000 |     6.000 |      12.000 |     18.000 |      0.333 |      -0.333 |         1.000 |       0.333 |        0.000 |
| classical | forced     | format       |   8.000 |  18.000 |     6.000 |      12.000 |     18.000 |      0.333 |      -0.333 |         1.000 |       0.333 |        1.000 |
| classical | forced     | formula      |   8.000 |  18.000 |     9.000 |       9.000 |     18.000 |      0.500 |       0.000 |         1.000 |       0.500 |        0.500 |
| classical | forced     | hidden       |   8.000 |  18.000 |     6.000 |      11.000 |     17.000 |      0.333 |      -0.278 |         0.944 |       0.353 |        0.667 |
| classical | forced     | layout       |   8.000 |  18.000 |     6.000 |      11.000 |     17.000 |      0.333 |      -0.278 |         0.944 |       0.353 |        0.500 |
| classical | forced     | locked       |   8.000 |  18.000 |     6.000 |      11.000 |     17.000 |      0.333 |      -0.278 |         0.944 |       0.353 |        0.000 |
| classical | forced     | scanned      |   8.000 |  18.000 |     6.000 |      11.000 |     17.000 |      0.333 |      -0.278 |         0.944 |       0.353 |        0.500 |
| classical | forced     | text         |   8.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| classical | forced     | version      |   8.000 |  18.000 |    14.000 |       3.000 |     17.000 |      0.778 |       0.611 |         0.944 |       0.824 |        0.167 |
| hybrid    | abstain_ok | chart_native |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | chart_only   |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | cross_file   |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | format       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | formula      |  20.000 |  18.000 |    13.000 |       5.000 |     18.000 |      0.722 |       0.444 |         1.000 |       0.722 |        0.833 |
| hybrid    | abstain_ok | hidden       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | layout       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | locked       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | scanned      |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | abstain_ok | text         |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | abstain_ok | version      |  20.000 |  18.000 |    12.000 |       6.000 |     18.000 |      0.667 |       0.333 |         1.000 |       0.667 |        0.333 |
| hybrid    | forced     | chart_native |  20.000 |  18.000 |    17.000 |       1.000 |     18.000 |      0.944 |       0.889 |         1.000 |       0.944 |        0.167 |
| hybrid    | forced     | chart_only   |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | cross_file   |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | format       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | formula      |  20.000 |  18.000 |    13.000 |       5.000 |     18.000 |      0.722 |       0.444 |         1.000 |       0.722 |        0.833 |
| hybrid    | forced     | hidden       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | layout       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | locked       |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | scanned      |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |        0.000 |
| hybrid    | forced     | text         |  20.000 |  18.000 |    18.000 |       0.000 |     18.000 |      1.000 |       1.000 |         1.000 |       1.000 |      nan     |
| hybrid    | forced     | version      |  20.000 |  18.000 |    11.000 |       7.000 |     18.000 |      0.611 |       0.222 |         1.000 |       0.611 |        0.389 |

## 反復間のばらつき（SPEC §5-4）

| arm       | mode       | channel      |   accuracy_mean |   accuracy_min |   accuracy_max |   n_repeats |
|:----------|:-----------|:-------------|----------------:|---------------:|---------------:|------------:|
| agentic   | abstain_ok | chart_native |           0.722 |          0.667 |          0.833 |           3 |
| agentic   | abstain_ok | chart_only   |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | cross_file   |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | format       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | formula      |           0.833 |          0.833 |          0.833 |           3 |
| agentic   | abstain_ok | hidden       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | layout       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | locked       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | scanned      |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | text         |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | abstain_ok | version      |           0.444 |          0.333 |          0.500 |           3 |
| agentic   | forced     | chart_native |           0.944 |          0.833 |          1.000 |           3 |
| agentic   | forced     | chart_only   |           0.944 |          0.833 |          1.000 |           3 |
| agentic   | forced     | cross_file   |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | format       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | formula      |           0.722 |          0.667 |          0.833 |           3 |
| agentic   | forced     | hidden       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | layout       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | locked       |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | scanned      |           0.944 |          0.833 |          1.000 |           3 |
| agentic   | forced     | text         |           1.000 |          1.000 |          1.000 |           3 |
| agentic   | forced     | version      |           0.556 |          0.500 |          0.667 |           3 |
| classical | abstain_ok | chart_native |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | chart_only   |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | cross_file   |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | format       |           0.000 |          0.000 |          0.000 |           3 |
| classical | abstain_ok | formula      |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | hidden       |           0.000 |          0.000 |          0.000 |           3 |
| classical | abstain_ok | layout       |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | locked       |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | scanned      |           0.333 |          0.333 |          0.333 |           3 |
| classical | abstain_ok | text         |           1.000 |          1.000 |          1.000 |           3 |
| classical | abstain_ok | version      |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | chart_native |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | chart_only   |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | cross_file   |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | format       |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | formula      |           0.500 |          0.500 |          0.500 |           3 |
| classical | forced     | hidden       |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | layout       |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | locked       |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | scanned      |           0.333 |          0.333 |          0.333 |           3 |
| classical | forced     | text         |           1.000 |          1.000 |          1.000 |           3 |
| classical | forced     | version      |           0.778 |          0.667 |          0.833 |           3 |
| hybrid    | abstain_ok | chart_native |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | chart_only   |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | cross_file   |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | format       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | formula      |           0.722 |          0.667 |          0.833 |           3 |
| hybrid    | abstain_ok | hidden       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | layout       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | locked       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | scanned      |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | text         |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | abstain_ok | version      |           0.667 |          0.500 |          0.833 |           3 |
| hybrid    | forced     | chart_native |           0.944 |          0.833 |          1.000 |           3 |
| hybrid    | forced     | chart_only   |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | cross_file   |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | format       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | formula      |           0.722 |          0.667 |          0.833 |           3 |
| hybrid    | forced     | hidden       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | layout       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | locked       |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | scanned      |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | text         |           1.000 |          1.000 |          1.000 |           3 |
| hybrid    | forced     | version      |           0.611 |          0.500 |          0.667 |           3 |

