"""Arm A `classical` — chunk + embed + BM25 + top-k。

``ClassicalArm`` は遅延 import する。``arm.py`` は sentence-transformers など
``arms`` 依存グループを引くため、ここで即時 import すると
``arms.classical.extract`` を読むだけの用途（CI のテストなど）でも重い依存が
必要になってしまう。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arms.classical.arm import ClassicalArm

__all__ = ["ClassicalArm"]


def __getattr__(name: str):
    if name == "ClassicalArm":
        from arms.classical.arm import ClassicalArm

        return ClassicalArm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
