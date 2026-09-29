"""規模プローブ — P4 の本番前に、LLM を呼ばずに「規模が何を難しくするか」を測る。

    uv run python -m eval.scale_probe --corpus corpus-150/ --corpus corpus-1000/ \
        --corpus corpus-5000/ --out results/probe-p4-scaling

なぜこれを作るのか:
    H3（SPEC §2）は「規模が大きくなると agentic が苦しくなり、hybrid が救う」
    という主張である。だが規模を大きくしても、**各アームが実際に何に
    苦しむのか**は LLM を回す前に機械的に分かる部分が多い。何時間もの run を
    回してから「そもそも規模が難しさになっていなかった」と知るのを避ける
    （規律「LLM を呼ぶ前に LLM 不要の検査で確かめる」）。

測る指標（1問ごと）:
    Arm A  a_file_recall@k    上位 k チャンクに答えのファイルが入ったか
    Arm C  c_all_sources      絞り込み候補に答えのファイルが**すべて**入ったか。
                              入らなければ、その問題はエージェントが何をしても解けない
           c_n_candidates     候補の件数（付随ファイルを含む）
           c_companion_capped 付随ファイルが頭打ち（2N 件）に達したか。達していると、
                              索引不能な答えのファイルが名前順で切り捨てられうる
    Arm B  b_key_path_hits    設問中のコード（例: PRJ-1234）をパスに含むファイル数。
                              1 桁のままなら、規模が増えても list_files 一発で届く
           b_key_grep_hits    同じコードを含むミラーの行数（grep の上限は 60 件）

コーパス単位:
    catalog_chars / catalog_rows_visible
        read_file は 20,000 文字で切る。カタログの何行目までが見えるか。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from arms.agentic.tools import MAX_CHARS, MAX_GREP_HITS
from arms.hybrid.arm import DEFAULT_N_FILES, HybridArm
from arms.llm import bootstrap
from gen.__main__ import _tree_fingerprint
from gen.common import hash_tree, read_questions_jsonl

# 設問に埋め込まれた文書コード。全チャネルがこの形を持つ
KEY_PATTERN = re.compile(r"\b([A-Z]{2,3}-\d{4})\b")
A_K = 8


def _catalog_stats(index_dir: Path) -> dict:
    body = (index_dir / "catalog.md").read_text(encoding="utf-8")
    rows = [line for line in body.split("\n") if line.startswith("| `")]
    visible = [line for line in body[:MAX_CHARS].split("\n") if line.startswith("| `")]
    return {
        "catalog_chars": len(body),
        "catalog_rows": len(rows),
        "catalog_rows_visible": len(visible),
    }


def _fingerprint(corpus: Path) -> str:
    """gen が表示する指紋と同じもの。索引（_index/）は生成物ではないので除く。"""
    digest = {k: v for k, v in hash_tree(corpus).items() if not k.startswith("_index/")}
    return _tree_fingerprint(digest)


def probe_corpus(corpus: Path) -> tuple[pd.DataFrame, dict]:
    meta = json.loads((corpus / "meta.json").read_text(encoding="utf-8"))
    items = read_questions_jsonl(corpus / "questions.jsonl")

    arm = HybridArm(k=DEFAULT_N_FILES, model="probe-no-llm")
    arm.prepare(corpus, meta["locale"])
    index = arm.classical._require_index()  # noqa: SLF001

    files_dir = corpus.resolve() / "files"
    all_paths = [p.relative_to(files_dir).as_posix() for p in files_dir.rglob("*") if p.is_file()]
    mirror_dir = corpus.resolve() / "_index" / "mirror"
    mirror_lines = [
        line
        for path in mirror_dir.rglob("*.md")
        for line in path.read_text(encoding="utf-8").split("\n")
    ]

    rows: list[dict] = []
    for item in items:
        sources = set(item.source_files)

        hits = index.search(item.question, A_K)
        a_recall = bool(sources & {h.chunk.path for h in hits})

        candidates = arm._candidate_files(item.question)  # noqa: SLF001
        n_selected = min(DEFAULT_N_FILES, len(candidates))
        companions = candidates[n_selected:]

        match = KEY_PATTERN.search(item.question)
        key = match.group(1) if match else ""
        key_lower = key.lower()

        rows.append(
            {
                "n_files": meta["n_files_written"],
                "qid": item.qid,
                "channel": item.channel,
                "difficulty": item.difficulty,
                f"a_file_recall@{A_K}": a_recall,
                "c_all_sources": sources <= set(candidates),
                "c_any_source": bool(sources & set(candidates)),
                "c_n_candidates": len(candidates),
                "c_companion_capped": len(companions) >= DEFAULT_N_FILES * 2,
                "key": key,
                "b_key_path_hits": sum(
                    1 for p in all_paths if key_lower and key_lower in p.lower()
                ),
                "b_key_grep_hits": sum(1 for line in mirror_lines if key and key in line),
            }
        )

    info = {
        "corpus": str(corpus),
        "fingerprint": _fingerprint(corpus),
        "meta": meta,
        "n_chunks": len(index.chunks),
        "n_candidate_files": DEFAULT_N_FILES,
        **_catalog_stats(corpus / "_index"),
        "max_chars": MAX_CHARS,
        "max_grep_hits": MAX_GREP_HITS,
    }
    return pd.DataFrame(rows), info


def summarise(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["n_files", "channel"])
        .agg(
            n=("qid", "count"),
            a_recall=(f"a_file_recall@{A_K}", "mean"),
            c_all=("c_all_sources", "mean"),
            c_cands=("c_n_candidates", "mean"),
            c_capped=("c_companion_capped", "mean"),
            b_path_max=("b_key_path_hits", "max"),
            b_grep_max=("b_key_grep_hits", "max"),
        )
        .reset_index()
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    bootstrap()

    p = argparse.ArgumentParser(
        prog="python -m eval.scale_probe",
        description="LLM を呼ばずに、規模が各アームの何を難しくするかを測る。",
    )
    p.add_argument("--corpus", type=Path, action="append", required=True, help="複数指定可")
    p.add_argument("--out", type=Path, default=None, help="結果の保存先ディレクトリ")
    args = p.parse_args(argv)

    frames: list[pd.DataFrame] = []
    infos: list[dict] = []
    for corpus in args.corpus:
        frame, info = probe_corpus(corpus)
        frames.append(frame)
        infos.append(info)
        print(
            f"{corpus}: {info['meta']['n_files_written']} ファイル / "
            f"{info['n_chunks']} チャンク / 指紋 {info['fingerprint']} / "
            f"カタログ {info['catalog_rows']} 行中 {info['catalog_rows_visible']} 行が見える"
        )

    frame = pd.concat(frames, ignore_index=True)
    summary = summarise(frame)
    overall = (
        frame.groupby("n_files")
        .agg(
            a_recall=(f"a_file_recall@{A_K}", "mean"),
            c_all=("c_all_sources", "mean"),
            c_cands=("c_n_candidates", "mean"),
            c_capped=("c_companion_capped", "mean"),
            b_path_max=("b_key_path_hits", "max"),
            b_grep_max=("b_key_grep_hits", "max"),
        )
        .reset_index()
    )

    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print()
    print("── 規模プローブ（LLM 未使用）── 全体 ─────────────────────")
    print(overall.to_string(index=False))
    print()
    print("── チャネル別 ───────────────────────────────────────────")
    print(summary.to_string(index=False))

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out / "scale_probe_raw.csv", index=False, encoding="utf-8-sig")
        summary.to_csv(args.out / "scale_probe_summary.csv", index=False, encoding="utf-8-sig")
        (args.out / "scale_probe_meta.json").write_text(
            json.dumps(infos, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\n保存先: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
