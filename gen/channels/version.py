"""`version` チャネル — 答えが旧版と新版の実質差分にある。

SPEC §3-1 #8。

━━ 設計履歴（重要）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
初版は SPEC §3-1 #8 の記述どおり ``old/`` と ``current/`` に同名ファイルを
置く構成だった。**これは Arm A に 6/6 で解かれた**（`results/p1-seed42-ja-k8/`）。

原因はパスである。Arm A はチャンクに出所を付けて渡す
（``[policies/current/VR-4879_policy.docx :: 第3条 保証期間]``）。
``current`` と ``old`` がそこに書いてあるので、中身を比べるまでもなく
現行版が分かってしまう。実際モデルの evidence はすべて ``current/`` を指していた。

出所の明示をやめれば罠は「成立」するが、それは evidence を書かせるために必要で
実務でも普通に行うことなので、SPEC §4-1 が禁じる手抜きに当たる。
つまり**罠の設計が甘い**側の問題である（P0 の `formula` と同じ構図）。

そこで難易度2 以降は、**どちらが現行版かをパスから読めないようにした**。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

難易度 = 罠の機構:
    1 … **コントロール**。``old/`` と ``current/`` に分ける初版の構成のまま。
        パスで判別できるので classical が解けて当然の段。
        （初版が解かれたこと自体を、この段が再現し続ける）
    2 … 同一フォルダに、新旧を示唆しない文書管理番号（``_D4127`` など）で並べる。
        どちらが現行かは**文書の冒頭にある改訂日**にしかない。
        しかも改訂日は「第1条」とは別の見出しブロックなので、
        構造を見たチャンク分割では**別チャンクに落ちる**。
        値を読むチャンクと日付を読むチャンクを突き合わせる必要がある。
    3 … 同上。さらに旧版のほうが本文が長く（附則が付く）検索で上位に来やすい。
        旧版を指す目次も置く。

囮は生成器が仕込むものではなく、**旧版が存在すること自体**である。
したがって難易度2・3 の両方に ``decoys``（旧版の値）を登録する。
他チャネルが難易度3 にしか囮を持たないのと違う点で、意図的。
"""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

from docx import Document
from docx.shared import Pt

from gen.common import Item, normalize_artifact
from gen.locales import Locale

CHANNEL = "version"
SUBDIR = "policies"

TOPICS_JA = ("設備調達", "外注管理", "品質保証", "安全衛生")
TOPICS_EN = ("equipment procurement", "subcontracting", "quality assurance", "safety")

# (difficulty, 旧版を置くか, パスで版が分かるか, 旧版を目立たせるか)
QUESTION_SPECS: tuple[tuple[int, bool, bool, bool], ...] = (
    (1, True, True, False),
    (2, True, False, False),
    (3, True, False, True),
)


def _write_policy(
    path: Path,
    loc: Locale,
    code: str,
    topic: str,
    months: int,
    revised: dt.date,
    cosmetic: bool,
    with_appendix: bool,
) -> None:
    """規程本体。

    改訂日は表題直下の「改訂履歴」見出しに置く。保証期間の条文とは
    **別の見出しブロック**になるので、構造を見たチャンク分割では別チャンクに
    落ちる。これが難易度2 以降の肝。
    """
    doc = Document()
    font = doc.styles["Normal"].font
    font.name = "Yu Gothic" if loc.code == "ja" else "Calibri"
    font.size = Pt(10.5)

    doc.add_heading(loc.fmt("vr_title", topic=topic, code=code), level=1)

    doc.add_heading(loc.s["vr_sec_revision"], level=2)
    doc.add_paragraph(loc.fmt("vr_body_revision", date=revised.isoformat()))

    sections = [
        ("vr_sec_purpose", loc.fmt("vr_body_purpose", topic=topic)),
        ("vr_sec_scope", loc.fmt("vr_body_scope", topic=topic)),
        ("vr_sec_warranty", loc.fmt("vr_body_warranty", months=months)),
        ("vr_sec_misc", loc.s["vr_body_misc"]),
    ]
    for heading_key, body in sections:
        heading = loc.s[heading_key]
        if cosmetic:
            # 体裁変更: 条番号の表記を変える（意味は変わらない）
            heading = heading.replace("第", "").replace("条 ", ". ")
        doc.add_heading(heading, level=2)
        doc.add_paragraph(body)

    if with_appendix:
        # 旧版だけを長くする。検索で上位に来やすくなる。
        doc.add_heading(loc.s["vr_sec_appendix"], level=2)
        for line in loc.s["vr_body_appendix"].split("\n"):
            doc.add_paragraph(line)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    normalize_artifact(path)


