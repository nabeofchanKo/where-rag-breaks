"""道具を使うアームのセッション記録を監査する（LLM 不要）。

    uv run python -m eval.hermetic_audit --corpus corpus-1000/ --since 2026-09-30T00:00:00Z

Claude CLI はセッションごとの記録を ``~/.claude/projects/<作業ディレクトリ名>/`` に
残す。Arm B / C の作業ディレクトリはコーパス直下なので、コーパスごとに記録が
まとまっている。ここから次の 3 点を数える。

    answer_files    正解の入ったファイル（questions.jsonl / meta.json / results/）や
                    リポジトリ外への言及。1 件でもあれば、その run は結論に使えない
    outside_paths   コーパスの外を指すパス（絶対パス・``..``・``/tmp``）を使った呼出。
                    ``read_file`` はガードで弾かれるが、``run_python`` は任意のコード
                    なので弾けない。件数と中身を目で確かめる
    foreign_codes   ``files/`` と ``_index/`` 以外から読んだ結果に、**別の設問の文書
                    コード**が出てきた呼出。前の設問の一時ファイルを読んだ疑い

★ P2/P3 では一時ファイルがコーパス直下に残っていた（SPEC §14-9）。858 セッションを
  これと同じ方法で全数検査し、前の設問の一時ファイルを読んだ形跡は無かった。
  P4 からは設問ごとに一時ファイルを消している（``arms.agentic.arm.restore``）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CODE = re.compile(r"\b([A-Z]{2,3}-\d{4})")
ANSWER_FILES = re.compile(r"questions\.jsonl|meta\.json|results[/\\]|\.claude[/\\]")
OUTSIDE = re.compile(r"""(?:['"\s(]|^)(?:[A-Za-z]:[/\\]|/tmp/|\.\./|\.\.\\)""")


def transcript_dir(corpus: Path) -> Path:
    """CLI が作業ディレクトリ名から作るフォルダ名（英数字以外を ``-`` に置換）。"""
    name = re.sub(r"[^A-Za-z0-9]", "-", str(corpus.resolve()))
    return Path.home() / ".claude" / "projects" / name


def _messages(session: Path):
    for line in session.read_text(encoding="utf-8").splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def audit(corpus: Path, since: str = "") -> dict:
    root = transcript_dir(corpus)
    sessions = sorted(root.glob("*.jsonl")) if root.is_dir() else []

    counted = 0
    answer_files: list[tuple[str, str]] = []
    outside: list[tuple[str, str, str]] = []
    foreign: list[tuple[str, str, list[str], list[str]]] = []

    for session in sessions:
        records = list(_messages(session))
        stamps = [r.get("timestamp", "") for r in records if r.get("timestamp")]
        if since and (not stamps or min(stamps) < since):
            continue
        counted += 1

        question: set[str] = set()
        uses: dict[str, tuple[str, dict]] = {}
        for record in records:
            message = record.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if record.get("type") == "user" and not question:
                text = (
                    content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                )
                if "質問" in text or "Question" in text:
                    tail = re.split(r"質問|Question", text, maxsplit=1)[1][:300]
                    question = set(CODE.findall(tail))
            if not isinstance(content, list):
                continue
            for item in content:
                if item.get("type") == "tool_use":
                    tool = item["name"].split("__")[-1]
                    blob = json.dumps(item["input"], ensure_ascii=False)
                    uses[item["id"]] = (tool, item["input"])
                    if ANSWER_FILES.search(blob):
                        answer_files.append((session.name, blob[:200]))
                    if OUTSIDE.search(blob):
                        outside.append((session.name, tool, blob[:200]))
                elif item.get("type") == "tool_result" and item.get("tool_use_id") in uses:
                    tool, args = uses[item["tool_use_id"]]
                    path = str(args.get("path", ""))
                    if tool not in ("read_file", "view_image") or not path:
                        continue
                    if path.lstrip("/\\").startswith(("files/", "_index/")):
                        continue
                    body = json.dumps(item.get("content"), ensure_ascii=False)
                    codes = set(CODE.findall(body)) - question
                    if codes:
                        foreign.append((session.name, path, sorted(question), sorted(codes)[:5]))

    return {
        "transcripts": str(root),
        "sessions": counted,
        "answer_files": answer_files,
        "outside_paths": outside,
        "foreign_codes": foreign,
    }


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(
        prog="python -m eval.hermetic_audit", description=__doc__.split("\n")[0]
    )
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument(
        "--since", default="", help="この時刻（ISO 8601, UTC）以降に始まったセッションだけ"
    )
    p.add_argument("--out", type=Path, default=None, help="結果を JSON で保存する場所")
    args = p.parse_args(argv)

    result = audit(args.corpus, args.since)
    print(f"記録: {result['transcripts']}")
    print(f"セッション数         : {result['sessions']}")
    print(f"正解ファイルへの言及 : {len(result['answer_files'])}")
    print(f"コーパス外のパス     : {len(result['outside_paths'])}")
    print(f"別設問のコード       : {len(result['foreign_codes'])}")
    for key in ("answer_files", "outside_paths", "foreign_codes"):
        for row in result[key][:10]:
            print(f"  [{key}]", *row)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 1 if result["answer_files"] or result["foreign_codes"] else 0


if __name__ == "__main__":
    sys.exit(main())
