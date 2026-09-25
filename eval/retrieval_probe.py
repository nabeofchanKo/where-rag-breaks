"""検索プローブ — LLM を呼ばずに Arm A の「上限」を測る。

    uv run python -m eval.retrieval_probe --corpus corpus/ --k 4,8,16,32

なぜこれを作るのか:
    Arm A の正答率は「検索が当たったか」と「モデルが読めたか」の積である。
    この 2 つを混ぜたまま議論すると、チャネル設計の良し悪しを判定できない。
    ここでは LLM を一切呼ばずに検索側だけを切り出して測る。**課金ゼロ・完全に
    決定的**なので、CI でも回せるしチャネル設計の反復にも使える。

測る指標:
    file_recall@k
        上位 k 件の中に、答えが実在するファイル由来のチャンクが 1 件以上あるか。
        「探し当てられたか」。
    answer_literal@k
        上位 k 件の本文に、**正解文字列がそのまま現れるか**。
    answer_literal_corpus
        k に関係なく、コーパス全体の抽出テキストのどこかに正解文字列が現れるか。
        Arm A が「読むだけで」答えられる上限。ここが 0 なら、そのチャネルは
        検索をいくら強くしても抽出テキストからは答えが取り出せない。

★ **解釈の注意（ここを曖昧にすると主張が過大になる）**:
    ``answer_literal`` が 0 でも、モデルが**計算や推論で導ける**可能性は残る。
    たとえば `formula` は合計値がどこにも書かれていないが、数量と単価が
    読めるならモデルは掛けて足せる。したがってこの指標は
    「古典的RAGが答えられない証明」ではなく、
    「答えが**そのままの形では存在しない**ことの証明」である。
    実際に答えられるかは Arm A を走らせて測ること。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from arms.classical.chunk import DEFAULT_CHUNK_CHARS, DEFAULT_OVERLAP_CHARS, chunk_blocks
from arms.classical.extract import extract_corpus
from arms.classical.retrieve import HybridIndex, embedding_model_name
from arms.llm import bootstrap
from gen.common import Item, normalize_text, read_questions_jsonl


def _contains_answer(item: Item, text: str) -> bool:
    """正規化したうえで、正解またはその許容表記が文中に現れるか。"""
    haystack = normalize_text(text)
    return any(normalize_text(a) in haystack for a in item.accepted if a.strip())


def probe(
    corpus: Path,
    ks: list[int],
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> tuple[pd.DataFrame, dict]:
    meta = json.loads((corpus / "meta.json").read_text(encoding="utf-8"))
    items = read_questions_jsonl(corpus / "questions.jsonl")

    blocks = extract_corpus(corpus / "files")
    chunks = chunk_blocks(blocks, chunk_chars, overlap_chars)
    index = HybridIndex(chunks, meta["locale"])

    corpus_text = "\n".join(c.text for c in chunks)

    rows: list[dict] = []
    for item in items:
        in_corpus = _contains_answer(item, corpus_text)
        sources = set(item.source_files)
        for k in ks:
            hits = index.search(item.question, k)
            retrieved_text = "\n".join(h.chunk.text for h in hits)
            hit_paths = {h.chunk.path for h in hits}
            rows.append(
                {
                    "qid": item.qid,
                    "channel": item.channel,
                    "difficulty": item.difficulty,
                    "k": k,
                    "file_recall": bool(sources & hit_paths),
                    "answer_literal": _contains_answer(item, retrieved_text),
                    "answer_literal_corpus": in_corpus,
                    "top1_path": hits[0].chunk.path if hits else "",
                }
            )

    info = {
        "corpus": meta,
        "n_blocks": len(blocks),
        "n_chunks": len(chunks),
        "chunk_chars": chunk_chars,
        "overlap_chars": overlap_chars,
        "embedding_model": embedding_model_name(),
        "retrieval": "bm25 + dense (RRF)",
        "k_values": ks,
    }
    return pd.DataFrame(rows), info


def summarise(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["channel", "k"], dropna=False)
        .agg(
            n=("qid", "count"),
            file_recall=("file_recall", "mean"),
            answer_literal=("answer_literal", "mean"),
            answer_literal_corpus=("answer_literal_corpus", "mean"),
        )
        .reset_index()
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    bootstrap()

    p = argparse.ArgumentParser(
        prog="python -m eval.retrieval_probe",
        description="LLM を呼ばずに検索側だけを測る（課金ゼロ・決定的）。",
    )
    p.add_argument("--corpus", type=Path, default=Path("corpus"))
    p.add_argument("--k", default="4,8,16,32", help="スイープする k（カンマ区切り）")
    p.add_argument("--out", type=Path, default=None, help="結果の保存先ディレクトリ")
    args = p.parse_args(argv)

    ks = [int(k) for k in args.k.split(",") if k.strip()]
    frame, info = probe(args.corpus, ks)
    summary = summarise(frame)

    pd.set_option("display.width", 160)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print(f"チャンク数: {info['n_chunks']}  埋め込み: {info['embedding_model']}")
    print()
    print("── 検索プローブ（LLM 未使用）────────────────────────────")
    print(summary.to_string(index=False))
    print()
    print("file_recall            … 上位 k に答えのあるファイルが入った割合")
    print("answer_literal         … 上位 k の本文に正解文字列がそのまま現れた割合")
    print("answer_literal_corpus  … コーパス全体の抽出テキストに現れる割合（k 非依存）")
    print()
    print("※ answer_literal が 0 でも、モデルが計算で導ける可能性は残る。")
    print("   これは『答えがそのままの形では存在しない』ことの証拠であり、")
    print("   『答えられない』ことの証明ではない。")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out / "probe_raw.csv", index=False, encoding="utf-8-sig")
        summary.to_csv(args.out / "probe_summary.csv", index=False, encoding="utf-8-sig")
        (args.out / "probe_meta.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\n出力: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
