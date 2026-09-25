"""全アーム共通の LLM 呼出（Claude Agent SDK）。

SPEC §4-2 は「アーム間でモデルを揃えること」を要求している。Arm A（ツール
なし1回呼出）も Arm B/C（ツールあり1 invoke）も**同じここを通す**ことで、
モデル・温度・リトライ回数のズレという交絡を構造的に防ぐ。

計測（SPEC §5-3）もここで一元化する: latency / input_tokens / output_tokens /
cost_usd / tool_calls / files_opened。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

DEFAULT_MODEL = "claude-sonnet-5"

# ファイルを開いたと見なすツール名（SPEC §5-3 の files_opened 用）
_FILE_TOOLS = {"Read", "Grep", "Glob", "NotebookRead"}


def bootstrap() -> None:
    """TLS 傍受環境での SSL 失敗を避ける（SPEC §10）。すべての入口で最初に呼ぶ。

    1. ``SSLKEYLOGFILE`` を外す。
       AVG などのアンチウイルスは、この環境変数を名前付きパイプ
       （``\\\\.\\avgMonFltProxy\\...``）に設定して TLS を傍受する。OpenSSL は
       この変数があると C ランタイムの FILE* API でそれを開こうとするが、
       Python 同梱の OpenSSL は OPENSSL_Applink を持たないため
       ``OPENSSL_Uplink(...): no OPENSSL_Applink`` で**プロセスごと即死**する。
       スタックトレースも出ないので原因が分かりにくい。実測で確認済み。

    2. OS の証明書ストアで検証する（truststore）。
       傍受環境では Python 同梱の CA バンドルに傍受用の証明書が無いため
       検証に失敗する。傍受のない環境でも害はない。

    3. 認証方式を確定させる（``WRB_AUTH``）。下の ``resolve_auth`` を参照。
    """
    os.environ.pop("SSLKEYLOGFILE", None)

    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 — truststore が無くても動作は続ける
        pass

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # noqa: BLE001
        pass

    resolve_auth()


def resolve_auth() -> str:
    """認証方式を決め、環境を**その方式だけが効く状態**にする。

    ``WRB_AUTH``:
        ``cli``（既定） … Claude CLI のログイン認証を使う。契約プランの利用枠を
            消費し、API の従量課金は発生しない。
        ``api``          … ``ANTHROPIC_API_KEY`` で API を叩く。従量課金になる。

    **なぜ明示的に切るのか**: ``.env`` に ``ANTHROPIC_API_KEY`` が置いてあると、
    CLI ログイン済みでも SDK はそちらを優先して API 課金に切り替わる。
    「CLI でログインしたから無料のはず」が静かに裏切られるので、cli モードでは
    キーを環境から**明示的に外す**。

    返り値は実際に有効になった方式。``meta.json`` に記録して、コストの数字が
    実請求なのか参考値なのかを後から判別できるようにする。
    """
    mode = os.environ.get("WRB_AUTH", "cli").strip().lower()
    if mode == "api":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("WRB_AUTH=api だが ANTHROPIC_API_KEY が設定されていない")
        return "api"

    os.environ.pop("ANTHROPIC_API_KEY", None)
    return "cli"


def resolve_model() -> str:
    return os.environ.get("WRB_MODEL", DEFAULT_MODEL)


@dataclass
class LLMResult:
    """1 回の LLM 呼出の結果と計測値。"""

    text: str
    latency_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: int = 0
    files_opened: list[str] = field(default_factory=list)
    num_turns: int = 0  # 「1 invoke」が本当に 1 往復で終わったかの検証用
    model: str = ""
    is_error: bool = False
    error: str = ""


def _usage_tokens(usage: dict | None) -> tuple[int, int]:
    if not usage:
        return 0, 0
    read = int(usage.get("input_tokens", 0) or 0)
    # キャッシュ読み書きも入力として課金対象なので合算する
    read += int(usage.get("cache_read_input_tokens", 0) or 0)
    read += int(usage.get("cache_creation_input_tokens", 0) or 0)
    return read, int(usage.get("output_tokens", 0) or 0)


def _extract_opened_files(block: ToolUseBlock) -> list[str]:
    raw = block.input or {}
    out = []
    for key in ("file_path", "path", "notebook_path"):
        value = raw.get(key)
        if isinstance(value, str):
            out.append(value)
    return out


async def _run(
    prompt: str,
    *,
    system_prompt: str,
    model: str,
    allowed_tools: list[str],
    cwd: Path | None,
    max_turns: int,
) -> LLMResult:
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        allowed_tools=allowed_tools,
        tools=allowed_tools or [],
        permission_mode="bypassPermissions" if allowed_tools else "default",
        cwd=str(cwd) if cwd else None,
        # ユーザーの CLAUDE.md や設定が混ざると再現性が壊れるため読み込まない
        setting_sources=None,
        skills=None,
    )

    text_parts: list[str] = []
    num_turns = 0
    tool_calls = 0
    files_opened: list[str] = []
    in_tok = out_tok = 0
    cost = 0.0
    is_error = False
    error = ""

    started = time.perf_counter()
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_calls += 1
                    if block.name in _FILE_TOOLS:
                        files_opened.extend(_extract_opened_files(block))
        elif isinstance(message, ResultMessage):
            num_turns = int(message.num_turns or 0)
            in_tok, out_tok = _usage_tokens(message.usage)
            cost = float(message.total_cost_usd or 0.0)
            is_error = bool(message.is_error)
            if is_error:
                error = str(message.result or message.errors or "unknown error")
            if not text_parts and message.result:
                text_parts.append(str(message.result))
    latency = time.perf_counter() - started

    return LLMResult(
        text="\n".join(text_parts).strip(),
        latency_s=latency,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=cost,
        tool_calls=tool_calls,
        files_opened=sorted(set(files_opened)),
        num_turns=num_turns,
        model=model,
        is_error=is_error,
        error=error,
    )


def complete(
    prompt: str,
    *,
    system_prompt: str,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    cwd: Path | None = None,
    max_turns: int = 2,
) -> LLMResult:
    """LLM を 1 invoke 呼ぶ（同期 API）。

    ``allowed_tools`` が空なら Arm A 相当（ツールなし1回）、
    ツールを渡せば Arm B/C 相当（内部で複数ツール呼出）になる。

    ``max_turns`` の既定が 2 なのは SDK の都合。1 にすると、モデルが 1 往復で
    正常に答え切った場合でも「Reached maximum number of turns (1)」でエラーに
    なる。ツールを渡していない呼出はそもそも追加の往復ができないので、
    2 にしても Arm A が「LLM 呼出 1 回」である性質は変わらない。
    実際の往復回数は ``LLMResult.num_turns`` に記録されるので、
    1 で終わっていることは結果から検証できる。
    """
    return asyncio.run(
        _run(
            prompt,
            system_prompt=system_prompt,
            model=model or resolve_model(),
            allowed_tools=allowed_tools or [],
            cwd=cwd,
            max_turns=max_turns,
        )
    )


# ── 出力の JSON パース ────────────────────────────────────────────
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_answer(text: str) -> dict:
    """モデル出力から回答 JSON を取り出す。

    取り出せなかった場合も**例外にしない**。「JSON を返せなかった」こと自体が
    そのアームの性能なので、棄権扱いにして記録する（SPEC §5-2 の answer_rate）。
    """
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidates.extend(fenced)
    match = _JSON_BLOCK.search(text)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return {"answer": "", "confidence": 0.0, "evidence": [], "abstained": True}
