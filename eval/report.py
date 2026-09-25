"""figures と markdown レポートの生成（SPEC §6）。

    uv run python -m eval.report --run results/<run_id>

このリポジトリの結論は 3 枚の図で示す。

    channel_heatmap.png   チャネル × アーム の正答率ヒートマップ（**主成果物**）
    cost_accuracy.png     1問あたりコスト（対数）× 正答率
    scaling.png           コーパス規模 × 正答率（P4 で複数 run が揃ってから）

★ **コスト軸の注意**:
    Claude CLI は 1 呼出あたり固定のオーバーヘッド（システムプロンプト等）を
    乗せる。生のコストだけを見ると全アームが一律に水増しされ、アーム間の
    差が実際より小さく見える。そのため cost_accuracy.png は
    「生のコスト」と「オーバーヘッドを引いた実質プロンプトトークン」の
    2 枚組にしてある。どちらか片方だけを引用しないこと。

    オーバーヘッドは**定数で持たない。run 自体のデータから推定する。**
    単発で測った値を定数にすると外す（実測: 冷えたキャッシュでの 1 回の値は
    4,327 だったが、432 回の run の平均 input_tokens は 3,131 で、
    引くと負になった）。``input_tokens ≈ a + b×k`` を最小二乗で当て、
    切片 a をオーバーヘッドとする。観測された最小 input_tokens が上限になる
    ので、推定値がそれを超えたら最小値で頭打ちにする。

    また CLI 認証（契約プランの枠）で走らせた場合、``cost_usd`` は定価換算の
    参考値であって実請求額ではない。meta.json の ``auth`` を見て図に明記する。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# 日本語を出せるフォント候補。見つからなければ英語ラベルに落とす。
_CJK_FONTS = ("Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP", "IPAexGothic")


def setup_fonts() -> bool:
    """日本語フォントがあれば設定する。返り値は日本語ラベルを使えるか。"""
    from matplotlib import font_manager

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_FONTS:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


class Labels:
    """日本語フォントが無い環境では英語に落とす。図が豆腐になるより読める方がよい。"""

    def __init__(self, japanese: bool) -> None:
        self.ja = japanese

    def __call__(self, ja: str, en: str) -> str:
        return ja if self.ja else en


def _save(fig: plt.Figure, path: Path) -> None:
    """PNG を決定的に保存する。matplotlib の既定は Software 名を埋め込む。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)


# ── 1. チャネル別ヒートマップ（主成果物）──────────────────────────
def channel_heatmap(frame: pd.DataFrame, out: Path, lab: Labels, mode: str) -> Path:
    """チャネル×難易度 を行、アームを列にした正答率ヒートマップ。

    SPEC §6-1 はチャネル×アームだが、難易度が「罠の機構」そのものなので
    行を (channel, difficulty) にして機構ごとの効き方が見えるようにしてある。
    """
    subset = frame[frame["mode"] == mode]
    pivot = (
        subset.groupby(["channel", "difficulty", "arm"])["correct"]
        .mean()
        .unstack("arm")
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(2.2 + 1.6 * len(pivot.columns), 0.6 * len(pivot) + 2.2))
    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")

    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(
        range(len(pivot)),
        [f"{ch}  (難易度 {d})" if lab.ja else f"{ch}  (tier {d})" for ch, d in pivot.index],
    )
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if not np.isnan(value):
                ax.text(
                    j,
                    i,
                    f"{value:.2f}",
                    ha="center",
                    va="center",
                    color="black" if 0.25 < value < 0.8 else "white",
                    fontweight="bold",
                )

    ax.set_title(
        lab(
            f"チャネル別 正答率（{mode} モード・N={subset['repeat'].nunique()}）",
            f"Accuracy by channel ({mode}, N={subset['repeat'].nunique()})",
        )
    )
    fig.colorbar(im, ax=ax, label=lab("正答率", "accuracy"))
    path = out / "channel_heatmap.png"
    _save(fig, path)
    return path


# ── 2. コスト × 正答率 ─────────────────────────────────────────────
def estimate_cli_overhead(frame: pd.DataFrame) -> int:
    """1 呼出あたりの固定オーバーヘッドを run 自体から推定する。

    ``input_tokens ≈ a + b×k`` の切片 a を採る。k が 1 種類しかない run では
    回帰できないので、観測された最小 input_tokens を上限として使う。
    """
    observed_min = int(frame["input_tokens"].min())
    if frame["k"].nunique() < 2:
        return observed_min
    slope, intercept = np.polyfit(
        frame["k"].to_numpy(float), frame["input_tokens"].to_numpy(float), 1
    )
    return int(max(0, min(intercept, observed_min)))


