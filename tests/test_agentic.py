"""Arm B の索引と道具のテスト（LLM は呼ばない）。

見るのは 2 点。

    1. **索引が Arm A を優遇していないこと**
       ミラーは Arm A と同じ抽出器で作る。ここが崩れると、Arm B の優位が
       「エージェントが自力で見つけた」からなのか「前処理が良かった」からなのか
       区別できなくなる。

    2. **道具がコーパスの外に出られないこと**
       外のファイルを読めてしまうと、答えを別経路から拾える可能性が残り、
       測定として成立しない。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from arms.agentic.tools import ToolContext, build_server
from arms.classical.extract import extract_corpus
from gen.__main__ import generate_corpus
from ingest.build import build

CHANNELS = ["format", "text"]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("agentic")
    generate_corpus(seed=13, files=20, questions=2, locale_code="ja", channels=CHANNELS, out=out)
    build(out, out / "_index")
    return out


# ── 索引 ────────────────────────────────────────────────────────────
def test_catalog_lists_every_file_with_only_a_headline(corpus: Path) -> None:
    catalog = (corpus / "_index" / "catalog.md").read_text(encoding="utf-8")
    files = [p for p in (corpus / "files").rglob("*") if p.is_file()]
    for path in files:
        assert path.relative_to(corpus / "files").as_posix() in catalog

    # 本文が丸ごと載っていないこと（載るとカタログを読むだけで答えが出る）
    body_lines = [line for line in catalog.split("\n") if line.startswith("|")]
    assert all(len(line) < 400 for line in body_lines), "カタログの行が長すぎる（本文が混ざった）"


def test_mirror_uses_exactly_the_classical_extractor(corpus: Path) -> None:
    """★ ミラーの中身が Arm A の抽出結果と一致すること。

    ここが緩むと Arm B が前処理で下駄を履く。比較の前提が壊れる。
    """
    mirror = corpus / "_index" / "mirror"
    by_path: dict[str, list] = {}
    for block in extract_corpus(corpus / "files"):
        by_path.setdefault(block.path, []).append(block)

    for rel, blocks in by_path.items():
        md = (mirror / (rel + ".md")).read_text(encoding="utf-8")
        for block in blocks:
            assert block.locator in md
            assert block.text in md


def test_files_without_extractable_text_have_no_mirror(corpus: Path) -> None:
    mirror = corpus / "_index" / "mirror"
    extracted = {b.path for b in extract_corpus(corpus / "files")}
    for path in (corpus / "files").rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(corpus / "files").as_posix()
        if rel not in extracted:
            assert not (mirror / (rel + ".md")).exists()


# ── 道具 ────────────────────────────────────────────────────────────
def _call(server_tool, args: dict) -> str:
    """SDK のツールを直接叩いて、返ってきたテキストを取り出す。"""
    result = asyncio.run(server_tool.handler(args))
    return "".join(c.get("text", "") for c in result["content"])


def _tools(ctx: ToolContext) -> dict:
    server = build_server(ctx)
    instance = server["instance"] if isinstance(server, dict) else server
    return {t.name: t for t in instance.tools} if hasattr(instance, "tools") else {}


@pytest.mark.parametrize(
    "escape",
    [
        "../../../etc/passwd",
        "..\\..\\secret.txt",
        "files/../../outside.txt",
        "C:/Windows/System32/drivers/etc/hosts",
    ],
)
def test_resolve_refuses_paths_that_leave_the_corpus(corpus: Path, escape: str) -> None:
    ctx = ToolContext(corpus)
    with pytest.raises(PermissionError):
        ctx.resolve(escape)


@pytest.mark.parametrize("rooted", ["/files", "/_index/catalog.md", "\\_index/catalog.md"])
def test_rooted_paths_are_read_as_corpus_relative(corpus: Path, rooted: str) -> None:
    """先頭の ``/`` は**コーパス相対**として読む（外には出ない）。

    ``/etc/passwd`` は ``<corpus>/etc/passwd`` に、UNC の ``//server/share/x`` は
    ``<corpus>/server/share/x`` になる。いずれも実在せず害も無い。
    例外にしないのは、モデルがルート付きで書いてきたときに素直に解釈した
    ほうが挙動が読みやすいため。外に出る経路は上のテストで塞いである。
    """
    resolved = ctx_resolve(corpus, rooted)
    assert resolved.is_relative_to(corpus.resolve())


def ctx_resolve(corpus: Path, raw: str) -> Path:
    return ToolContext(corpus).resolve(raw)


def test_resolve_accepts_paths_inside_the_corpus(corpus: Path) -> None:
    ctx = ToolContext(corpus)
    assert ctx.resolve("_index/catalog.md").is_file()
    assert ctx.resolve("files").is_dir()


def test_allowed_set_restricts_visible_files(corpus: Path) -> None:
    """Arm C が候補を絞るためのフックが効くこと。"""
    every = [
        p.relative_to(corpus / "files").as_posix()
        for p in (corpus / "files").rglob("*")
        if p.is_file()
    ]
    keep = {every[0]}
    ctx = ToolContext(corpus, allowed=keep)

    visible = [p.relative_to(corpus / "files").as_posix() for p in ctx.visible_files()]
    assert visible == sorted(keep)

    with pytest.raises(PermissionError):
        ctx.resolve(f"files/{every[1]}")
    assert ctx.resolve(f"files/{every[0]}").is_file()


def test_note_open_records_both_originals_and_mirror(corpus: Path) -> None:
    ctx = ToolContext(corpus)
    ctx.note_open(ctx.resolve("_index/catalog.md"))
    first = next(p for p in (corpus / "files").rglob("*") if p.is_file())
    ctx.note_open(first)
    assert "_index/catalog.md" in ctx.files_opened
    assert any(p.startswith("files/") for p in ctx.files_opened)
