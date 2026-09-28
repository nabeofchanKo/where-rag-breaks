"""Arm C の絞り込みのテスト（LLM は呼ばない）。

検査するのは 2 点。

    1. **絞ったらカタログとミラーも連動して絞られること**
       候補を N 件にしてもカタログに全ファイルが並んでいたら、
       エージェントはそこから好きなものを選べてしまい、
       「絞ってから渡す」という設計が成立しない。

    2. **索引不能なファイルが候補に入りうること**
       PNG や暗号化 zip はチャンクを 1 つも生まないので、素朴な
       チャンク検索では永久に候補に入らない。それでは Arm C が
       グラフ画像にも暗号化ファイルにも触れられず、hybrid という方式の
       性質ではなく絞り込みの手抜きで負けることになる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arms.agentic.tools import ToolContext
from gen.__main__ import generate_corpus
from ingest.build import build

CHANNELS = ["chart_only", "text"]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("hybrid")
    generate_corpus(seed=21, files=24, questions=2, locale_code="ja", channels=CHANNELS, out=out)
    build(out, out / "_index")
    return out


def _all_files(corpus: Path) -> list[str]:
    return sorted(
        p.relative_to(corpus / "files").as_posix()
        for p in (corpus / "files").rglob("*")
        if p.is_file()
    )


# ── カタログの連動 ──────────────────────────────────────────────────
def test_catalog_is_filtered_to_the_allowed_files(corpus: Path) -> None:
    every = _all_files(corpus)
    keep = set(every[:3])
    raw = (corpus / "_index" / "catalog.md").read_text(encoding="utf-8")

    filtered = ToolContext(corpus, allowed=keep).filter_catalog(raw)

    for path in keep:
        assert f"`{path}`" in filtered
    for path in set(every) - keep:
        assert f"`{path}`" not in filtered, f"{path} がカタログに残っている"
    assert "伏せてある" in filtered, "伏せた件数が示されていない"


def test_catalog_is_untouched_without_narrowing(corpus: Path) -> None:
    raw = (corpus / "_index" / "catalog.md").read_text(encoding="utf-8")
    assert ToolContext(corpus, allowed=None).filter_catalog(raw) == raw


# ── ミラーの連動 ────────────────────────────────────────────────────
def test_mirror_visibility_follows_the_allowed_set(corpus: Path) -> None:
    every = _all_files(corpus)
    docx = [p for p in every if p.endswith(".docx")]
    keep, drop = {docx[0]}, docx[1]

    ctx = ToolContext(corpus, allowed=keep)
    mirror = corpus / "_index" / "mirror"
    assert ctx.mirror_is_visible(mirror / (docx[0] + ".md"))
    assert not ctx.mirror_is_visible(mirror / (drop + ".md"))
    # カタログ自体はミラーではないので常に見える（中身は filter_catalog が絞る）
    assert ctx.mirror_is_visible(corpus / "_index" / "catalog.md")


# ── 索引不能ファイルの到達性 ────────────────────────────────────────
def test_unindexable_files_exist_in_this_corpus(corpus: Path) -> None:
    """前提の確認: チャンクを生まないファイルが実際にあること。"""
    from arms.classical.extract import extract_corpus

    indexable = {b.path for b in extract_corpus(corpus / "files")}
    unindexable = set(_all_files(corpus)) - indexable
    assert unindexable, "索引不能ファイルが無い（このテストの前提が崩れている）"
    assert any(p.endswith(".png") for p in unindexable)


def test_companions_bring_in_unindexable_neighbours(corpus: Path) -> None:
    """★ 選ばれたファイルの近くにある索引不能ファイルが候補に入ること。

    ここが無いと Arm C はグラフ画像に触れられず、hybrid の性質ではなく
    絞り込みの手抜きで負ける（SPEC §4-1 の steel-man 原則は Arm C にも及ぶ）。
    """
    from arms.classical.extract import extract_corpus
    from arms.hybrid.arm import HybridArm

    indexable = {b.path for b in extract_corpus(corpus / "files")}
    deck = next(p for p in _all_files(corpus) if p.endswith(".pptx"))
    image = next(
        p for p in _all_files(corpus) if p.endswith(".png") and p not in indexable
    )

    arm = HybridArm(k=5)
    # 索引は使わずに、付随ファイル探索だけを直接検査する
    arm.classical._index = _FakeIndex(indexable)  # noqa: SLF001
    arm.agentic.corpus = corpus.resolve()

    companions = arm._companions([deck])  # noqa: SLF001
    assert image in companions, "同じ資料の図版が候補に入っていない"
    assert all(c not in indexable for c in companions), "索引可能なファイルが混ざっている"


class _FakeIndex:
    """``_companions`` が見るのは ``chunks`` の path だけ。"""

    def __init__(self, paths: set[str]) -> None:
        self.chunks = [type("C", (), {"path": p})() for p in sorted(paths)]
