"""情報チャネルの登録所。

1 チャネル = 1 モジュール = 1 生成器（SPEC §3-1）。
各モジュールは次の 2 つを公開する:

    generate(rng, outdir, n_questions, locale) -> list[Item]
        設問つきのファイル群を生成し、Item を返す。

    generate_fillers(rng, outdir, count, locale) -> list[str]
        設問を持たないディストラクタを生成し、相対パスを返す。
        設問つきファイルと見分けがつかない形式であること。

SPEC §3-3 の元の契約は ``generate(rng, outdir, n_questions)`` だが、
SPEC §10 がコーパスの言語切り替えを要求しているため ``locale`` を足している。
"""

from __future__ import annotations

from types import ModuleType

from gen.channels import (
    chart_native,
    chart_only,
    cross_file,
    format,
    formula,
    hidden,
    layout,
    locked,
    scanned,
    text,
    version,
)

# 実装済みのチャネル。SPEC §8 のフェーズが進むごとにここへ足していく。
#   P0: text, formula
#   P1: 残り9チャネル ← 実装済み（SPEC §3-1 の11チャネルすべてが揃った）
REGISTRY: dict[str, ModuleType] = {
    "text": text,
    "format": format,
    "formula": formula,
    "chart_only": chart_only,
    "chart_native": chart_native,
    "scanned": scanned,
    "layout": layout,
    "version": version,
    "cross_file": cross_file,
    "hidden": hidden,
    "locked": locked,
}

ALL_CHANNELS = tuple(sorted(REGISTRY))
