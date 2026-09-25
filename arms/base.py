"""アームの共通インタフェースと出力契約（SPEC §4-2）。

**禁止事項をここで構造的に担保する（SPEC §11）**:
    ``answer()`` が受け取るのは設問文だけである。``Item`` を渡さない。
    したがってアームは qid もチャネル名も ``source_files`` も見られない。
    「設問ごとの特別扱い」は書きたくても書けない。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

# SPEC §4-2「棄権の扱い」:
#   Arm A は常に答える設計、Arm B は棄権できる設計になりがちで、これは交絡要因。
#   両モードで走らせて両方記録する。
AnswerMode = Literal["abstain_ok", "forced"]

ANSWER_CONTRACT = """\
必ず次の JSON だけを出力すること。前置きも後書きも書かない。

{"answer": "...", "confidence": 0.0-1.0, "evidence": ["path:locator", ...], "abstained": false}

- answer   … 短く答える。数値なら数値だけ、氏名なら氏名だけ。説明を混ぜない
- evidence … 根拠の所在。"ファイル名:シート名やセル番地や見出し" の形式
- abstained… 与えられた情報から確実に答えられない場合に true
"""

ANSWER_CONTRACT_EN = """\
Output only the following JSON. No preamble, no trailing commentary.

{"answer": "...", "confidence": 0.0-1.0, "evidence": ["path:locator", ...], "abstained": false}

- answer   ... answer briefly. A number alone if numeric, a name alone if a name
- evidence ... where the support came from, as "filename:sheet or cell or heading"
- abstained... true when the given material does not allow a confident answer
"""

FORCED_SUFFIX = """\
このモードでは棄権できない。確信が持てなくても必ず最も可能性の高い答えを
書き、abstained は false にすること。
"""

FORCED_SUFFIX_EN = """\
Abstaining is not permitted in this mode. Even when unsure, give the most
likely answer and set abstained to false.
"""


def contract_for(locale: str, mode: AnswerMode) -> str:
    """出力契約の文面。アーム間で共通にする（プロンプト差を交絡させない）。"""
    if locale == "en":
        contract, forced = ANSWER_CONTRACT_EN, FORCED_SUFFIX_EN
    else:
        contract, forced = ANSWER_CONTRACT, FORCED_SUFFIX
    return contract + ("\n" + forced if mode == "forced" else "")


@dataclass
class ArmAnswer:
    """1 設問に対するアームの出力と計測値（SPEC §4-2 出力契約 + §5-3）。"""

    answer: str
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    abstained: bool = False

    # 計測
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
    tool_names: list[str] = field(default_factory=list)
    tool_results: int = 0
    permission_denials: int = 0
    num_turns: int = 0
    files_opened: list[str] = field(default_factory=list)

    # 再現のためのパラメータ
    k: int | None = None
    model: str = ""
    retrieved: list[str] = field(default_factory=list)  # 診断用。採点には使わない
    error: str = ""

    @classmethod
    def from_payload(cls, payload: dict, **measured: object) -> ArmAnswer:
        answer = payload.get("answer")
        evidence = payload.get("evidence") or []
        return cls(
            answer="" if answer is None else str(answer).strip(),
            confidence=_as_float(payload.get("confidence")),
            evidence=[str(e) for e in evidence] if isinstance(evidence, list) else [],
            abstained=bool(payload.get("abstained", False)),
            **measured,  # type: ignore[arg-type]
        )


def _as_float(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


class Arm(Protocol):
    """全アームが満たすインタフェース。"""

    name: str

    def prepare(self, corpus: Path, locale: str) -> None:
        """索引を構築する。設問ごとではなく**コーパスごとに1回**呼ばれる。"""
        ...

    def answer(self, question: str, mode: AnswerMode) -> ArmAnswer:
        """設問に答える。受け取れるのは設問文とモードだけ。"""
        ...
