"""`chart_native` / `version` / `locked` の罠を固定するテスト。"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from arms.classical.extract import extract_corpus, extract_file
from gen.__main__ import generate_corpus
from gen.common import Item, normalize_text, read_questions_jsonl

CHANNELS = ["chart_native", "locked", "version"]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("p1c")
    generate_corpus(seed=3, files=40, questions=3, locale_code="ja", channels=CHANNELS, out=out)
    return out


@pytest.fixture(scope="module")
def extracted(corpus: Path) -> dict[str, str]:
    out: dict[str, list[str]] = {}
    for block in extract_corpus(corpus / "files"):
        out.setdefault(block.path, []).append(block.text)
    return {path: "\n".join(parts) for path, parts in out.items()}


def _items(corpus: Path, channel: str) -> dict[int, Item]:
    return {
        it.difficulty: it
        for it in read_questions_jsonl(corpus / "questions.jsonl")
        if it.channel == channel
    }


def _text(item: Item, extracted: dict[str, str]) -> str:
    return "\n".join(extracted.get(path, "") for path in item.source_files)


@pytest.mark.parametrize("channel", CHANNELS)
def test_all_three_tiers_exist(corpus: Path, channel: str) -> None:
    assert set(_items(corpus, channel)) == {1, 2, 3}


# ── chart_native ────────────────────────────────────────────────────
def test_chart_native_hides_the_mapping_not_the_numbers(
    corpus: Path, extracted: dict[str, str]
) -> None:
    """隠れているのは数値ではなく「どの列がどの拠点か」。

    openpyxl は非表示シートも読むので数値は抽出テキストに出る。それでも
    系列名（拠点名）はチャート定義の中にしかないので、対応づけができない。
    """
    items = _items(corpus, "chart_native")

    control = _text(items[1], extracted)
    assert items[1].answer in control, "難易度1 は参考表から解けるべき（コントロール）"
    assert "参考表" in control, "難易度1 は拠点名つきの表があるべき"

    for tier in (2, 3):
        text = _text(items[tier], extracted)
        # 数値自体は出ていてよい（隠しているのは対応づけ）
        assert any(ch.isdigit() for ch in text), "非表示シートの数値すら出ていないのは想定外"
        assert "参考表" not in text, f"難易度{tier} に拠点名つきの表が残っている"

    # 難易度2 は拠点名がどこにも出ない
    assert items[2].answer not in _text(items[2], extracted)

    # 難易度3 は「掲載順」注記があるので拠点名自体は出る。ただし順序は
    # グラフの系列順と違うので、どれが最大かは分からない（layout と同じ構造）。
    tier3 = _text(items[3], extracted)
    assert "掲載順" in tier3, "難易度3 の囮となる順序注記が無い"
    assert items[3].decoys and items[3].decoys[0] in tier3


def test_chart_native_series_names_live_in_the_chart_xml(corpus: Path) -> None:
    """拠点名が chart XML の中にあることを直接確認する。"""
    item = _items(corpus, "chart_native")[2]
    path = corpus / "files" / item.source_files[0]
    with zipfile.ZipFile(path) as zf:
        charts = [n for n in zf.namelist() if n.startswith("xl/charts/")]
        assert charts, "chart が埋め込まれていない"
        blob = b"".join(zf.read(n) for n in charts).decode("utf-8", "ignore")
    assert item.answer in blob, "系列名がチャート定義に入っていない"


def test_chart_native_hidden_sheet_is_hidden(corpus: Path) -> None:
    from openpyxl import load_workbook

    item = _items(corpus, "chart_native")[2]
    wb = load_workbook(corpus / "files" / item.source_files[0])
    assert wb["_src"].sheet_state == "hidden"


# ── version ─────────────────────────────────────────────────────────
def _editions(item: Item, extracted: dict[str, str]) -> tuple[str, str]:
    """(現行版の本文, 旧版の本文)。どちらが現行かは**改訂日**で決まる。"""
    policies = [p for p in item.source_files if p.endswith(".docx") and "_index" not in p]
    assert len(policies) == 2
    dated = sorted(
        policies,
        key=lambda p: extracted[p].split("最終改訂日:")[1].strip().split()[0],
    )
    return extracted[dated[1]], extracted[dated[0]]


def test_version_old_edition_is_the_decoy(corpus: Path, extracted: dict[str, str]) -> None:
    """旧版の値が囮になっている。

    このチャネルだけは難易度2 にも囮がある。囮を仕込んでいるのではなく、
    **旧版が存在すること自体が囮**だから。
    """
    items = _items(corpus, "version")
    for tier in (1, 2, 3):
        item = items[tier]
        assert item.decoys, f"難易度{tier} に旧版の値が登録されていない"
        current, old = _editions(item, extracted)
        assert item.answer in current, "現行版に正解が入っていない"
        assert item.decoys[0] in old, "旧版に囮の値が入っていない"


def test_version_control_tier_reveals_the_edition_through_the_path(corpus: Path) -> None:
    """★ 難易度1 だけはパスで新旧が分かる（コントロール段）。

    初版はこの構成しか無く、Arm A に 6/6 で解かれた。出所ヘッダに
    ``policies/current/`` と出るため、中身を比べずに現行版が分かってしまう。
    その経緯を段として保存してある。
    """
    paths = _items(corpus, "version")[1].source_files
    assert any("/current/" in p for p in paths) and any("/old/" in p for p in paths)


def test_version_trap_tiers_hide_the_edition_from_the_path(corpus: Path) -> None:
    """難易度2 以降はパスから新旧が読めない。

    連番（``_ed1`` / ``_ed2``）も使わない。番号の大小そのものがヒントになり、
    改訂日を読まずに当てられてしまうため。
    """
    import re

    for tier in (2, 3):
        for path in _items(corpus, "version")[tier].source_files:
            assert "/current/" not in path and "/old/" not in path
            assert not re.search(r"_ed\d", path), "連番が新旧のヒントになっている"


def test_version_revision_date_is_in_a_different_chunk(
    corpus: Path, extracted: dict[str, str]
) -> None:
    """改訂日と保証期間が別の見出しブロックにある。

    構造を見たチャンク分割では別チャンクに落ちるので、
    「値を読むチャンク」と「どちらが現行かを決めるチャンク」を
    突き合わせる必要が出る。これが難易度2 以降の肝。
    """
    from arms.classical.chunk import chunk_blocks
    from arms.classical.extract import extract_corpus as _extract

    chunks = chunk_blocks(_extract(corpus / "files"))
    item = _items(corpus, "version")[2]
    for path in item.source_files:
        own = [c for c in chunks if c.path == path]
        with_value = {c.locator for c in own if "保証期間は" in c.text}
        with_date = {c.locator for c in own if "最終改訂日" in c.text}
        assert with_value and with_date
        assert not (with_value & with_date), "改訂日と保証期間が同じチャンクに入っている"


def test_version_editions_differ_only_in_the_substantive_value(
    corpus: Path, extracted: dict[str, str]
) -> None:
    """新旧は保証期間の数値だけが実質的に違う（ほかは体裁差）。"""
    item = _items(corpus, "version")[2]
    current, old = _editions(item, extracted)
    assert old != current
    assert item.answer in current and item.answer not in old
    assert item.decoys[0] in old and item.decoys[0] not in current


# ── locked ──────────────────────────────────────────────────────────
def test_locked_archive_is_not_extractable(corpus: Path, extracted: dict[str, str]) -> None:
    for item in _items(corpus, "locked").values():
        archive = next(p for p in item.source_files if p.endswith(".zip"))
        assert extract_file(corpus / "files" / archive, archive) == []
        assert archive not in extracted


def test_locked_password_rule_is_split_across_documents(
    corpus: Path, extracted: dict[str, str]
) -> None:
    """パスワードそのものはどこにも書かれておらず、規則と材料が別文書にある。"""
    item = _items(corpus, "locked")[2]
    rule = extracted[next(p for p in item.source_files if p.endswith("_handling.docx"))]
    master = extracted[next(p for p in item.source_files if p.endswith("_master.docx"))]

    assert "パスワード" in rule and "拠点コード" in rule
    assert "拠点コード:" in master and "確定日:" in master
    # 規則の文書に材料は無く、材料の文書に規則は無い
    assert "拠点コード:" not in rule
    assert "パスワード" not in master


def test_locked_archive_needs_the_password(corpus: Path) -> None:
    """暗号化されていること（パスワード無しでは読めない）を実際に確かめる。"""
    import pyzipper

    item = _items(corpus, "locked")[2]
    archive = corpus / "files" / next(p for p in item.source_files if p.endswith(".zip"))
    with pyzipper.AESZipFile(archive) as zf:
        name = zf.namelist()[0]
        with pytest.raises(RuntimeError):
            zf.read(name)


def test_locked_control_tier_is_solvable_but_traps_are_not(
    corpus: Path, extracted: dict[str, str]
) -> None:
    items = _items(corpus, "locked")
    haystack = normalize_text(_text(items[1], extracted))
    assert normalize_text(items[1].answer) in haystack, (
        "難易度1 は送付状から解けるべき（コントロール）"
    )
    for tier in (2, 3):
        assert normalize_text(items[tier].answer) not in normalize_text(
            _text(items[tier], extracted)
        ), f"難易度{tier} の金額が平文に漏れている"
    assert normalize_text(items[3].decoys[0]) in normalize_text(_text(items[3], extracted))
