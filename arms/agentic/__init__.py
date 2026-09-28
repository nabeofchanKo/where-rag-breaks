"""Arm B `agentic` — カタログ + 道具でモデル自身が探す。

``ClassicalArm`` と同じ理由で遅延 import する（重い依存を引くため）。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arms.agentic.arm import AgenticArm

__all__ = ["AgenticArm"]


def __getattr__(name: str):
    if name == "AgenticArm":
        from arms.agentic.arm import AgenticArm

        return AgenticArm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
