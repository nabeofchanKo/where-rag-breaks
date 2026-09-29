"""スケーリングの図とレポート（SPEC §6-3、P4 の成果物）。

    uv run python -m eval.scaling \
        --point 151  results/p4-n150-classical results/p4-n150-agentic results/p4-n150-hybrid \
        --point 311  results/p1-seed42-ja-k8 results/p1-version-v2-k8 \
                     results/p2-agentic-forced results/p3-hybrid-forced \
        --out results/p4-scaling

``--point`` の先頭は**その規模のファイル数**、残りはその規模で測った run。
規模ごとに run を束ねる理由は、既存の 311 ファイルの点が複数の run に
分かれているため（`version` だけ作り直した run がある）。同じ規模の中で
同じ (アーム, チャネル, モード) が重なったら、``eval.report`` と同じく
**後に書いた run を採り、上書きを必ず表示する**。

★ **規模ごとに反復回数が違う。** 311 ファイルは N=3、P4 で足した規模は N=1
  （P4 の目的は破綻点の特定なので、N を下げて規模を取った。SPEC §14-9）。
  図とレポートの両方に各点の N を必ず出す。N=1 の点に誤差棒は無い。

★ **強制回答モードだけを使う。** 棄権モードは P4 では測っていない。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from eval.report import Labels, _resolve_overlaps, _save, setup_fonts  # noqa: E402

MODE = "forced"
ARM_ORDER = ("classical", "agentic", "hybrid")
ARM_STYLE = {
    "classical": {"marker": "o", "color": "#1f77b4"},
    "agentic": {"marker": "s", "color": "#d62728"},
    "hybrid": {"marker": "^", "color": "#2ca02c"},
}


def load_points(points: list[list[str]]) -> tuple[pd.DataFrame, list[str]]:
    """``--point N run...`` を読み、``n_files`` 列を付けて連結する。"""
    frames: list[pd.DataFrame] = []
    notes: list[str] = []
    for point in points:
        label, runs = int(point[0]), [Path(r) for r in point[1:]]
        parts: list[pd.DataFrame] = []
        for run in runs:
            meta = json.loads((run / "meta.json").read_text(encoding="utf-8"))
            actual = meta["corpus"]["n_files_written"]
            if actual != label:
                # 既存の 311 の点は、version を作り直す前の 308 ファイルの run を含む。
                # 黙って混ぜず、どの run がどのコーパスで測られたかを必ず出す。
                notes.append(f"{run.name}: コーパスは {actual} ファイル（{label} の点に含めた）")
            frame = pd.read_csv(run / "scored.csv")
            parts.append(frame[frame["mode"] == MODE])
        merged = pd.concat(parts, ignore_index=True)
        merged, overridden = _resolve_overlaps(merged, [r.name for r in runs])
        for arm, channel, dropped, kept in overridden:
            notes.append(f"{label} ファイル: {arm}/{channel} は {dropped} を {kept} で上書き")
        merged["n_files"] = label
        frames.append(merged)
    return pd.concat(frames, ignore_index=True), notes


def summarise(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """規模 × アーム（× チャネル）の集計。ばらつきは反復ごとの正答率の min/max。"""
    per_repeat = (
        frame.groupby([*keys, "repeat"])
        .agg(accuracy=("correct", "mean"))
        .reset_index()
        .groupby(keys)
        .agg(acc_min=("accuracy", "min"), acc_max=("accuracy", "max"), n_repeats=("repeat", "nunique"))
    )
    frame = frame.assign(incorrect=frame["answered"] & ~frame["correct"])
    main = frame.groupby(keys).agg(
        n=("qid", "count"),
        accuracy=("correct", "mean"),
        correct=("correct", "sum"),
        incorrect=("incorrect", "sum"),
        cost_usd=("cost_usd", "mean"),
        latency_s=("latency_s", "mean"),
        tool_calls=("tool_calls", "mean"),
        errors=("error", lambda s: int(s.notna().sum())),
    )
    out = main.join(per_repeat).reset_index()
    out["penalized"] = (out["correct"] - out["incorrect"]) / out["n"]
    return out.drop(columns=["correct", "incorrect"])


def scaling_figure(summary: pd.DataFrame, out: Path, lab: Labels, auth: str) -> Path:
    """横軸=ファイル数（対数）。正答率・1問コスト・1問秒の 3 枚組。"""
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    panels = (
        ("accuracy", lab("正答率", "accuracy")),
        ("cost_usd", lab("1問あたりコスト（USD）", "cost per question (USD)")),
        ("latency_s", lab("1問あたり秒", "seconds per question")),
    )
    for ax, (column, ylabel) in zip(axes, panels, strict=True):
        for arm in [a for a in ARM_ORDER if a in set(summary["arm"])]:
            part = summary[summary["arm"] == arm].sort_values("n_files")
            style = ARM_STYLE[arm]
            ax.plot(part["n_files"], part[column], label=arm, linewidth=2, **style)
            if column == "accuracy":
                spread = part[part["n_repeats"] > 1]
                ax.vlines(
                    spread["n_files"], spread["acc_min"], spread["acc_max"],
                    color=style["color"], alpha=0.5, linewidth=4,
                )
        ax.set_xscale("log")
        ax.set_xticks(sorted(summary["n_files"].unique()))
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
        ax.minorticks_off()
        ax.set_xlabel(lab("コーパスのファイル数（対数）", "files in corpus (log)"))
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
        if column == "accuracy":
            ax.set_ylim(-0.05, 1.05)
            ax.legend(title=lab("アーム", "arm"))

    repeats = (
        summary.groupby("n_files")["n_repeats"].max().sort_index()
    )
    n_note = ", ".join(f"{n:,}={r}" for n, r in repeats.items())
    note = lab(
        f"強制回答モード。反復回数 N（ファイル数=N）: {n_note}。"
        "縦の帯は N>1 の点の反復間 min/max。",
        f"Forced mode. Repeats N (files=N): {n_note}. Bars show min/max across repeats where N>1.",
    )
    if auth == "cli":
        note += lab(
            "\nコストは定価換算の参考値（cli 認証）であり実請求額ではない。",
            "\nCost is a list-price estimate (cli auth), not an amount billed.",
        )
    fig.suptitle(lab("コーパス規模と正答率・コスト・時間", "Corpus size versus accuracy, cost, time"))
    fig.text(0.5, -0.05, note, ha="center", fontsize=9)
    path = out / "scaling.png"
    _save(fig, path)
    return path


def channel_figure(summary: pd.DataFrame, out: Path, lab: Labels) -> Path:
    """チャネルごとの小さな図。どのチャネルから崩れるかを見る。"""
    channels = sorted(summary["channel"].unique())
    cols = 4
    rows = -(-len(channels) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows), sharex=True, sharey=True)
    for ax, channel in zip(axes.flat, channels, strict=False):
        part = summary[summary["channel"] == channel]
        for arm in [a for a in ARM_ORDER if a in set(part["arm"])]:
            line = part[part["arm"] == arm].sort_values("n_files")
            ax.plot(line["n_files"], line["accuracy"], label=arm, **ARM_STYLE[arm])
        ax.set_title(channel, fontsize=10)
        ax.set_xscale("log")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3)
    for ax in list(axes.flat)[len(channels):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(lab("チャネル別 規模と正答率（強制回答）", "Accuracy by channel and corpus size (forced)"))
    fig.supxlabel(lab("コーパスのファイル数（対数）", "files in corpus (log)"))
    path = out / "scaling_by_channel.png"
    _save(fig, path)
    return path


def write_markdown(
    out: Path, overall: pd.DataFrame, by_channel: pd.DataFrame, notes: list[str], figures: list[Path]
) -> Path:
    def table(df: pd.DataFrame) -> str:
        return df.to_markdown(index=False, floatfmt=".3f")

    lines = [
        "# スケーリング（P4）",
        "",
        "強制回答モードのみ。規模ごとの反復回数 N は `n_repeats` 列を参照"
        "（311 ファイルは N=3、P4 で足した規模は N=1）。",
        "",
        "## 図",
        "",
        *[f"![{p.stem}](figures/{p.name})" for p in figures],
        "",
        "## 規模 × アーム",
        "",
        table(overall),
        "",
        "## 規模 × アーム × チャネル",
        "",
        table(by_channel),
        "",
        "## 束ねた run についての注記",
        "",
        *([f"- {n}" for n in notes] or ["- なし"]),
        "",
    ]
    path = out / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(
        prog="python -m eval.scaling", description="規模ごとの run を束ねて scaling.png を出す。"
    )
    p.add_argument(
        "--point",
        nargs="+",
        action="append",
        required=True,
        metavar="N_FILES RUN",
        help="規模のファイル数と、その規模で測った run（複数）",
    )
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    frame, notes = load_points(args.point)
    for note in notes:
        print(f"  {note}")

    first_run = Path(args.point[0][1])
    auth = json.loads((first_run / "meta.json").read_text(encoding="utf-8")).get("auth", "")

    overall = summarise(frame, ["n_files", "arm"])
    by_channel = summarise(frame, ["n_files", "arm", "channel"])

    lab = Labels(setup_fonts())
    figures_dir = args.out / "figures"
    figures = [
        scaling_figure(overall, figures_dir, lab, auth),
        channel_figure(by_channel, figures_dir, lab),
    ]
    report = write_markdown(args.out, overall, by_channel, notes, figures)

    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print(overall.to_string(index=False))
    for path in [*figures, report]:
        print(f"出力: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