def _build(
    rng: random.Random,
    outdir: Path,
    loc: Locale,
    code: str,
    with_old: bool,
    path_reveals: bool,
    emphasise_old: bool,
) -> tuple[int, int | None, str, list[str]]:
    topic = rng.choice(TOPICS_JA if loc.code == "ja" else TOPICS_EN)
    current_months = rng.choice([12, 18, 24, 36])
    old_months = rng.choice([m for m in (6, 12, 18, 24, 36) if m != current_months])

    current_date = dt.date(2027, rng.randrange(6, 13), rng.randrange(1, 28))
    old_date = dt.date(2025, rng.randrange(1, 13), rng.randrange(1, 28))

    files: list[str] = []
    if path_reveals:
        current_rel = f"{SUBDIR}/current/{code}_policy.docx"
        old_rel = f"{SUBDIR}/old/{code}_policy.docx"
    else:
        # 版の別がパスに出ない形にする。
        # ★ ``_ed1`` / ``_ed2`` のような連番は使わない。番号の大小そのものが
        #   新旧のヒントになり、日付を読まずに当てられてしまう。
        #   文書管理番号（採番順と改訂順が無関係）を模して、2つとも
        #   ランダムな番号にする。
        doc_ids = rng.sample(range(1000, 9999), 2)
        current_rel = f"{SUBDIR}/{code}_policy_D{doc_ids[0]}.docx"
        old_rel = f"{SUBDIR}/{code}_policy_D{doc_ids[1]}.docx"

    _write_policy(
        outdir / current_rel, loc, code, topic, current_months, current_date,
        cosmetic=False, with_appendix=False,
    )
    files.append(current_rel)

    if with_old:
        _write_policy(
            outdir / old_rel, loc, code, topic, old_months, old_date,
            cosmetic=True, with_appendix=emphasise_old,
        )
        files.append(old_rel)

    if emphasise_old:
        index_rel = f"{SUBDIR}/{code}_index.docx"
        doc = Document()
        doc.styles["Normal"].font.size = Pt(10.5)
        doc.add_heading(loc.fmt("vr_index_title", code=code), level=1)
        doc.add_paragraph(loc.fmt("vr_index_body", code=code, name=Path(old_rel).name))
        path = outdir / index_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)
        normalize_artifact(path)
        files.append(index_rel)

    return current_months, (old_months if with_old else None), topic, files


def generate(rng: random.Random, outdir: Path, n_questions: int, locale: Locale) -> list[Item]:
    codes = [f"VR-{n:04d}" for n in rng.sample(range(1000, 5000), n_questions)]

    items: list[Item] = []
    for i, code in enumerate(codes):
        difficulty, with_old, path_reveals, emphasise = QUESTION_SPECS[
            i % len(QUESTION_SPECS)
        ]
        months, old_months, topic, files = _build(
            rng, outdir, locale, code, with_old, path_reveals, emphasise
        )
        items.append(
            Item(
                qid=f"{CHANNEL}-{i + 1:02d}",
                channel=CHANNEL,
                question=locale.fmt("q_version", code=code, topic=topic),
                answer=str(months),
                answer_type="number",
                answer_aliases=[f"{months}か月", f"{months} months"],
                source_files=files,
                # 囮 = 旧版の値。仕込むのではなく、旧版が存在すること自体が囮。
                decoys=[str(old_months)] if old_months is not None else [],
                difficulty=difficulty,
                locale=locale.code,
            )
        )
    return items


def generate_fillers(rng: random.Random, outdir: Path, count: int, locale: Locale) -> list[str]:
    written: list[str] = []
    for n in rng.sample(range(5000, 9999), count):
        _, with_old, path_reveals, emphasise = QUESTION_SPECS[
            rng.randrange(len(QUESTION_SPECS))
        ]
        _, _, _, files = _build(
            rng, outdir, locale, f"VR-{n:04d}", with_old, path_reveals, emphasise
        )
        written.extend(files)
    return written
