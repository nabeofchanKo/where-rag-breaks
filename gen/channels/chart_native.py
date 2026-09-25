"""`chart_native` チャネル — 答えがネイティブchartの定義にしかない。

SPEC §3-1 #5 / §3-5。系列を**非表示シート**の範囲に向ける。

★ 罠の正確な所在（ここを取り違えると設計が甘くなる）:
    openpyxl は非表示シートも ``wb.sheetnames`` に含めるので、
    **数値そのものは抽出テキストに現れる**。隠れているのは数値ではなく
    「どの列がどの拠点か」という**対応づけ**である。それは
    ``xl/charts/chart1.xml`` の系列定義にしかなく、値を読むだけの抽出器には
    絶対に出てこない。

    P0 の `formula` で「集計値だけ隠しても入力が読めれば再計算される」と
    反証されたのと同じ轍を踏まないよう、隠すのは**意味の対応づけ**にしてある。

難易度 = 罠の機構:
    1 … **コントロール**。見える側のシートに拠点名つきの参考表がある。
    2 … 非表示シートは数値だけ。拠点名はグラフの系列定義にしかない。
    3 … 同上。さらに見える側に「掲載順: …」という**別の順序**の注記を置く。
        列順と取り違えると別の拠点を答える。``decoys`` に登録済み。
"""

from __future__ import annotations

import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, Series
from openpyxl.chart.series import SeriesLabel
from openpyxl.styles import Font

from gen.common import Item, normalize_artifact
from gen.locales import Locale

CHANNEL = "chart_native"
SUBDIR = "utilisation"

MONTHS_JA = ("1月", "2月", "3月", "4月")
MONTHS_EN = ("January", "February", "March", "April")

# (difficulty, 参考表を出すか, 別順序の注記を置くか)
QUESTION_SPECS: tuple[tuple[int, bool, bool], ...] = (
    (1, True, False),
    (2, False, False),
    (3, False, True),
)


def _build(
    rng: random.Random,
    outdir: Path,
    loc: Locale,
    code: str,
    show_table: bool,
    show_order_note: bool,
) -> tuple[str, str, str | None, str]:
    months = MONTHS_JA if loc.code == "ja" else MONTHS_EN
    sites = rng.sample(loc.sites, 4)
    # 列 = 拠点、行 = 月。値は重複させない（最大が一意に決まるように）
    values = {
        site: rng.sample(range(50, 99), len(months)) for site in sites
    }

    asked_month_index = rng.randrange(len(months))
    column = [values[site][asked_month_index] for site in sites]
    answer_site = sites[column.index(max(column))]

    wb = Workbook()
    visible = wb.active
    visible.title = loc.s["cn_sheet_visible"]
    hidden = wb.create_sheet(loc.s["cn_sheet_hidden"])
    hidden.sheet_state = "hidden"

    period = "2027年度" if loc.code == "ja" else "FY2027"
    visible["A1"] = loc.fmt("cn_title", period=period, code=code)
    visible["A1"].font = Font(bold=True, size=13)
    visible["A2"] = loc.s["cn_note_caption"]

    decoy: str | None = None
    if show_order_note:
        # グラフの系列順とは**別の順序**。列順と取り違えると別の拠点になる。
        shuffled = sites[:]
        rng.shuffle(shuffled)
        visible["A3"] = loc.fmt("cn_note_order_decoy", order="、".join(shuffled))
        candidate = shuffled[column.index(max(column))]
        decoy = candidate if candidate != answer_site else None

    if show_table:
        visible["A5"] = loc.s["cn_table_heading"]
        visible["A5"].font = Font(bold=True)
        for col, site in enumerate(sites, start=2):
            visible.cell(row=6, column=col, value=site)
        for row, month in enumerate(months, start=7):
            visible.cell(row=row, column=1, value=month)
            for col, site in enumerate(sites, start=2):
                visible.cell(row=row, column=col, value=values[site][row - 7])

    # ── 非表示シート: **ラベルを一切置かない**数値だけの行列 ──
    for row_index, _month in enumerate(months, start=1):
        for col_index, site in enumerate(sites, start=1):
            hidden.cell(row=row_index, column=col_index, value=values[site][row_index - 1])

    # ── グラフ: 系列名（拠点名）はここにしかない ──
    chart = BarChart()
    chart.title = loc.s["cn_chart_title"]
    for col_index, site in enumerate(sites, start=1):
        reference = Reference(hidden, min_col=col_index, min_row=1, max_row=len(months))
        series = Series(reference)
        series.tx = SeriesLabel(v=site)  # ← 拠点名はチャート定義の中だけ
        chart.series.append(series)
    chart.set_categories(
        Reference(visible, min_col=1, min_row=7, max_row=6 + len(months))
        if show_table
        else Reference(hidden, min_col=1, min_row=1, max_row=len(months))
    )
    visible.add_chart(chart, "H3")

    rel = f"{SUBDIR}/{code}_utilisation.xlsx"
    path = outdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    normalize_artifact(path)

    return months[asked_month_index], answer_site, decoy, rel


def generate(rng: random.Random, outdir: Path, n_questions: int, locale: Locale) -> list[Item]:
    codes = [f"UT-{n:04d}" for n in rng.sample(range(1000, 5000), n_questions)]

    items: list[Item] = []
    for i, code in enumerate(codes):
        difficulty, show_table, show_order = QUESTION_SPECS[i % len(QUESTION_SPECS)]
        month, site, decoy, rel = _build(rng, outdir, locale, code, show_table, show_order)
        items.append(
            Item(
                qid=f"{CHANNEL}-{i + 1:02d}",
                channel=CHANNEL,
                question=locale.fmt("q_chart_native", code=code, month=month),
                answer=site,
                answer_type="name",
                source_files=[rel],
                decoys=[decoy] if decoy else [],
                difficulty=difficulty,
                locale=locale.code,
            )
        )
    return items


def generate_fillers(rng: random.Random, outdir: Path, count: int, locale: Locale) -> list[str]:
    written: list[str] = []
    for n in rng.sample(range(5000, 9999), count):
        _, show_table, show_order = QUESTION_SPECS[rng.randrange(len(QUESTION_SPECS))]
        _, _, _, rel = _build(rng, outdir, locale, f"UT-{n:04d}", show_table, show_order)
        written.append(rel)
    return written
