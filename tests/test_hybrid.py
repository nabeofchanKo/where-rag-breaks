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


def test_companion_cap_keeps_the_matching_file(corpus: Path) -> None:
    """★ 付随ファイルが上限を超えても、本体と同じ名前の図版は切り落とされないこと。

    名前順で切ると、規模が大きくなって同じディレクトリに埋め草の図版が
    並んだとき本命が落ちる（1,524 ファイルで locked の全問が詰んだ。SPEC §14-9）。
    ここでは本命の図版が**名前順で最後**になる資料を選び、上限を 2 件に絞る。
    """
    from arms.classical.extract import extract_corpus
    from arms.hybrid.arm import HybridArm

    indexable = {b.path for b in extract_corpus(corpus / "files")}
    images = sorted(p for p in _all_files(corpus) if p.endswith(".png") and p not in indexable)
    assert len(images) > 2, "図版が上限以下しか無い（このテストの前提が崩れている）"

    last = images[-1]
    code = last.rsplit("/", 1)[-1].split("_")[0]
    deck = next(p for p in _all_files(corpus) if p.endswith(".pptx") and f"/{code}_" in p)

    arm = HybridArm(k=1)  # 上限は 2k = 2 件
    arm.classical._index = _FakeIndex(indexable)  # noqa: SLF001
    arm.agentic.corpus = corpus.resolve()

    companions = arm._companions([deck])  # noqa: SLF001
    assert len(companions) == 2
    assert last in companions, "名前順で最後の本命の図版が上限で切り落とされた"


class _FakeIndex:
    """``_companions`` が見るのは ``chunks`` の path だけ。"""

    def __init__(self, paths: set[str]) -> None:
        self.chunks = [type("C", (), {"path": p})() for p in sorted(paths)]


# ── 物理的な絞り込み（SPEC §14-9）────────────────────────────────────
def test_workspace_holds_only_the_candidates(corpus: Path) -> None:
    """★ 候補外のファイルは作業ディレクトリに**存在しない**こと。

    P3 では道具ごとの検査で絞っていたが、read_file はミラーを素通しし、
    run_python は原本をどれでも開けた。物理的に置かなければ、どの道具でも届かない。
    """
    from arms.hybrid.arm import HybridArm

    everything = _all_files(corpus)
    candidates = [p for p in everything if p.endswith(".pptx")][:1]
    outside = [p for p in everything if p not in candidates]
    assert outside, "候補外のファイルが無い（このテストの前提が崩れている）"

    arm = HybridArm(k=5)
    arm.agentic.corpus = corpus.resolve()
    workspace = arm.build_workspace(candidates)

    present = sorted(
        p.relative_to(workspace / "files").as_posix()
        for p in (workspace / "files").rglob("*")
        if p.is_file()
    )
    assert present == candidates
    mirrors = [p.name for p in (workspace / "_index" / "mirror").rglob("*.md")]
    assert mirrors == [f"{Path(candidates[0]).name}.md"]

    catalog = (workspace / "_index" / "catalog.md").read_text(encoding="utf-8")
    assert candidates[0] in catalog
    assert not any(f"`{p}`" in catalog for p in outside), "カタログに候補外の行が残っている"
    assert workspace.parent == corpus.resolve().parent, "作業ディレクトリはコーパスの外に置く"
