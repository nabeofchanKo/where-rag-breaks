"""答えの漏洩検査（SPEC §3-3 / §11）。

    uv run python -m eval.leak_check --corpus corpus/

検査するもの:
    1. 答えがファイル名・フォルダ名に出ていないか
    2. 答えが設問文そのものに出ていないか
    3. 答えが Arm B/C のカタログ（ingest/ の出力）に出ていないか
    4. 設問文が答えの在り処（ファイルパス）を教えていないか
    5. 設問文にチャネル名が漏れていないか（SPEC §3-2）

**なぜ自動化するのか**: 漏洩は一度混入すると、そのチャネルの正答率が
理由もなく上がる。目視レビューでは見落とすし、生成器を直すたびに再発する。
CI で毎回回す。

漏洩が見つかったら終了コード 1 を返す。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from gen.channels import ALL_CHANNELS
from gen.common import Item, normalize_text, read_questions_jsonl

# 短すぎる答えは偶然一致してしまう（"5" が "PRJ-5000" に含まれる等）。
# 偶然一致で CI を落とすと検査そのものが無視されるようになるので、
# 文字列包含での検査は一定長以上に限る。
MIN_LEN_FOR_CONTAINS = 4


@dataclass(frozen=True)
class Leak:
    qid: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.qid}: {self.detail}"


def _paths_of(corpus: Path) -> list[str]:
    """コーパス内の全パス（ファイル名とフォルダ名の両方を含む）。"""
    root = corpus / "files"
    seen: set[str] = set()
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        seen.add(rel.as_posix())
        for parent in rel.parents:
            if parent.as_posix() != ".":
                seen.add(parent.as_posix())
    return sorted(seen)


def _check_item(item: Item, paths: list[str], catalog: str | None) -> list[Leak]:
    leaks: list[Leak] = []
    answer = normalize_text(item.answer)

    if len(answer) >= MIN_LEN_FOR_CONTAINS:
        for path in paths:
            if answer in normalize_text(path):
                leaks.append(
                    Leak(item.qid, "filename", f"答え {item.answer!r} がパス {path!r} に出ている")
                )

        if catalog is not None and answer in normalize_text(catalog):
            leaks.append(Leak(item.qid, "catalog", f"答え {item.answer!r} がカタログに出ている"))

        if answer in normalize_text(item.question):
            leaks.append(Leak(item.qid, "question", f"答え {item.answer!r} が設問文に出ている"))

    # 設問が答えの在り処を教えてはいけない（探索そのものが評価対象のため）
    for rel in item.source_files:
        stem = Path(rel).stem
        if stem and stem.lower() in item.question.lower():
            leaks.append(
                Leak(item.qid, "sourcepath", f"設問文がソースファイル名 {stem!r} を含んでいる")
            )

    # チャネル名を設問文に出さない（SPEC §3-2）
    for channel in ALL_CHANNELS:
        if channel in item.question.lower():
            leaks.append(
                Leak(item.qid, "channelname", f"設問文にチャネル名 {channel!r} が出ている")
            )

    return leaks


def check(corpus: Path, catalog_path: Path | None = None) -> list[Leak]:
    items = read_questions_jsonl(corpus / "questions.jsonl")
    paths = _paths_of(corpus)
    catalog = None
    if catalog_path is not None and catalog_path.is_file():
        catalog = catalog_path.read_text(encoding="utf-8")

    leaks: list[Leak] = []
    for item in items:
        leaks.extend(_check_item(item, paths, catalog))
    return leaks


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(
        prog="python -m eval.leak_check",
        description="答えがファイル名・カタログ・設問文に漏れていないか検査する。",
    )
    p.add_argument("--corpus", type=Path, default=Path("corpus"), help="コーパスの場所")
    p.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help="Arm B/C のカタログ（存在すれば検査対象に加える）",
    )
    args = p.parse_args(argv)

    if not (args.corpus / "questions.jsonl").is_file():
        print(f"コーパスが見つからない: {args.corpus}", file=sys.stderr)
        return 2

    leaks = check(args.corpus, args.catalog)
    n_items = len(read_questions_jsonl(args.corpus / "questions.jsonl"))

    if leaks:
        print(f"❌ FAIL — {n_items} 問中 {len({leak.qid for leak in leaks})} 問で漏洩を検出")
        for leak in leaks:
            print(f"  {leak}")
        return 1

    print(f"✅ PASS — {n_items} 問、漏洩なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
