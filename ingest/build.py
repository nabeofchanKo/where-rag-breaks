"""Arm B / C の索引を作る — カタログ + Markdown ミラー（SPEC §4-2）。

    uv run python -m ingest.build --corpus corpus/ --out corpus/_index

生成物:
    ``catalog.md``   1ファイル1行。パス・種別・サイズ・見出し行だけ
    ``mirror/``      各ファイルの抽出テキストを Markdown にしたもの

★ **公平性のための設計判断（重要）**

ミラーは **Arm A とまったく同じ抽出器** (``arms.classical.extract``) で作る。

もしミラー作成時だけ発表者ノートやセルの塗り色まで拾ってしまうと、
Arm B の優位は「エージェントが自力で見つけた」からではなく
「前処理が優遇されていた」からになり、比較が成立しなくなる。

**Arm B の強みは索引ではなく道具にある。** ミラーに出てこない答えは、
``run_python`` で原本を開く／``view_image`` で画像を見る、という
エージェント自身の行動でしか取れない。そこが測りたい差である。

カタログも同じ理由で**見出し行しか載せない**。本文を要約して載せると、
そこに答えが混ざって漏洩検査を通っても実質的なヒントになる。
``eval/leak_check.py --catalog`` が答えの漏れを検査する。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arms.classical.extract import SUPPORTED, extract_file

# カタログの見出し行はここで切る。長い本文が入るとヒントになる。
HEADLINE_CHARS = 60


def _headline(path: Path, rel: str) -> str:
    """カタログに載せる 1 行。抽出できた**最初の行だけ**。"""
    if path.suffix.lower() not in SUPPORTED:
        return "（テキスト抽出不可）"
    blocks = extract_file(path, rel)
    if not blocks:
        return "（テキスト抽出不可）"
    first = next((line.strip() for line in blocks[0].text.split("\n") if line.strip()), "")
    return first[:HEADLINE_CHARS] or "（テキスト抽出不可）"


def build(corpus: Path, out: Path) -> dict:
    files_dir = corpus / "files"
    mirror_dir = out / "mirror"

    if out.exists():
        import shutil

        shutil.rmtree(out)
    mirror_dir.mkdir(parents=True)

    rows: list[str] = []
    n_mirrored = 0

    for path in sorted(files_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(files_dir).as_posix()
        size = path.stat().st_size
        rows.append(f"| `{rel}` | {path.suffix.lstrip('.')} | {size:,} | {_headline(path, rel)} |")

        blocks = extract_file(path, rel) if path.suffix.lower() in SUPPORTED else []
        if not blocks:
            continue
        body = [f"# {rel}", ""]
        for block in blocks:
            body += [f"## {block.locator}", "", block.text, ""]
        mirror_path = mirror_dir / (rel + ".md")
        mirror_path.parent.mkdir(parents=True, exist_ok=True)
        mirror_path.write_text("\n".join(body), encoding="utf-8", newline="\n")
        n_mirrored += 1

    catalog = [
        "# ファイルカタログ",
        "",
        f"コーパス内の全 {len(rows)} ファイル。",
        "",
        "- `mirror/<パス>.md` に、テキスト抽出できたファイルの内容が置いてある",
        "- 「（テキスト抽出不可）」の行はミラーが無い。原本を直接扱う必要がある",
        "",
        "| パス | 種別 | バイト | 見出し |",
        "|---|---|---|---|",
        *rows,
        "",
    ]
    (out / "catalog.md").write_text("\n".join(catalog), encoding="utf-8", newline="\n")

    return {"n_files": len(rows), "n_mirrored": n_mirrored, "catalog": str(out / "catalog.md")}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(
        prog="python -m ingest.build",
        description="Arm B / C 用のカタログと Markdown ミラーを作る。",
    )
    p.add_argument("--corpus", type=Path, default=Path("corpus"))
    p.add_argument("--out", type=Path, default=None, help="既定: <corpus>/_index")
    args = p.parse_args(argv)

    out = args.out or (args.corpus / "_index")
    info = build(args.corpus, out)
    print(f"カタログ    : {info['catalog']}")
    print(f"ファイル数  : {info['n_files']}")
    print(f"ミラー作成  : {info['n_mirrored']}（残りはテキスト抽出不可）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
