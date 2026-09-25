"""コーパス生成の入口。

    python -m gen --seed 42 --files 20 --out corpus/

決定性の約束（SPEC §8 P0 の完了条件）:
    同じ引数で 2 回実行すると、生成される全ファイルがバイト一致する。
    これを成立させるために、
      - 乱数はすべて ``make_rng(seed, ...)`` から引く（時刻・PID を混ぜない）
      - 出力ディレクトリは実行のたびに作り直す（前回の残骸を混ぜない）
      - OOXML は ``normalize_artifact`` でタイムスタンプを固定して詰め直す
      - meta.json に実行時刻を書かない
    tests/test_determinism.py がこれを検証する。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from gen.channels import ALL_CHANNELS, REGISTRY
from gen.common import Item, hash_tree, make_rng, write_questions_jsonl
from gen.locales import get_locale

# コーパスの形式を変える変更を入れたら上げる。meta.json に記録され、
# 「同じ seed なのに中身が違う」の原因追跡に使う。
GENERATOR_VERSION = 2

DEFAULT_QUESTIONS_PER_CHANNEL = 6


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m gen",
        description="正解ラベルつき合成コーパスを決定的に生成する。",
    )
    p.add_argument("--seed", type=int, default=42, help="乱数シード（既定: 42）")
    p.add_argument(
        "--files",
        type=int,
        default=20,
        help=(
            "コーパスの目標総ファイル数。設問に必要なファイルを引いた残りは、"
            "設問を持たないディストラクタで埋める（既定: 20）"
        ),
    )
    p.add_argument(
        "--questions",
        type=int,
        default=DEFAULT_QUESTIONS_PER_CHANNEL,
        help=f"1チャネルあたりの設問数（既定: {DEFAULT_QUESTIONS_PER_CHANNEL}）",
    )
    p.add_argument(
        "--locale",
        default="ja",
        choices=("ja", "en"),
        help="コーパス本文の言語（既定: ja）。ファイル名は常に ASCII",
    )
    p.add_argument(
        "--channels",
        default=",".join(ALL_CHANNELS),
        help=f"生成するチャネル（カンマ区切り）。既定: {','.join(ALL_CHANNELS)}",
    )
    p.add_argument("--out", type=Path, default=Path("corpus"), help="出力先（既定: corpus/）")
    return p


def _resolve_channels(spec: str) -> list[str]:
    names = [c.strip() for c in spec.split(",") if c.strip()]
    unknown = [c for c in names if c not in REGISTRY]
    if unknown:
        raise SystemExit(
            f"未実装のチャネル: {', '.join(unknown)}（実装済み: {', '.join(ALL_CHANNELS)}）"
        )
    return sorted(names)


def generate_corpus(
    seed: int, files: int, questions: int, locale_code: str, channels: list[str], out: Path
) -> dict:
    locale = get_locale(locale_code)
    files_dir = out / "files"

    # 前回の残骸が混ざるとバイト一致が崩れるので作り直す
    if out.exists():
        shutil.rmtree(out)
    files_dir.mkdir(parents=True)

    items: list[Item] = []
    for channel in channels:
        module = REGISTRY[channel]
        rng = make_rng(seed, "questions", channel)
        items.extend(module.generate(rng, files_dir, questions, locale))

    question_files = sum(len(it.source_files) for it in items)
    filler_budget = max(0, files - question_files)

    # ディストラクタをチャネルへ均等配分する。端数は先頭のチャネルから配る。
    base, remainder = divmod(filler_budget, len(channels))
    filler_counts = {
        ch: base + (1 if i < remainder else 0) for i, ch in enumerate(channels)
    }

    filler_paths: list[str] = []
    for channel in channels:
        count = filler_counts[channel]
        if count:
            rng = make_rng(seed, "fillers", channel)
            filler_paths.extend(REGISTRY[channel].generate_fillers(rng, files_dir, count, locale))

    write_questions_jsonl(items, out / "questions.jsonl")

    meta = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "locale": locale_code,
        "channels": channels,
        "questions_per_channel": questions,
        "n_questions": len(items),
        "n_files_requested": files,
        "n_files_written": sum(1 for p in files_dir.rglob("*") if p.is_file()),
        "n_filler_files": len(filler_paths),
        # 実行時刻は書かない（書くと同 seed 再生成のバイト一致が壊れる）
    }
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return meta


def main(argv: list[str] | None = None) -> int:
    # Windows の既定コンソールは cp932 で、日本語の生成ログが化ける
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    channels = _resolve_channels(args.channels)

    meta = generate_corpus(
        seed=args.seed,
        files=args.files,
        questions=args.questions,
        locale_code=args.locale,
        channels=channels,
        out=args.out,
    )

    digest = hash_tree(args.out)
    print(f"生成先          : {args.out}")
    print(f"チャネル        : {', '.join(meta['channels'])}")
    print(f"言語            : {meta['locale']}")
    print(f"設問数          : {meta['n_questions']}")
    print(
        f"ファイル数      : {meta['n_files_written']}"
        f"（うちディストラクタ {meta['n_filler_files']}）"
    )
    print(f"コーパスの指紋  : {_tree_fingerprint(digest)}")
    return 0


def _tree_fingerprint(digest: dict[str, str]) -> str:
    """ツリー全体の要約ハッシュ。目視で同一性を確認するため。"""
    import hashlib

    h = hashlib.sha256()
    for name in sorted(digest):
        h.update(name.encode("utf-8"))
        h.update(digest[name].encode("ascii"))
    return h.hexdigest()[:16]


if __name__ == "__main__":
    sys.exit(main())
