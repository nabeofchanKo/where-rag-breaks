"""`formula` チャネル — 答えが数式とその参照範囲にある。

SPEC §3-1 #3 / §3-5。

━━ 設計履歴（重要）━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
初版は「合計値をどこにも書かない」だけの罠だった。**これは Arm A に 10/10 で
突破された**（`results/pilot-k8-forced/`）。SPEC §2 の反証条件に該当する。

原因は Arm A の手抜きではなく罠の設計。集計結果だけを隠しても、**入力（数量・
単価・区分）が読める形で残っていれば現代のモデルは再計算する**。実際モデルは
数量×単価を12行ぶん計算し、別シートの税率を掛けて正解していた。

SPEC §2「★ 反証されたら仕様を直す。結果に合わせて評価を曲げない」に従い、
難易度の軸を「計算の複雑さ」から「**何が抽出不能か**」へ組み替えた。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

難易度 = 罠の機構:

    1 … **コントロール**。初版のまま（集計値なし・入力は読める）。
        classical が解けて当然の段。ここが解けないなら実装がおかしい。
        罠を積んだだけではないことを示すために**意図的に残している**。

    2 … **k の窓に入らない**。明細を 240〜320 行にする。チャンク分割すると
        十数個の断片になり、top-k がそれを全部は載せられない。検索が
        失敗しているのではなく、窓が足りない。k を上げれば解けるが
        コストが上がる（cost_accuracy.png の材料になる）。

    3 … **キャッシュ値の陳腐化**。サマリシートの数式セルに、旧版の明細から
        計算した値を後処理で注入する。``data_only=True`` で読むと、数式と
        食い違う古い値が返る。classical は**自信満々に古い値を答える**。
        この囮の値は ``Item.decoys`` に入れ、採点時に「囮を掴んだ割合」を
        集計できるようにしてある。

★ 難易度3の正解について:
    明細の行が事実であり、サマリのキャッシュはそれと整合しない古い値である。
    「この見積の税込総額は」と問われたときの正解は明細から計算した値であって、
    古いキャッシュではない。ファイルには改訂履歴行を置いて、明細が新しい版で
    あることが読み取れるようにしている。
"""

from __future__ import annotations

import random
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from gen.common import Item, inject_cached_value, normalize_artifact, number_aliases
from gen.locales import Locale

CHANNEL = "formula"
SUBDIR = "quotes"

HEADER_ROW = 4  # 1:表題 2:改訂履歴 3:空 4:見出し
FIRST_DATA_ROW = 5
TAX_RATE = Decimal("0.10")

SMALL_ROWS = (8, 13)  # 難易度1・3
LARGE_ROWS = (240, 321)  # 難易度2（チャンクの窓を超えさせる）

# (質問キー, 答えの種類, difficulty, 行数の規模, キャッシュを陳腐化させるか)
QUESTION_SPECS: tuple[tuple[str, str, int, tuple[int, int], bool], ...] = (
    ("q_subtotal", "subtotal", 1, SMALL_ROWS, False),
    ("q_subtotal", "subtotal", 2, LARGE_ROWS, False),
    ("q_total", "total", 3, SMALL_ROWS, True),
)


def _excel_round(value: Decimal) -> int:
    """Excel の ROUND(x, 0) と同じ丸め（0 から遠い方へ half up）。

    Python 組込みの ``round`` は銀行家丸めなので使えない。正解が 1 円ずれる。
    """
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _item_name(loc: Locale, rng: random.Random, index: int, many: bool) -> str:
    base = loc.items[index % len(loc.items)] if many else rng.choice(loc.items)
    if not many:
        return base
    # 大規模な明細では同じ品目が枝番つきで何度も出る（実在の部品表に近い形）
    return loc.fmt("xl_item_numbered", item=base, n=index + 1)


