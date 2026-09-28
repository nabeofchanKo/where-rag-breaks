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
    """行=チャネル、列=アーム×難易度 の正答率ヒートマップ。

    SPEC §6-1 はチャネル×アームだが、難易度が「罠の機構」そのものなので
    列を (arm, difficulty) にして機構ごとの効き方が見えるようにしてある。

    ★ 行に (channel, difficulty) を積むと 33 行の縦長になって読めない。
      チャネルを行、難易度を列に置くと **同じ行の中で段の落ち方**が並ぶので、
      「コントロール段は緑・罠の段は赤」という主張が一目で分かる。
    """
    subset = frame[frame["mode"] == mode]
    pivot = (
        subset.groupby(["channel", "arm", "difficulty"])["correct"]
        .mean()
        .unstack(["arm", "difficulty"])
        .sort_index()
    )
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)

    arms = sorted({arm for arm, _ in pivot.columns})
    tier = (lambda d: f"難易度{d}") if lab.ja else (lambda d: f"tier {d}")
    labels = [
        tier(d) if len(arms) == 1 else f"{arm}\n{tier(d)}" for arm, d in pivot.columns
    ]

    fig, ax = plt.subplots(figsize=(2.6 + 1.3 * len(pivot.columns), 0.45 * len(pivot) + 2.4))
    data = pivot.to_numpy(dtype=float)
    im = ax.imshow(data, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")

    ax.set_xticks(range(len(pivot.columns)), labels)
    ax.set_yticks(range(len(pivot)), list(pivot.index))

    # アームの切れ目に縦線を入れる。どこまでが同じアームか一目で分かるように。
    for index in range(1, len(pivot.columns)):
        if pivot.columns[index][0] != pivot.columns[index - 1][0]:
            ax.axvline(index - 0.5, color="white", linewidth=3)
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
    suffix = "" if mode == "forced" else f"_{mode}"
    path = out / f"channel_heatmap{suffix}.png"
    _save(fig, path)
    return path


# ── 2. コスト × 正答率 ─────────────────────────────────────────────
def estimate_cli_overhead(frame: pd.DataFrame) -> int:  # noqa: D401
    """1 呼出あたりの固定オーバーヘッドを run 自体から推定する。

    ``input_tokens ≈ a + b×k`` の切片 a を採る。k が 1 種類しかない run では
    回帰できないので、観測された最小 input_tokens を上限として使う。
    """
    usable = frame.dropna(subset=["k"])
    observed_min = int(frame["input_tokens"].min())
    if usable.empty or usable["k"].nunique() < 2:
        return observed_min
    frame = usable
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


def _resolve_overlaps(
    frame: pd.DataFrame, order: list[str]
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    """同じ (アーム, チャネル) が複数の run にあるとき、**後の run を採る**。

    ★ なぜ必要か:
        チャネルの設計を直して測り直すと、同じアーム・同じチャネルの結果が
        古い run と新しい run の両方に残る。素朴に連結すると新旧が混ざった
        平均になり、**どちらの設計の数字なのか分からない図**ができる。

        `--also` に渡した順を優先度とし、後に指定した run が上書きする。
        上書きが起きたら必ず標準出力に出す（黙って捨てない）。
    """
    rank = {name: index for index, name in enumerate(order)}
    frame = frame.copy()
    frame["_rank"] = frame["run_id"].map(lambda r: rank.get(r, -1))

    overridden: list[tuple[str, str, str, str]] = []
    keep_index: list[int] = []
    for (arm, channel), group in frame.groupby(["arm", "channel"], dropna=False):
        best = group["_rank"].max()
        winners = group[group["_rank"] == best]
        losers = group[group["_rank"] != best]
        if not losers.empty:
            overridden.append(
                (
                    str(arm),
                    str(channel),
                    ", ".join(sorted(losers["run_id"].unique())),
                    ", ".join(sorted(winners["run_id"].unique())),
                )
            )
        keep_index.extend(winners.index.tolist())

    return frame.loc[sorted(keep_index)].drop(columns="_rank"), overridden


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
        *(
            [
                f"- 重ねた run: {', '.join(meta['merged_runs'])}"
                "（同じアーム×チャネルが重複した場合は後の run を採用）"
            ]
            if meta.get("merged_runs")
            else []
        ),
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
    p.add_argument(
        "--also",
        type=Path,
        action="append",
        default=[],
        help=(
            "別 run の scored.csv を重ねてアーム比較にする（複数指定可）。"
            "図と表だけが合算され、レポートの実行条件は --run のものを載せる"
        ),
    )
    p.add_argument("--mode", default="forced", help="ヒートマップに使う棄権モード（既定: forced）")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "出力先（既定: --run と同じ場所）。--also で複数 run を重ねるときは"
            "必ず別の場所を指定すること。指定しないと単一 run の図を上書きしてしまう"
        ),
    )
    args = p.parse_args(argv)

    scored = args.run / "scored.csv"
    if not scored.is_file():
        print(f"scored.csv が無い。先に eval.score を実行すること: {scored}", file=sys.stderr)
        return 2

    frame = pd.read_csv(scored)
    extra_runs: list[str] = []
    for other in args.also:
        other_scored = other / "scored.csv"
        if not other_scored.is_file():
            print(f"scored.csv が無い: {other_scored}", file=sys.stderr)
            return 2
        frame = pd.concat([frame, pd.read_csv(other_scored)], ignore_index=True)
        extra_runs.append(other.name)
    if extra_runs:
        frame, overridden = _resolve_overlaps(frame, [args.run.name, *extra_runs])
        for arm, channel, dropped, kept in overridden:
            print(f"  {arm}/{channel}: {dropped} を {kept} で上書きした")
    meta = json.loads((args.run / "meta.json").read_text(encoding="utf-8"))
    if extra_runs:
        # どの run を重ねたかは必ず残す。図だけ見て出所が分からない状態にしない。
        meta["merged_runs"] = [meta.get("run_id", args.run.name), *extra_runs]
        meta["arms"] = sorted(frame["arm"].unique())

    japanese = setup_fonts()
    lab = Labels(japanese)
    if not japanese:
        print("⚠️ 日本語フォントが見つからないため、図のラベルは英語で出力する")

    out_dir = args.out or args.run
    if args.also and args.out is None:
        print(
            "エラー: --also を使うときは --out で別の出力先を指定すること"
            f"（{args.run} の単一アームの図を上書きしてしまう）",
            file=sys.stderr,
        )
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    figures = []
    # 棄権あり／なしの対比がこのベンチマークの主張の核なので、両方出す。
    for mode in sorted(frame["mode"].unique(), key=lambda m: m != args.mode):
        figures.append(channel_heatmap(frame, figures_dir, lab, mode))
    figures.append(cost_accuracy(frame, figures_dir, lab, meta.get("auth", "")))
    report = write_markdown(out_dir, frame, meta, figures)

    for path in [*figures, report]:
        print(f"出力: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
