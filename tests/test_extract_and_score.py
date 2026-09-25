"""抽出・チャンク分割・採点の単体テスト。

ここは **LLM も埋め込みモデルも使わない**範囲だけを見る。CI は `arms` 依存
グループ（torch など）を入れないので、重い依存を引く経路を踏まないことも
このテストが同時に保証している。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arms.classical.chunk import chunk_blocks
from arms.classical.extract import Block, extract_corpus
from eval.score import exact_match, matches_decoy
from gen.__main__ import generate_corpus
from gen.common import Item, normalize_text, number_aliases, read_questions_jsonl


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("corpus")
    generate_corpus(
        seed=42, files=14, questions=3, locale_code="ja", channels=["formula", "text"], out=out
    )
    return out


# ── 抽出 ────────────────────────────────────────────────────────────
def test_extracts_both_formats(corpus: Path) -> None:
    blocks = extract_corpus(corpus / "files")
    suffixes = {Path(b.path).suffix for b in blocks}
    assert suffixes == {".docx", ".xlsx"}
    assert all(b.text.strip() for b in blocks)


def test_formula_channel_has_all_three_traps(corpus: Path) -> None:
    """`formula` の3段が実際に作られている（SPEC §2 の反証を受けた作り直し）。

    難易度1 はコントロール（罠なし）、2 は k の窓超え、3 は陳腐化キャッシュ。
    段が潰れると、どの機構が効いたのかを結果から切り分けられなくなる。
    """
    from openpyxl import load_workbook

    items = [
        it for it in read_questions_jsonl(corpus / "questions.jsonl") if it.channel == "formula"
    ]
    by_difficulty = {it.difficulty: it for it in items}
    assert set(by_difficulty) == {1, 2, 3}, "3段そろっていない"

    def rows_of(item) -> int:
        ws = load_workbook(corpus / "files" / item.source_files[0], data_only=False)["明細"]
        return sum(1 for r in ws.iter_rows(min_row=5) if r[0].value is not None)

    assert rows_of(by_difficulty[1]) < 20, "難易度1 は小規模明細のはず"
    assert rows_of(by_difficulty[2]) > 200, "難易度2 は k の窓を超える規模のはず"

    # 難易度3: 陳腐化したキャッシュ値が入っていて、それが囮として登録されている
    d3 = by_difficulty[3]
    cached = load_workbook(corpus / "files" / d3.source_files[0], data_only=True)["サマリ"]
    assert cached["B5"].value is not None, "キャッシュ値が注入されていない"
    assert str(cached["B5"].value) != d3.answer, (
        "キャッシュ値が正解と一致している（囮になっていない）"
    )
    assert d3.decoys == [str(cached["B5"].value)], "囮が Item に記録されていない"

    assert not by_difficulty[1].decoys and not by_difficulty[2].decoys


def test_decoy_is_reachable_but_answer_is_not(corpus: Path) -> None:
    """囮は抽出テキストに現れ、正解は現れない。

    これが逆転していたら罠が成立していない。
    """
    haystack = normalize_text("\n".join(b.text for b in extract_corpus(corpus / "files")))
    items = [
        it for it in read_questions_jsonl(corpus / "questions.jsonl") if it.channel == "formula"
    ]
    for item in items:
        for decoy in item.decoys:
            assert normalize_text(decoy) in haystack, f"{item.qid}: 囮 {decoy} が読めない位置にある"


def test_xlsx_extraction_keeps_formulas_and_cell_refs(corpus: Path) -> None:
    """★ SPEC §4-1: 抽出器に穴を作らない。

    data_only=True だけで読むと数式セルが全部 None になる。それは
    「古典的RAGの限界」ではなく実装の手抜きなので、数式文字列とセル番地を
    必ず出していることを固定する。
    """
    blocks = extract_corpus(corpus / "files")
    summary = [b for b in blocks if b.path.endswith(".xlsx") and "サマリ" in b.locator]
    assert summary, "サマリシートが抽出できていない"

    text = summary[0].text
    assert "=SUM(" in text, "数式が抽出されていない（抽出器の穴になっている）"
    assert "=SUMIF(" in text
    assert "B2:" in text or "B2: " in text, "セル番地が失われている"


def test_formula_channel_answer_is_absent_from_extracted_text(corpus: Path) -> None:
    """`formula` の正解は抽出テキストのどこにも現れない（SPEC §3-1 #3）。

    これが崩れたら罠が成立していない。合計値がファイルに書き込まれてしまった
    ということなので、生成器のバグ。
    """
    items = [
        it for it in read_questions_jsonl(corpus / "questions.jsonl") if it.channel == "formula"
    ]
    assert items, "formula の設問が無い"

    haystack = normalize_text("\n".join(b.text for b in extract_corpus(corpus / "files")))
    for item in items:
        assert normalize_text(item.answer) not in haystack, (
            f"{item.qid}: 合計値 {item.answer} が抽出テキストに現れている。罠が壊れている"
        )


def test_text_channel_answer_is_present_in_extracted_text(corpus: Path) -> None:
    """`text` の正解は抽出テキストに存在する（ベースラインとして成立している）。"""
    items = [it for it in read_questions_jsonl(corpus / "questions.jsonl") if it.channel == "text"]
    haystack = normalize_text("\n".join(b.text for b in extract_corpus(corpus / "files")))
    for item in items:
        assert any(normalize_text(a) in haystack for a in item.accepted), (
            f"{item.qid}: 正解 {item.answer} が本文から抽出できていない"
        )


# ── チャンク分割 ────────────────────────────────────────────────────
def test_chunks_keep_provenance(corpus: Path) -> None:
    chunks = chunk_blocks(extract_corpus(corpus / "files"))
    assert chunks
    for c in chunks:
        assert c.path and c.locator
        assert c.path in c.render()


def test_long_sheet_split_repeats_the_header_row() -> None:
    """表を分割するときはヘッダ行を各断片に複製する（列の意味を失わせない）。"""
    header = "A1: 品目 | B1: 数量 | C1: 単価"
    rows = "\n".join(f"A{i}: 品目{i} | B{i}: {i} | C{i}: {i * 100}" for i in range(2, 60))
    blocks = [Block(path="x.xlsx", locator="シート 明細", text=f"{header}\n{rows}")]

    pieces = chunk_blocks(blocks, chunk_chars=300, overlap_chars=60)
    assert len(pieces) > 1, "分割されていない"
    assert all(p.text.startswith(header) for p in pieces), "ヘッダ行が複製されていない"


# ── 採点 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("answer", "candidate", "expected"),
    [
        ("1320", "1,320", True),  # 桁区切り
        ("1320", "1320円", False),  # 単位付きは alias で明示しない限り不正解
        ("佐藤 健一", "佐藤健一", True),  # 空白
        ("2027-03-19", "2027-03-19。", True),  # 末尾句読点
        ("設備保全部", "調達部", False),
        ("1320", "", False),  # 空回答
        ("1320", "13200", False),  # 桁違いを吸収してはいけない
    ],
)
def test_exact_match_normalisation(answer: str, candidate: str, expected: bool) -> None:
    item = Item(
        qid="t-01", channel="text", question="?", answer=answer, answer_type="text", locale="ja"
    )
    assert exact_match(item, candidate) is expected


def test_exact_match_accepts_declared_aliases() -> None:
    item = Item(
        qid="t-02",
        channel="formula",
        question="?",
        answer="1320",
        answer_type="number",
        answer_aliases=number_aliases(1320, "円")[1:],
        locale="ja",
    )
    assert exact_match(item, "1,320円")
    assert exact_match(item, "1320")
    assert not exact_match(item, "1320ドル")


def test_matches_decoy() -> None:
    """囮の判定も正規化を通す（表記揺れで取りこぼさない）。"""
    item = Item(
        qid="f-01",
        channel="formula",
        question="?",
        answer="37885100",
        answer_type="number",
        decoys=["38955400"],
        locale="ja",
    )
    assert matches_decoy(item, "38,955,400")
    assert not matches_decoy(item, "37885100")
    assert not matches_decoy(item, "")


def test_decoy_cannot_equal_the_answer() -> None:
    """囮と正解が同一の Item は作れない（作れると採点が壊れる）。"""
    with pytest.raises(ValueError, match="囮になっていない"):
        Item(
            qid="f-02",
            channel="formula",
            question="?",
            answer="100",
            answer_type="number",
            decoys=["100"],
            locale="ja",
        )