def _make_lines(rng: random.Random, loc: Locale, rows: tuple[int, int]) -> list[dict]:
    """明細行を決める。ここで確定した値がそのまま正解計算の入力になる。"""
    n = rng.randrange(*rows)
    many = n > len(loc.items)
    names = (
        [_item_name(loc, rng, i, True) for i in range(n)]
        if many
        else rng.sample(loc.items, n)
    )
    approved, on_hold = loc.statuses

    lines = [
        {
            "item": name,
            "qty": rng.randrange(1, 25),
            "unit_price": rng.randrange(12, 900) * 1000,
            "status": on_hold if rng.random() < 0.35 else approved,
        }
        for name in names
    ]
    # 承認済と保留が最低1件ずつ存在することを保証する
    if all(line["status"] == approved for line in lines):
        lines[rng.randrange(n)]["status"] = on_hold
    if all(line["status"] == on_hold for line in lines):
        lines[rng.randrange(n)]["status"] = approved
    return lines


def _previous_revision(rng: random.Random, lines: list[dict]) -> list[dict]:
    """旧版の明細を作る。難易度3の陳腐化キャッシュはこれを元に計算する。

    数量を何件か変えるだけにする（品目の増減まで変えると、旧版の合計が
    現行の明細からは到底導けない数になり、囮として不自然になる）。
    """
    old = [dict(line) for line in lines]
    for index in rng.sample(range(len(old)), min(3, len(old))):
        delta = rng.choice((-3, -2, -1, 1, 2, 3))
        old[index]["qty"] = max(1, old[index]["qty"] + delta)
    return old


def _compute(lines: list[dict], approved_label: str) -> dict[str, int]:
    """正解を **生成時に** 計算する。ファイルを読み直して作らない（SPEC §3-3）。"""
    subtotal = sum(line["qty"] * line["unit_price"] for line in lines)
    approved = sum(
        line["qty"] * line["unit_price"] for line in lines if line["status"] == approved_label
    )
    tax = _excel_round(Decimal(subtotal) * TAX_RATE)
    return {"subtotal": subtotal, "approved": approved, "tax": tax, "total": subtotal + tax}


def _write_workbook(
    path: Path, loc: Locale, code: str, project: str, lines: list[dict], revision: int
) -> None:
    """明細 / サマリ / 設定 の3シートを書く。**計算結果はどこにも書かない。**"""
    wb = Workbook()
    detail = wb.active
    detail.title = loc.s["xl_sheet_detail"]
    summary = wb.create_sheet(loc.s["xl_sheet_summary"])
    config = wb.create_sheet(loc.s["xl_sheet_config"])

    # ── 明細シート ────────────────────────────────────────
    detail["A1"] = loc.fmt("xl_title", project=project, code=code)
    detail["A1"].font = Font(bold=True, size=13)
    detail["A2"] = loc.fmt("xl_revision", n=revision)

    headers = ("xl_h_item", "xl_h_qty", "xl_h_unit_price", "xl_h_amount", "xl_h_status")
    for col, key in enumerate(headers, start=1):
        cell = detail.cell(row=HEADER_ROW, column=col, value=loc.s[key])
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for offset, line in enumerate(lines):
        r = FIRST_DATA_ROW + offset
        detail.cell(row=r, column=1, value=line["item"])
        detail.cell(row=r, column=2, value=line["qty"])
        detail.cell(row=r, column=3, value=line["unit_price"])
        # 金額そのものが数式。抽出テキストに個々の金額すら現れない。
        detail.cell(row=r, column=4, value=f"=B{r}*C{r}")
        detail.cell(row=r, column=5, value=line["status"])

    last_row = FIRST_DATA_ROW + len(lines) - 1
    for col, width in enumerate((26, 8, 12, 14, 12), start=1):
        detail.column_dimensions[get_column_letter(col)].width = width

    # ── 設定シート（税率は別シート。難易度3の連鎖の起点）──
    config["A1"] = loc.s["xl_sheet_config"]
    config["A1"].font = Font(bold=True)
    config["A2"] = loc.s["xl_l_tax_rate"]
    config["B2"] = float(TAX_RATE)

    # ── サマリシート（すべて数式。値は入れない）────────────
    d = loc.s["xl_sheet_detail"]
    c = loc.s["xl_sheet_config"]
    approved_label = loc.statuses[0]
    rows = (
        (loc.s["xl_l_subtotal"], f"=SUM('{d}'!D{FIRST_DATA_ROW}:D{last_row})"),
        (
            loc.s["xl_l_approved"],
            f"=SUMIF('{d}'!E{FIRST_DATA_ROW}:E{last_row},\"{approved_label}\","
            f"'{d}'!D{FIRST_DATA_ROW}:D{last_row})",
        ),
        (loc.s["xl_l_tax"], f"=ROUND(B2*'{c}'!B2,0)"),
        (loc.s["xl_l_total"], "=B2+B4"),
    )
    summary["A1"] = loc.fmt("xl_title", project=project, code=code)
    summary["A1"].font = Font(bold=True, size=13)
    for offset, (label, formula) in enumerate(rows):
        r = 2 + offset
        summary.cell(row=r, column=1, value=label).font = Font(bold=True)
        summary.cell(row=r, column=2, value=formula)
    summary.column_dimensions["A"].width = 20
    summary.column_dimensions["B"].width = 18

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# サマリシートの行と、そこに入る値のキー
_SUMMARY_CELLS = (("B2", "subtotal"), ("B3", "approved"), ("B4", "tax"), ("B5", "total"))


