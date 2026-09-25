"""`layout` チャネル — 答えが図形の空間関係にしかない。

SPEC §3-1 #7。PIL で座席図を既知座標に描き、docx に埋め込む。

なぜ古典的RAGが落ちるのか:
    「誰がどこに座っているか」は画像の中の**座標**にしかない。
    名前の一覧を抜き出しても、隣接関係は復元できない。
    抽出テキストに現れるのは本文のキャプションだけである。

難易度 = 罠の機構:
    1 … **コントロール**。本文に座席割当の表と「A列は左から A-1、A-2、A-3」という
        並び順の規則が書いてある。テキストだけで隣席を導ける。
    2 … 画像のみ。本文はキャプションだけ。
    3 … 画像のみ。さらに**五十音順**の在席者一覧を本文に置く。
        座席順と並びが違うので、一覧を座席順と取り違えると隣人を間違える。
        その間違いで出てくる氏名を ``decoys`` に登録してある。
"""

from __future__ import annotations

import random
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt

from gen.common import Item, normalize_artifact
from gen.imaging import Seat, save_layout_png
from gen.locales import Locale

CHANNEL = "layout"
SUBDIR = "facilities"
IMAGE_SUBDIR = "facilities/figures"

ROWS = ("A", "B", "C")
SEATS_PER_ROW = 3
ORIGIN_X, ORIGIN_Y = 90, 110
STEP_X, STEP_Y = 150, 110

# (difficulty, 座席割当の表と規則を本文に出すか, 五十音順一覧を本文に出すか)
QUESTION_SPECS: tuple[tuple[int, bool, bool], ...] = (
    (1, True, False),
    (2, False, False),
    (3, False, True),
)


def _roster_neighbour(people: list[str], index: int) -> str | None:
    """五十音順一覧の上で、``people[index]`` の隣に並ぶ氏名。

    一覧を座席順と取り違えたときに拾ってしまう名前＝囮。実際の隣人と
    同じ名前になる席では囮が成立しないので ``None`` を返す。
    後ろが無ければ前を使う（一覧の末尾から出題しても囮が作れるように）。
    """
    roster = sorted(people)
    position = roster.index(people[index])
    candidate = (
        roster[position + 1] if position + 1 < len(roster) else roster[position - 1]
    )
    actual_neighbour = people[index + 1]
    return None if candidate == actual_neighbour else candidate


def _seat_grid(people: list[str]) -> list[Seat]:
    seats: list[Seat] = []
    for row_index in range(len(ROWS)):
        for col in range(SEATS_PER_ROW):
            person = people[row_index * SEATS_PER_ROW + col]
            seats.append(
                Seat(
                    label=person,
                    x=ORIGIN_X + col * STEP_X,
                    y=ORIGIN_Y + row_index * STEP_Y,
                )
            )
    return seats


def _build(
    rng: random.Random,
    outdir: Path,
    loc: Locale,
    code: str,
    show_table: bool,
    show_roster: bool,
) -> tuple[str, str, str | None, list[str]]:
    people = rng.sample(loc.people, len(ROWS) * SEATS_PER_ROW)
    number = rng.randrange(1, 6)
    room = f"第{number}会議室" if loc.code == "ja" else f"Meeting room {number}"

    # 右隣が存在する席（各行の最後の席は除く）から出題する
    candidates = [
        i for i in range(len(people)) if (i % SEATS_PER_ROW) < SEATS_PER_ROW - 1
    ]
    if show_roster:
        # 難易度3 は「五十音順一覧を座席順と取り違える」ことが罠なので、
        # 一覧上の隣が実際の隣人と**別人になる**席から出題しないと囮が成立しない。
        usable = [i for i in candidates if _roster_neighbour(people, i) is not None]
        candidates = usable or candidates
    asked = rng.choice(candidates)
    person, neighbour = people[asked], people[asked + 1]

    image_rel = f"{IMAGE_SUBDIR}/{code}_seating.png"
    save_layout_png(
        outdir / image_rel,
        loc.fmt("ly_doc_title", room=room, code=code),
        _seat_grid(people),
        loc.code,
    )

    doc = Document()
    font = doc.styles["Normal"].font
    font.name = "Yu Gothic" if loc.code == "ja" else "Calibri"
    font.size = Pt(10.5)
    doc.add_heading(loc.fmt("ly_doc_title", room=room, code=code), level=1)
    doc.add_paragraph(loc.s["ly_caption"])
    doc.add_picture(str(outdir / image_rel), width=Inches(6.0))

    decoy: str | None = None
    if show_table:
        doc.add_heading(loc.s["ly_table_heading"], level=2)
        doc.add_paragraph(loc.s["ly_seat_rule"])
        for index, name in enumerate(people):
            seat = f"{ROWS[index // SEATS_PER_ROW]}-{index % SEATS_PER_ROW + 1}"
            doc.add_paragraph(f"{seat}: {name}")
    if show_roster:
        # 座席順ではない並び。これを座席順と取り違えると隣人を間違える。
        doc.add_heading(loc.s["ly_roster_heading"], level=2)
        for name in sorted(people):
            doc.add_paragraph(name)
        decoy = _roster_neighbour(people, asked)

    doc_rel = f"{SUBDIR}/{code}_seating.docx"
    path = outdir / doc_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    normalize_artifact(path)

    return person, neighbour, decoy, [doc_rel, image_rel]


def generate(rng: random.Random, outdir: Path, n_questions: int, locale: Locale) -> list[Item]:
    codes = [f"LY-{n:04d}" for n in rng.sample(range(1000, 5000), n_questions)]

    items: list[Item] = []
    for i, code in enumerate(codes):
        difficulty, show_table, show_roster = QUESTION_SPECS[i % len(QUESTION_SPECS)]
        person, neighbour, decoy, files = _build(
            rng, outdir, locale, code, show_table, show_roster
        )
        aliases = [neighbour.replace(" ", "")] if " " in neighbour else []
        items.append(
            Item(
                qid=f"{CHANNEL}-{i + 1:02d}",
                channel=CHANNEL,
                question=locale.fmt("q_layout", code=code, person=person),
                answer=neighbour,
                answer_type="name",
                answer_aliases=aliases,
                source_files=files,
                decoys=[decoy] if decoy else [],
                difficulty=difficulty,
                locale=locale.code,
            )
        )
    return items


def generate_fillers(rng: random.Random, outdir: Path, count: int, locale: Locale) -> list[str]:
    written: list[str] = []
    for n in rng.sample(range(5000, 9999), count):
        _, show_table, show_roster = QUESTION_SPECS[rng.randrange(len(QUESTION_SPECS))]
        _, _, _, files = _build(rng, outdir, locale, f"LY-{n:04d}", show_table, show_roster)
        written.extend(files)
    return written
