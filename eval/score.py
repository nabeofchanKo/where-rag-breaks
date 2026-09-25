"""採点（SPEC §5-1 / §5-2）。

    uv run python -m eval.score --run results/<run_id>

採点は 2 段:
    1. **正規化 exact match（主）** — 空白・全角半角・桁区切り・末尾句読点を
       正規化し、``answer`` と ``answer_aliases`` のいずれかに一致で正解
    2. **LLM judge（副）** — exact で外れた回答**だけ**を判定にかける。
       judge のモデルとプロンプトは固定して meta に記録する

judge が exact と食い違った件数は必ずレポートする（採点の信頼区間として）。

★ SPEC §11: **結果を見てから採点基準を変えない。** ``answer_aliases`` は
生成時に確定している。事後に足した場合はレポートに明記すること。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from gen.common import Item, normalize_text, read_questions_jsonl

# arms.llm は claude-agent-sdk（arms 依存グループ）を引く。exact match だけを
# 使いたい呼び出し側（CI のテスト）が重い依存なしで import できるよう遅延させる。

JUDGE_SYSTEM = """\
あなたは短答式の採点者である。表記の揺れだけを吸収し、意味が異なるものは
容赦なく不正解にすること。数値は単位と桁が一致して初めて正解とする。
"""

JUDGE_TEMPLATE = """\
## 設問
{question}

## 正解（これと同義なら正解）
{answer}

## 許容表記
{aliases}

## 採点対象の回答
{candidate}

