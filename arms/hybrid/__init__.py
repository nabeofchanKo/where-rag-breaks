"""Arm C `hybrid` — 検索でファイルを絞ってからエージェント。

他のアームと同じ理由で遅延 import する。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arms.hybrid.arm import HybridArm

__all__ = ["HybridArm"]


def __getattr__(name: str):
    if name == "HybridArm":
        from arms.hybrid.arm import HybridArm

        return HybridArm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
