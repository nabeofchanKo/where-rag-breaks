"""`version` チャネル — 答えが旧版と新版の実質差分にある。

SPEC §3-1 #8。``old/`` と ``current/`` に同名ファイルを置き、
**体裁変更 N 件 + 実質変更 M 件**を入れる。

なぜ古典的RAGが落ちるのか:
    旧版と新版はほぼ同じ文面なので、チャンクの埋め込みもほぼ同じになる。
    検索は両方を等しく引いてくるが、**どちらが現行版かはチャンクの中身からは
    分からない**（パスにしか書かれていない）。結果、旧版の値を答える。

    この囮は生成器が仕込むものではなく、**旧版の存在そのもの**である。
    したがって難易度2・3 の両方に ``decoys``（旧版の値）を登録する。
    他チャネルが難易度3 にしか囮を持たないのと違う点で、意図的。

難易度 = 罠の機構:
    1 … **コントロール**。現行版しか存在しない。
    2 … old/ と current/ の両方がある。実質変更は保証期間の数値 1 か所で、
        ほかに体裁変更（条番号の表記ゆれ、語尾）が複数ある。
    3 … 同上。さらに「内容は old/ 配下の版を参照のこと」という目次を置く。
        旧版が積極的に引かれるようになる。
"""

from __future__ import annotations

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

# (difficulty, 旧版を置くか, 旧版を指す目次を置くか)
QUESTION_SPECS: tuple[tuple[int, bool, bool], ...] = (
    (1, False, False),
    (2, True, False),
    (3, True, True),
)


def _write_policy(
    path: Path, loc: Locale, code: str, topic: str, months: int, cosmetic: bool
) -> None:
    """規程本体。``cosmetic`` で体裁だけを変える（実質差分は months のみ）。"""
    doc = Document()
    font = doc.styles["Normal"].font
    font.name = "Yu Gothic" if loc.code == "ja" else "Calibri"
    font.size = Pt(10.5)

    doc.add_heading(loc.fmt("vr_title", topic=topic, code=code), level=1)

    sections = (
        ("vr_sec_purpose", loc.fmt("vr_body_purpose", topic=topic)),
        ("vr_sec_scope", loc.fmt("vr_body_scope", topic=topic)),
        ("vr_sec_warranty", loc.fmt("vr_body_warranty", months=months)),
        ("vr_sec_misc", loc.s["vr_body_misc"]),
    )
    for heading_key, body in sections:
        heading = loc.s[heading_key]
        if cosmetic:
            # 体裁変更: 条番号の表記を変える（意味は変わらない）
            heading = heading.replace("第", "").replace("条 ", ". ")
        doc.add_heading(heading, level=2)
        doc.add_paragraph(body)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    normalize_artifact(path)


def _build(
    rng: random.Random, outdir: Path, loc: Locale, code: str, with_old: bool, with_index: bool
) -> tuple[int, int | None, str, list[str]]:
    topic = rng.choice(TOPICS_JA if loc.code == "ja" else TOPICS_EN)
    current_months = rng.choice([12, 18, 24, 36])
    old_months = rng.choice([m for m in (6, 12, 18, 24, 36) if m != current_months])

    files: list[str] = []
    current_rel = f"{SUBDIR}/current/{code}_policy.docx"
    _write_policy(outdir / current_rel, loc, code, topic, current_months, cosmetic=False)
    files.append(current_rel)

    if with_old:
        old_rel = f"{SUBDIR}/old/{code}_policy.docx"
        _write_policy(outdir / old_rel, loc, code, topic, old_months, cosmetic=True)
        files.append(old_rel)

    if with_index:
        index_rel = f"{SUBDIR}/{code}_index.docx"
        doc = Document()
        doc.styles["Normal"].font.size = Pt(10.5)
        doc.add_heading(loc.fmt("vr_index_title", code=code), level=1)
        doc.add_paragraph(loc.fmt("vr_index_body", code=code))
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
        difficulty, with_old, with_index = QUESTION_SPECS[i % len(QUESTION_SPECS)]
        months, old_months, topic, files = _build(
            rng, outdir, locale, code, with_old, with_index
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
        _, with_old, with_index = QUESTION_SPECS[rng.randrange(len(QUESTION_SPECS))]
        _, _, _, files = _build(rng, outdir, locale, f"VR-{n:04d}", with_old, with_index)
        written.extend(files)
    return written