## 出力形式
次の JSON だけを出力せよ。
{{"correct": true/false, "reason": "20字程度の理由"}}
"""


def matches_decoy(item: Item, candidate: str) -> bool:
    """回答が「囮」に一致したか。

    囮は「間違えるならこう間違えるはず」と生成時に予測した値
    （例: 陳腐化したキャッシュ値）。単に不正解なのと、**設計どおりの
    間違え方をした**のとでは意味がまったく違う。後者はチャネルの罠が
    狙いどおり効いた証拠なので、別に数える。
    """
    if not candidate.strip() or not item.decoys:
        return False
    normalized = normalize_text(candidate)
    return any(normalize_text(d) == normalized for d in item.decoys)


def exact_match(item: Item, candidate: str) -> bool:
    """正規化 exact match。空回答は常に不正解。"""
    if not candidate.strip():
        return False
    normalized = normalize_text(candidate)
    return any(normalize_text(a) == normalized for a in item.accepted)


def judge(item: Item, candidate: str, model: str) -> tuple[bool, str]:
    """exact で外れた回答だけを LLM に判定させる。"""
    from arms.llm import complete, parse_json_answer

    prompt = JUDGE_TEMPLATE.format(
        question=item.question,
        answer=item.answer,
        aliases=", ".join(item.answer_aliases) or "(なし)",
        candidate=candidate,
    )
    result = complete(prompt, system_prompt=JUDGE_SYSTEM, model=model, allowed_tools=[])
    payload = parse_json_answer(result.text)
    return bool(payload.get("correct", False)), str(payload.get("reason", ""))


def score_rows(
    rows: list[dict], items: dict[str, Item], *, use_judge: bool, judge_model: str
) -> pd.DataFrame:
    scored: list[dict] = []
    disagreements = 0

    for row in rows:
        item = items[row["qid"]]
        candidate = row.get("answer", "") or ""
        abstained = bool(row.get("abstained", False))

        by_exact = exact_match(item, candidate)
        correct = by_exact
        judged_by = "exact"
        judge_reason = ""

        # 棄権した回答は判定にかけない（棄権は 0 点であって誤答ではない）
        if use_judge and not by_exact and not abstained and candidate.strip():
            by_judge, judge_reason = judge(item, candidate, judge_model)
            if by_judge:
                correct = True
                judged_by = "judge"
                disagreements += 1

        scored.append(
            {
                **row,
                "correct": bool(correct),
                "judged_by": judged_by,
                "judge_reason": judge_reason,
                "answered": bool(candidate.strip()) and not abstained,
                "answered_decoy": matches_decoy(item, candidate),
                "has_decoy": bool(item.decoys),
            }
        )

    frame = pd.DataFrame(scored)
    frame.attrs["judge_disagreements"] = disagreements
    return frame


def summarise(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """SPEC §5-2 の 4 指標。棄権の扱いで結論が変わるので全部出す。"""

    def agg(group: pd.DataFrame) -> pd.Series:
        total = len(group)
        correct = int(group["correct"].sum())
        answered = int(group["answered"].sum())
        incorrect = answered - correct
        with_decoy = int(group["has_decoy"].sum())
        took_decoy = int(group["answered_decoy"].sum())
        return pd.Series(
            {
                "total": total,
                "correct": correct,
                "incorrect": incorrect,
                "answered": answered,
                "accuracy": correct / total if total else 0.0,
                "penalized": (correct - incorrect) / total if total else 0.0,
                "answer_rate": answered / total if total else 0.0,
                "precision": correct / answered if answered else 0.0,
                # 「設計どおりの間違え方」をした割合。囮のある設問だけが母数。
                "decoy_rate": took_decoy / with_decoy if with_decoy else float("nan"),
            }
        )

    return frame.groupby(by, dropna=False).apply(agg, include_groups=False).reset_index()


def summarise_with_spread(frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """反復間のばらつきを併記する（SPEC §5-4: 1発取りの数字を結論にしない）。"""
    per_repeat = summarise(frame, [*by, "repeat"])
    return (
        per_repeat.groupby(by, dropna=False)["accuracy"]
        .agg(accuracy_mean="mean", accuracy_min="min", accuracy_max="max", n_repeats="count")
        .reset_index()
    )


def best_k_per_channel(frame: pd.DataFrame) -> pd.DataFrame:
    """SPEC §4-1: k=5 固定で殴らず、**チャネルごとの最良 k** で評価する。"""
    per_k = summarise(frame, ["arm", "mode", "channel", "k"])
    idx = per_k.groupby(["arm", "mode", "channel"], dropna=False)["accuracy"].idxmax()
    return per_k.loc[idx].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(prog="python -m eval.score", description="raw.jsonl を採点する。")
    p.add_argument("--run", type=Path, required=True, help="results/<run_id>")
    p.add_argument("--corpus", type=Path, default=Path("corpus"))
    p.add_argument(
        "--no-judge", action="store_true", help="LLM judge を使わず exact match だけで採点する"
    )
    p.add_argument("--judge-model", default="", help="judge のモデル（既定: 本体と同じ）")
    args = p.parse_args(argv)

    from arms.llm import bootstrap, resolve_model

    bootstrap()

    raw_path = args.run / "raw.jsonl"
    if not raw_path.is_file():
        print(f"raw.jsonl が無い: {raw_path}", file=sys.stderr)
        return 2

    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line]
    items = {it.qid: it for it in read_questions_jsonl(args.corpus / "questions.jsonl")}

    judge_model = args.judge_model or resolve_model()
    frame = score_rows(rows, items, use_judge=not args.no_judge, judge_model=judge_model)

    out_csv = args.run / "scored.csv"
    frame.to_csv(out_csv, index=False, encoding="utf-8-sig")

    channel_summary = summarise(frame, ["arm", "mode", "channel"])
    spread = summarise_with_spread(frame, ["arm", "mode", "channel"])
    best_k = best_k_per_channel(frame)

    for name, table in (
        ("summary_by_channel.csv", channel_summary),
        ("spread_by_channel.csv", spread),
        ("best_k_by_channel.csv", best_k),
    ):
        table.to_csv(args.run / name, index=False, encoding="utf-8-sig")

    disagreements = frame.attrs.get("judge_disagreements", 0)
    (args.run / "scoring_meta.json").write_text(
        json.dumps(
            {
                "judge_used": not args.no_judge,
                "judge_model": None if args.no_judge else judge_model,
                "judge_system_prompt": None if args.no_judge else JUDGE_SYSTEM,
                "judge_overrode_exact": disagreements,
                "n_rows": len(frame),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    pd.set_option("display.width", 160)
    print("── チャネル別（全 k をまとめた素の集計）────────────────")
    print(channel_summary.to_string(index=False))
    print()
    by_difficulty = summarise(frame, ["arm", "mode", "channel", "difficulty"])
    by_difficulty.to_csv(args.run / "summary_by_difficulty.csv", index=False, encoding="utf-8-sig")

    print("── 難易度別（= 罠の機構別）──────────────────────────────")
    print(by_difficulty.to_string(index=False))
    print()
    print("decoy_rate … 囮（陳腐化したキャッシュ値など）をそのまま答えた割合。")
    print("             囮のある設問だけが母数。NaN は囮のない段。")
    print()
    print("── チャネルごとの最良 k（SPEC §4-1）────────────────────")
    print(best_k.to_string(index=False))
    print()
    print("── 反復間のばらつき（SPEC §5-4）────────────────────────")
    print(spread.to_string(index=False))
    print()
    print(f"judge が exact を覆した件数: {disagreements}")
    print(f"出力: {out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
