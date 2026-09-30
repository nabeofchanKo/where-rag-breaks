"""``eval.run`` の入口の検査（LLM は呼ばない）。

P4 では規模違いのコーパスが並ぶ。qid は規模をまたいで同じなので、
``--corpus`` を取り違えて既存の run を「再開」すると、記録済みの行が
黙ってスキップされ、別規模の結果が 1 つの run に混ざる。それを入口で止める。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.run import main
from gen.__main__ import generate_corpus

CHANNELS = ["text"]


@pytest.fixture(scope="module")
def corpora(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    small = tmp_path_factory.mktemp("small")
    large = tmp_path_factory.mktemp("large")
    generate_corpus(seed=42, files=6, questions=2, locale_code="ja", channels=CHANNELS, out=small)
    generate_corpus(seed=42, files=12, questions=2, locale_code="ja", channels=CHANNELS, out=large)
    return small, large


def test_same_questions_across_sizes(corpora: tuple[Path, Path]) -> None:
    """規模を変えても設問は同一（P4 の前提）。"""
    small, large = corpora
    assert (small / "questions.jsonl").read_bytes() == (large / "questions.jsonl").read_bytes()


def test_resuming_on_another_corpus_is_refused(
    corpora: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    small, large = corpora
    run_dir = tmp_path / "p4-test"
    run_dir.mkdir()
    corpus_meta = json.loads((small / "meta.json").read_text(encoding="utf-8"))
    (run_dir / "meta.json").write_text(json.dumps({"corpus": corpus_meta}), encoding="utf-8")

    code = main(["--corpus", str(large), "--run-id", "p4-test", "--results", str(tmp_path)])

    assert code == 2
    assert "別のコーパス" in capsys.readouterr().err


def test_unknown_qid_is_refused(corpora: tuple[Path, Path], tmp_path: Path) -> None:
    small, _ = corpora
    code = main(["--corpus", str(small), "--qids", "text-99", "--results", str(tmp_path)])
    assert code == 2
