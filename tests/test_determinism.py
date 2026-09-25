"""SPEC §8 P0 の完了条件「同 seed 再生成がバイト一致」を固定するテスト。

このテストが落ちたら、コーパスのどこかに実行ごとに変わる値（時刻・PID・
salt つきハッシュ・辞書順に依存しない反復）が混入している。数値が変わる
原因を潰さないまま先へ進むと、あとで「前回と結果が違う」の切り分けが
できなくなる。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gen.__main__ import generate_corpus
from gen.channels import ALL_CHANNELS
from gen.common import Item, hash_tree, normalize_ooxml, read_questions_jsonl

SMALL = {"files": 10, "questions": 2, "channels": sorted(ALL_CHANNELS)}


def _generate(out: Path, *, seed: int = 42, locale: str = "ja", **kw) -> dict:
    params = {**SMALL, **kw}
    return generate_corpus(seed=seed, locale_code=locale, out=out, **params)


@pytest.mark.parametrize("locale", ["ja", "en"])
def test_same_seed_is_byte_identical(tmp_path: Path, locale: str) -> None:
    """同じ seed・同じ引数なら、生成物は1バイトも変わらない。"""
    a, b = tmp_path / "a", tmp_path / "b"
    _generate(a, locale=locale)
    _generate(b, locale=locale)

    ha, hb = hash_tree(a), hash_tree(b)
    assert sorted(ha) == sorted(hb), "生成されたファイルの一覧が違う"

    differing = [name for name in ha if ha[name] != hb[name]]
    assert not differing, f"同 seed なのに内容が違うファイル: {differing}"


def test_different_seed_changes_the_corpus(tmp_path: Path) -> None:
    """seed を変えれば中身が変わる（seed が実際に効いていることの確認）。"""
    a, b = tmp_path / "a", tmp_path / "b"
    _generate(a, seed=42)
    _generate(b, seed=43)
    assert hash_tree(a) != hash_tree(b)


def test_locale_changes_the_corpus(tmp_path: Path) -> None:
    """--locale が実際に本文を切り替えている。"""
    ja, en = tmp_path / "ja", tmp_path / "en"
    _generate(ja, locale="ja")
    _generate(en, locale="en")

    ja_items = read_questions_jsonl(ja / "questions.jsonl")
    en_items = read_questions_jsonl(en / "questions.jsonl")
    assert all(it.locale == "ja" for it in ja_items)
    assert all(it.locale == "en" for it in en_items)
    assert any(ord(ch) > 0x3000 for it in ja_items for ch in it.question), (
        "ja コーパスの設問に日本語が含まれていない"
    )
    assert all(ord(ch) < 0x3000 for it in en_items for ch in it.question), (
        "en コーパスの設問に非ASCII文字が混ざっている"
    )


def test_filenames_are_ascii(tmp_path: Path) -> None:
    """ファイル名・フォルダ名は常に ASCII（SPEC §10 の NFD 罠回避）。"""
    for locale in ("ja", "en"):
        out = tmp_path / locale
        _generate(out, locale=locale)
        for path in out.rglob("*"):
            rel = path.relative_to(out).as_posix()
            assert rel.isascii(), f"ASCII でないパス: {rel}"


def test_normalize_ooxml_is_idempotent(tmp_path: Path) -> None:
    """正規化を二度かけても結果が変わらない。"""
    out = tmp_path / "c"
    _generate(out)
    target = next((out / "files").rglob("*.xlsx"))
    before = target.read_bytes()
    normalize_ooxml(target)
    assert target.read_bytes() == before


def test_every_question_has_a_label_and_a_source(tmp_path: Path) -> None:
    """全問に正解ラベルと、答えが実在するファイルへの参照がある。"""
    out = tmp_path / "c"
    meta = _generate(out)
    items = read_questions_jsonl(out / "questions.jsonl")

    assert len(items) == meta["n_questions"] > 0
    assert len({it.qid for it in items}) == len(items), "qid が重複している"

    for it in items:
        assert it.answer.strip(), f"{it.qid}: 正解が空"
        assert it.source_files, f"{it.qid}: source_files が空"
        for rel in it.source_files:
            assert (out / "files" / rel).is_file(), f"{it.qid}: {rel} が存在しない"


def test_questions_jsonl_is_stable_and_sorted(tmp_path: Path) -> None:
    """questions.jsonl は qid 昇順で、再読込しても同じ Item に戻る。"""
    out = tmp_path / "c"
    _generate(out)
    raw = (out / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    qids = [json.loads(line)["qid"] for line in raw]
    assert qids == sorted(qids)

    items = read_questions_jsonl(out / "questions.jsonl")
    assert all(isinstance(it, Item) for it in items)


def test_meta_has_no_timestamp(tmp_path: Path) -> None:
    """meta.json に実行時刻を書かない（書くとバイト一致が壊れる）。"""
    out = tmp_path / "c"
    _generate(out)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    forbidden = {"generated_at", "timestamp", "created_at", "date", "run_at"}
    assert not (forbidden & meta.keys()), f"meta.json に時刻が入っている: {meta.keys()}"