def _build(
    rng: random.Random,
    outdir: Path,
    loc: Locale,
    code: str,
    rows: tuple[int, int],
    stale: bool,
) -> tuple[dict[str, int], dict[str, int] | None, str]:
    """1 ファイルを生成して (正解の集計, 陳腐化した集計 or None, 相対パス) を返す。"""
    project = rng.choice(loc.project_names)
    lines = _make_lines(rng, loc, rows)
    revision = rng.randrange(2, 5) if stale else 1

    rel = f"{SUBDIR}/{code}_quotation.xlsx"
    path = outdir / rel
    _write_workbook(path, loc, code, project, lines, revision)

    totals = _compute(lines, loc.statuses[0])
    old_totals = None

    if stale:
        # 旧版の明細から計算した値をキャッシュとして注入する。
        # サマリ全体を旧版で揃えるので、シート内では辻褄が合って見える。
        old_totals = _compute(_previous_revision(rng, lines), loc.statuses[0])
        for cell_ref, key in _SUMMARY_CELLS:
            inject_cached_value(path, loc.s["xl_sheet_summary"], cell_ref, old_totals[key])

    normalize_artifact(path)
    return totals, old_totals, rel


def _unit(loc: Locale) -> str:
    return "円" if loc.code == "ja" else ""


def generate(rng: random.Random, outdir: Path, n_questions: int, locale: Locale) -> list[Item]:
    """SPEC §3-3 の生成器契約（locale を追加したもの）。"""
    codes = [f"QT-{n:04d}" for n in rng.sample(range(1000, 5000), n_questions)]

    items: list[Item] = []
    for i, code in enumerate(codes):
        question_key, field, difficulty, rows, stale = QUESTION_SPECS[i % len(QUESTION_SPECS)]
        totals, old_totals, rel = _build(rng, outdir, locale, code, rows, stale)
        value = totals[field]

        # 囮 = 陳腐化したキャッシュ値。診断用でアームには渡さない。
        decoys = []
        if old_totals is not None and old_totals[field] != value:
            decoys.append(str(old_totals[field]))

        items.append(
            Item(
                qid=f"{CHANNEL}-{i + 1:02d}",
                channel=CHANNEL,
                question=locale.fmt(question_key, code=code),
                answer=str(value),
                answer_type="number",
                answer_aliases=number_aliases(value, _unit(locale))[1:],
                source_files=[rel],
                decoys=decoys,
                difficulty=difficulty,
                locale=locale.code,
            )
        )
    return items


def generate_fillers(
    rng: random.Random, outdir: Path, count: int, locale: Locale
) -> list[str]:
    """設問を持たない見積書を足す（ディストラクタ）。

    規模も陳腐化の有無も設問つきファイルと同じ分布にする。形式で当てられると
    検索の評価にならないため。
    """
    written: list[str] = []
    # 設問用コード（1000-4999）と番号帯を分けているので衝突しない
    for n in rng.sample(range(5000, 9999), count):
        _, _, _, rows, stale = QUESTION_SPECS[rng.randrange(len(QUESTION_SPECS))]
        _, _, rel = _build(rng, outdir, locale, f"QT-{n:04d}", rows, stale)
        written.append(rel)
    return written
