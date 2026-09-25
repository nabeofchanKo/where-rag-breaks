"""画像系チャネル（`chart_only` / `layout` / `scanned`）の罠を固定するテスト。

★ このグループでは「正解文字列が抽出テキストに出るか」だけでは罠を判定できない。

    `layout` 難易度3 は、五十音順の在席者一覧を本文に置くので**全員の氏名が
    抽出テキストに現れる**。それでも「誰が隣か」は画像の座標にしかないので
    罠は成立している。`format` も同じ構造（管理番号は表にあるが、どの行が
    塗られているかは分からない）。

    したがってここでは、**答えを特定できる手がかりが抽出テキストにあるか**を
    チャネルごとの形で検査する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arms.classical.extract import extract_corpus, extract_file
from gen.__main__ import generate_corpus
from gen.common import Item, normalize_text, read_questions_jsonl

CHANNELS = ["chart_only", "layout", "scanned"]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("p1b")
    generate_corpus(seed=11, files=30, questions=3, locale_code="ja", channels=CHANNELS, out=out)
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


# ── chart_only ──────────────────────────────────────────────────────
def test_chart_only_value_is_in_the_image_only(corpus: Path, extracted: dict[str, str]) -> None:
    items = _items(corpus, "chart_only")
    assert normalize_text(items[1].answer) in normalize_text(_text(items[1], extracted)), (
        "難易度1 は表からも読めるべき（コントロール）"
    )
    for tier in (2, 3):
        assert normalize_text(items[tier].answer) not in normalize_text(
            _text(items[tier], extracted)
        ), f"難易度{tier} の値が抽出テキストに漏れている"
    assert normalize_text(items[3].decoys[0]) in normalize_text(_text(items[3], extracted)), (
        "難易度3 の囮（全社合計）が本文に無い"
    )


def test_png_is_never_extracted(corpus: Path) -> None:
    """画像は抽出対象にしない（OCR を掛けない＝実務の既定の挙動）。"""
    for png in (corpus / "files").rglob("*.png"):
        assert extract_file(png, png.name) == []


# ── layout ──────────────────────────────────────────────────────────
def test_layout_control_tier_states_the_seating_rule(
    corpus: Path, extracted: dict[str, str]
) -> None:
    items = _items(corpus, "layout")
    control = _text(items[1], extracted)
    assert "A列は左から" in control, "難易度1 は並び順の規則が本文にあるべき"
    assert f"{items[1].answer}" in control

    for tier in (2, 3):
        assert "A列は左から" not in _text(items[tier], extracted), (
            f"難易度{tier} に並び順の規則が漏れている"
        )


def test_layout_trap_tier_hides_the_adjacency_not_the_name(
    corpus: Path, extracted: dict[str, str]
) -> None:
    """難易度3 は氏名一覧があるので名前自体は出るが、隣接関係は出ない。

    「正解文字列が抽出テキストに出る＝罠が壊れている」ではないことを、
    テストの形で明示しておく。
    """
    item = _items(corpus, "layout")[3]
    text = _text(item, extracted)
    assert item.answer in text, "五十音順一覧があるので氏名自体は現れる"
    assert "座席割当" not in text, "座席割当が漏れている（隣接関係が読めてしまう）"
    assert item.decoys and item.decoys[0] in text


def test_layout_tier_two_hides_the_name_entirely(corpus: Path, extracted: dict[str, str]) -> None:
    item = _items(corpus, "layout")[2]
    assert item.answer not in _text(item, extracted)


# ── scanned ─────────────────────────────────────────────────────────
def test_scanned_pdf_has_no_text_layer(corpus: Path, extracted: dict[str, str]) -> None:
    """難易度2・3 の PDF からはテキストが 1 文字も取れない。

    難易度1（コントロール）は通常のテキストPDFなので取れる。
    両方確認することで「PDF 抽出そのものが壊れている」のではないと言える。
    """
    items = _items(corpus, "scanned")

    control_pdf = next(p for p in items[1].source_files if p.endswith(".pdf"))
    assert extracted.get(control_pdf, "").strip(), "難易度1 のテキストPDFが読めていない"
    assert items[1].answer in extracted[control_pdf]

    for tier in (2, 3):
        pdf = next(p for p in items[tier].source_files if p.endswith(".pdf"))
        assert not extracted.get(pdf, "").strip(), f"難易度{tier} の PDF にテキスト層が残っている"


def test_scanned_decoy_is_in_the_readable_cover(corpus: Path, extracted: dict[str, str]) -> None:
    item = _items(corpus, "scanned")[3]
    cover = next(p for p in item.source_files if p.endswith(".docx"))
    text = extracted[cover]
    assert item.decoys and item.decoys[0] in text, "囮が送付状に無い"
    assert item.answer not in text, "正解が送付状に漏れている"
