"""Arm A のチャンク分割。

SPEC §4-1: 「妥当なチャンク戦略（構造を見た分割、サイズと overlap は
パラメータ化）」。

方針:
    構造（docx の見出し / xlsx のシート）を第一の境界にする。固定長で機械的に
    切ると、見出しと本文、あるいは表のヘッダ行とデータ行が別チャンクに落ちる。
    それは古典的RAGの「構造的な限界」ではなく単なる実装の粗さなので、
    steel-man の観点から採用しない。

    構造単位が大きすぎる場合だけ、行境界を優先した固定長分割に落とす。
    その際も**先頭行（ヘッダ）を各断片に複製する**。表のヘッダを失わせるのは
    抽出器の穴に当たる。
"""

from __future__ import annotations

from dataclasses import dataclass

from arms.classical.extract import Block

DEFAULT_CHUNK_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 200


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    path: str
    locator: str
    text: str

    def render(self) -> str:
        """プロンプトに載せる形。出所を必ず付ける（evidence を書けるように）。"""
        return f"[{self.path} :: {self.locator}]\n{self.text}"


def _split_lines(
    text: str, chunk_chars: int, overlap_chars: int, repeat_header: bool
) -> list[str]:
    """行境界を優先して分割する。行の途中では切らない。"""
    lines = text.split("\n")
    header = lines[0] if (repeat_header and len(lines) > 1) else None

    pieces: list[str] = []
    current: list[str] = []
    size = 0

    for line in lines:
        # 1 行だけで上限を超える場合は、その行を単独の断片にする
        if size and size + len(line) + 1 > chunk_chars:
            pieces.append("\n".join(current))
            # overlap ぶんだけ末尾の行を持ち越す
            carried: list[str] = []
            carried_size = 0
            for prev in reversed(current):
                if carried_size + len(prev) + 1 > overlap_chars:
                    break
                carried.insert(0, prev)
                carried_size += len(prev) + 1
            current = carried
            size = carried_size
            if header is not None and (not current or current[0] != header):
                current.insert(0, header)
                size += len(header) + 1
        current.append(line)
        size += len(line) + 1

    if current:
        pieces.append("\n".join(current))
    return [p for p in pieces if p.strip()]


def chunk_blocks(
    blocks: list[Block],
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    """構造単位を第一境界としてチャンクに分ける。"""
    chunks: list[Chunk] = []
    for index, block in enumerate(blocks):
        # xlsx のシートは1行目がヘッダ行相当なので、分割時に複製する
        repeat_header = block.locator.startswith(("シート", "Sheet"))
        pieces = (
            [block.text]
            if len(block.text) <= chunk_chars
            else _split_lines(block.text, chunk_chars, overlap_chars, repeat_header)
        )
        for part, piece in enumerate(pieces):
            locator = block.locator if len(pieces) == 1 else f"{block.locator} ({part + 1})"
            chunks.append(
                Chunk(
                    chunk_id=f"{index:05d}-{part:03d}",
                    path=block.path,
                    locator=locator,
                    text=piece,
                )
            )
    return chunks
