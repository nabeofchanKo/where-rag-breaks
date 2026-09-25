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

from gen.channels import formula, text

# 実装済みのチャネル。SPEC §8 のフェーズが進むごとにここへ足していく。
#   P0: text, formula
#   P1: format, chart_only, chart_native, scanned, layout, version,
#       cross_file, hidden, locked
REGISTRY: dict[str, ModuleType] = {
    "text": text,
    "formula": formula,
}

ALL_CHANNELS = tuple(sorted(REGISTRY))
