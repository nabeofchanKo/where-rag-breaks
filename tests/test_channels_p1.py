"""P1 で追加したチャネルの罠が成立していることを固定するテスト。

各チャネルについて確かめるのは 2 つだけ。

    1. **コントロール段（難易度1）は抽出テキストから解ける**
       ここが解けないなら、罠ではなく抽出器か検索の問題である。
       SPEC §4-1「抽出器に意図的な穴を作らない」の自動検査にあたる。

    2. **罠の段（難易度2以上）は抽出テキストから解けない**
       ここが解けてしまうなら罠が成立していない。

LLM も埋め込みモデルも使わない。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arms.classical.extract import extract_corpus
from gen.__main__ import generate_corpus
from gen.common import Item, normalize_text, read_questions_jsonl

CHANNELS = ["cross_file", "format", "hidden"]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("p1")
    generate_corpus(seed=7, files=60, questions=3, locale_code="ja", channels=CHANNELS, out=out)
    return out


@pytest.fixture(scope="module")
def extracted(corpus: Path) -> dict[str, str]:
    """コーパス相対パス -> そのファイルから抽出できた全テキスト。"""
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


def _source_text(item: Item, extracted: dict[str, str]) -> str:
    return "\n".join(extracted.get(path, "") for path in item.source_files)


# ── 共通 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("channel", CHANNELS)
def test_all_three_tiers_exist(corpus: Path, channel: str) -> None:
    assert set(_items(corpus, channel)) == {1, 2, 3}, f"{channel}: 3段そろっていない"


@pytest.mark.parametrize("channel", CHANNELS)
def test_decoy_only_on_tier_three(corpus: Path, channel: str) -> None:
    items = _items(corpus, channel)
    assert items[3].decoys, f"{channel}: 難易度3 に囮が無い"
    assert not items[1].decoys and not items[2].decoys


# ── format ──────────────────────────────────────────────────────────
def test_format_fill_colour_never_reaches_the_text(corpus: Path, extracted: dict[str, str]) -> None:
    """塗り色そのものは抽出テキストに現れない。

    ※ `format` は正解（管理番号）自体は表の中にあるので、
    「正解文字列が抽出テキストに出るか」では罠を判定できない。
    **どの行が塗られているかを示す手がかりが無い**ことが罠である。
    """
    for item in _items(corpus, "format").values():
        text = _source_text(item, extracted)
        assert item.answer in text, "管理番号は表にあるはず（表自体は読めている）"
        assert "FFF2A8" not in text and "黄" not in text, "塗り色の痕跡が漏れている"


def test_format_control_tier_is_solvable_but_traps_are_not(
    corpus: Path, extracted: dict[str, str]
) -> None:
    items = _items(corpus, "format")
    control = _source_text(items[1], extracted)
    assert "要再検査" in control, "難易度1 は備考からも解けるべき（コントロール）"

    for tier in (2, 3):
        assert "要再検査" not in _source_text(items[tier], extracted), (
            f"難易度{tier} に手がかりが残っている"
        )
    assert "確認中" in _source_text(items[3], extracted), "難易度3 の囮が置かれていない"


# ── hidden ──────────────────────────────────────────────────────────
def test_hidden_notes_never_reach_the_text(corpus: Path, extracted: dict[str, str]) -> None:
    """発表者ノートは抽出されない（SPEC §4-1 の線引き）。"""
    for item in _items(corpus, "hidden").values():
        assert "社内メモ" not in _source_text(item, extracted), "ノートが抽出に漏れている"


def test_hidden_control_tier_is_solvable_but_traps_are_not(
    corpus: Path, extracted: dict[str, str]
) -> None:
    items = _items(corpus, "hidden")
    assert f"{items[1].answer}%" in _source_text(items[1], extracted), (
        "難易度1 は本文からも解けるべき（コントロール）"
    )
    for tier in (2, 3):
        assert f"{items[tier].answer}%" not in _source_text(items[tier], extracted), (
            f"難易度{tier} の答えが本文に漏れている"
        )
    assert f"{items[3].decoys[0]}%" in _source_text(items[3], extracted), (
        "難易度3 の囮が本文に置かれていない"
    )


def test_pptx_extraction_is_not_a_hole(corpus: Path, extracted: dict[str, str]) -> None:
    """pptx から図形テキストが取れている。

    取れていないと `hidden` のコントロール段すら解けず、
    それは罠ではなく抽出器の穴になる（SPEC §4-1 違反）。
    """
    pptx = [p for p in extracted if p.endswith(".pptx")]
    assert pptx, "pptx が 1 件も抽出されていない"
    assert all(extracted[p].strip() for p in pptx)


# ── cross_file ──────────────────────────────────────────────────────
def test_cross_file_total_is_written_nowhere(corpus: Path, extracted: dict[str, str]) -> None:
    haystack = normalize_text("\n".join(extracted.values()))
    for item in _items(corpus, "cross_file").values():
        assert normalize_text(item.answer) not in haystack, (
            f"{item.qid}: 合計 {item.answer} がどこかのファイルに書かれている"
        )


def test_cross_file_tiers_differ_in_file_count(corpus: Path) -> None:
    items = _items(corpus, "cross_file")
    assert len(items[1].source_files) <= 4, "難易度1 は窓に収まる規模であるべき"
    assert len(items[2].source_files) >= 10, "難易度2 は窓を超える規模であるべき"
    assert len(items[3].source_files) > len(items[2].source_files), "難易度3 は集計表のぶん多い"