def cost_accuracy(frame: pd.DataFrame, out: Path, lab: Labels, auth: str) -> Path:
    overhead = estimate_cli_overhead(frame)
    grouped = (
        frame.groupby(["arm", "channel", "k"])
        .agg(
            accuracy=("correct", "mean"),
            cost=("cost_usd", "mean"),
            input_tokens=("input_tokens", "mean"),
        )
        .reset_index()
    )
    grouped["marginal_tokens"] = (grouped["input_tokens"] - overhead).clip(lower=1)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    channels = sorted(grouped["channel"].unique())
    markers = ("o", "s", "^", "D", "v", "P", "X", "*", "<", ">", "h")

    for ax, xcol, xlabel in (
        (
            axes[0],
            "cost",
            lab("1問あたりコスト（USD・対数）", "cost per question (USD, log)"),
        ),
        (
            axes[1],
            "marginal_tokens",
            lab(
                "1問あたり実質プロンプトトークン（対数）",
                "marginal prompt tokens per question (log)",
            ),
        ),
    ):
        for i, channel in enumerate(channels):
            part = grouped[grouped["channel"] == channel].sort_values(xcol)
            ax.plot(
                part[xcol],
                part["accuracy"],
                marker=markers[i % len(markers)],
                label=channel,
            )
            for _, row in part.iterrows():
                ax.annotate(
                    f"k={int(row['k'])}",
                    (row[xcol], row["accuracy"]),
                    textcoords="offset points",
                    xytext=(5, 5),
                    fontsize=8,
                )
        ax.set_xscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(lab("正答率", "accuracy"))
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3)
        ax.legend()

    note = lab(
        f"左は生のコスト。CLI が 1 呼出あたり乗せる固定オーバーヘッドを"
        f"この run から推定すると約 {overhead:,} トークン。右はそれを引いた値。",
        f"Left is raw cost. The fixed per-call overhead estimated from this run is "
        f"~{overhead:,} tokens; the right panel subtracts it.",
    )
    if auth == "cli":
        note += lab(
            "\n認証は cli（契約プランの枠）のため、"
            "コストは定価換算の参考値であり実請求額ではない。",
            "\nAuth was cli (subscription), so cost is a list-price estimate, "
            "not an amount billed.",
        )
    fig.suptitle(lab("コストと正答率", "Cost versus accuracy"))
    fig.text(0.5, -0.04, note, ha="center", fontsize=9)

    path = out / "cost_accuracy.png"
    _save(fig, path)
    return path


# ── 3. markdown レポート ───────────────────────────────────────────
def write_markdown(run: Path, frame: pd.DataFrame, meta: dict, figures: list[Path]) -> Path:
    from eval.score import best_k_per_channel, summarise, summarise_with_spread

    scoring = {}
    scoring_path = run / "scoring_meta.json"
    if scoring_path.is_file():
        scoring = json.loads(scoring_path.read_text(encoding="utf-8"))

    def table(df: pd.DataFrame) -> str:
        return df.to_markdown(index=False, floatfmt=".3f")

    lines = [
        f"# 実行レポート — `{meta.get('run_id', run.name)}`",
        "",
        "## 実行条件",
        "",
        f"- モデル: `{meta.get('model')}`  認証: `{meta.get('auth')}`",
        "- コーパス: seed `{seed}` / locale `{locale}` / generator_version `{gv}`".format(
            seed=meta.get("corpus", {}).get("seed"),
            locale=meta.get("corpus", {}).get("locale"),
            gv=meta.get("corpus", {}).get("generator_version"),
        ),
        f"- アーム: {', '.join(meta.get('arms', []))}",
        f"- k: {meta.get('k_values')}  モード: {meta.get('modes')}  反復: {meta.get('repeats')}",
        f"- CLI の固定オーバーヘッド（この run から推定）: "
        f"**{estimate_cli_overhead(frame):,} トークン/呼出**",
        "",
        "### 索引の構成",
        "",
        "```json",
        json.dumps(meta.get("arm_config", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "### 密閉性の検証（SPEC §4-2）",
        "",
        f"- ツールが結果を返した回数: **{int(frame.get('tool_results', pd.Series([0])).sum())}**"
        "（Arm A は 0 でなければ無効）",
        f"- 往復が 1 回で終わらなかった呼出: "
        f"**{int((frame.get('num_turns', pd.Series([1])) != 1).sum())}**",
        "",
        "### 採点",
        "",
        f"- LLM judge: `{scoring.get('judge_model') or '未使用'}`",
        f"- judge が exact match を覆した件数: **{scoring.get('judge_overrode_exact', 0)}**",
        f"- 囮に一致したため judge にかけなかった件数: "
        f"**{scoring.get('judge_blocked_on_decoy', 0)}**",
        "",
        "採点基準に対する事後変更は"
        " [`docs/scoring-changes.md`](../../docs/scoring-changes.md) を参照。",
        "",
        "## 図",
        "",
    ]
    lines += [f"![{p.stem}](figures/{p.name})" for p in figures]
    lines += [
        "",
        "## チャネル × 難易度（= 罠の機構）",
        "",
        table(summarise(frame, ["arm", "mode", "channel", "difficulty"])),
        "",
        "`decoy_rate` は囮（陳腐化したキャッシュ値など）をそのまま答えた割合。",
        "囮のある設問だけが母数で、NaN は囮のない段。",
        "",
        "## チャネルごとの最良 k（SPEC §4-1）",
        "",
        table(best_k_per_channel(frame)),
        "",
        "## 反復間のばらつき（SPEC §5-4）",
        "",
        table(summarise_with_spread(frame, ["arm", "mode", "channel"])),
        "",
    ]
    path = run / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(
        prog="python -m eval.report", description="figures と markdown レポートを生成する。"
    )
    p.add_argument("--run", type=Path, required=True, help="results/<run_id>")
    p.add_argument("--mode", default="forced", help="ヒートマップに使う棄権モード（既定: forced）")
    args = p.parse_args(argv)

    scored = args.run / "scored.csv"
    if not scored.is_file():
        print(f"scored.csv が無い。先に eval.score を実行すること: {scored}", file=sys.stderr)
        return 2

    frame = pd.read_csv(scored)
    meta = json.loads((args.run / "meta.json").read_text(encoding="utf-8"))

    japanese = setup_fonts()
    lab = Labels(japanese)
    if not japanese:
        print("⚠️ 日本語フォントが見つからないため、図のラベルは英語で出力する")

    figures_dir = args.run / "figures"
    figures = [
        channel_heatmap(frame, figures_dir, lab, args.mode),
        cost_accuracy(frame, figures_dir, lab, meta.get("auth", "")),
    ]
    report = write_markdown(args.run, frame, meta, figures)

    for path in [*figures, report]:
        print(f"出力: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
