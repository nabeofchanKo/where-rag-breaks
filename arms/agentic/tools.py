"""Arm B / C に渡す道具（SPEC §4-2）。

    list_files / read_file / grep / run_python / view_image

★ **CLI 組込みのツールではなく自前で定義する理由**

Claude CLI の Read / Grep / Bash をそのまま使えば実装は要らない。しかしそれでは
測定結果が**CLI のバージョンごとの組込みツールの仕様**に左右される。
このベンチマークは他人の環境で再現できることが前提なので、道具の側は
リポジトリの中で固定する。SPEC §4-2 が挙げる 5 つに限定するのも同じ理由。

★ **すべてコーパスの中に閉じる**

パスは必ずコーパス直下に解決し、外へ出るものは拒否する。エージェントに
任意のファイルを読ませてしまうと、答えを別の場所から拾える可能性が残り、
測定として成立しない。``run_python`` も同じディレクトリに閉じる。
"""

from __future__ import annotations

import base64
import re
import subprocess
import sys
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

SERVER_NAME = "wrb"

# run_python の実行上限。無限ループでベンチマークを止めないため。
PYTHON_TIMEOUT_S = 60
# 1 回の read_file / grep で返す最大文字数。文脈を食い潰さないため。
MAX_CHARS = 20_000
MAX_GREP_HITS = 60

# view_image が扱う拡張子
_IMAGE_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class ToolContext:
    """道具が触れてよい範囲。アームごとに 1 つ作る。

    ``allowed`` を渡すと、その相対パスの集合だけに絞る（Arm C 用）。
    None なら corpus 配下すべて。
    """

    def __init__(self, corpus: Path, allowed: set[str] | None = None) -> None:
        self.corpus = corpus.resolve()
        self.files = self.corpus / "files"
        self.index = self.corpus / "_index"
        self.allowed = allowed
        self.calls: list[str] = []
        self.files_opened: list[str] = []

    # ── パス解決 ────────────────────────────────────────────
    def resolve(self, raw: str) -> Path:
        """コーパス内の実パスに解決する。外に出るパスは弾く。"""
        candidate = (self.corpus / raw.lstrip("/\\")).resolve()
        if not candidate.is_relative_to(self.corpus):
            raise PermissionError(f"コーパスの外は参照できない: {raw}")

        if self.allowed is not None:
            rel = self._relative_to_files(candidate)
            if rel is not None and rel not in self.allowed:
                raise PermissionError(f"このアームに割り当てられていないファイル: {rel}")
        return candidate

    def _relative_to_files(self, path: Path) -> str | None:
        try:
            return path.relative_to(self.files).as_posix()
        except ValueError:
            return None

    def note_open(self, path: Path) -> None:
        """開いたファイルを記録する（SPEC §5-3 の files_opened）。

        原本（``files/…``）もミラー（``_index/mirror/…``）も両方記録する。
        「原本に到達したのか、ミラーで済ませたのか」は Arm B の挙動を読む
        うえで重要な区別なので、パスの形でそのまま残す。

        ★ **``run_python`` の中で開いたファイルはここに載らない。**
        任意のコードなので追跡できない。``files_opened`` は
        ``read_file`` と ``view_image`` の記録であって、
        「エージェントが触れた全ファイル」ではない。結果を読むときは
        ``tool_names`` に ``run_python`` が並んでいるかも併せて見ること。
        """
        self.files_opened.append(path.relative_to(self.corpus).as_posix())

    def visible_files(self) -> list[Path]:
        paths = [p for p in sorted(self.files.rglob("*")) if p.is_file()]
        if self.allowed is None:
            return paths
        return [p for p in paths if self._relative_to_files(p) in self.allowed]


def _text(body: str) -> dict:
    return {"content": [{"type": "text", "text": body}]}


def _clip(body: str) -> str:
    if len(body) <= MAX_CHARS:
        return body
    return body[:MAX_CHARS] + f"\n…（{len(body) - MAX_CHARS} 文字を省略）"


def build_server(ctx: ToolContext):
    """``ToolContext`` に束縛した MCP サーバを作る。"""

    @tool(
        "list_files",
        "コーパス内のファイルを列挙する。glob パターンで絞り込める（例: 'quotes/*.xlsx'）。",
        {"pattern": str},
    )
    async def list_files(args: dict) -> dict:
        ctx.calls.append("list_files")
        pattern = (args.get("pattern") or "**/*").strip() or "**/*"
        matched = [
            p for p in ctx.visible_files()
            if p.relative_to(ctx.files).match(pattern) or pattern == "**/*"
        ]
        lines = [
            f"{p.relative_to(ctx.files).as_posix()}  ({p.stat().st_size:,} bytes)"
            for p in matched
        ]
        head = f"{len(lines)} 件"
        return _text(_clip(head + "\n" + "\n".join(lines[:500])))

    @tool(
        "read_file",
        "テキストファイル（カタログ、Markdown ミラーなど）を読む。"
        "バイナリ原本は read_file では読めないので run_python か view_image を使うこと。",
        {"path": str},
    )
    async def read_file(args: dict) -> dict:
        ctx.calls.append("read_file")
        try:
            path = ctx.resolve(args["path"])
        except PermissionError as exc:
            return _text(f"エラー: {exc}")
        if not path.is_file():
            return _text(f"エラー: ファイルが無い: {args['path']}")
        ctx.note_open(path)
        try:
            return _text(_clip(path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            return _text(
                f"エラー: {args['path']} はテキストとして読めない（バイナリ）。"
                "run_python で開くか、画像なら view_image を使うこと。"
            )

    @tool(
        "grep",
        "コーパス内のテキスト（カタログと Markdown ミラー）を正規表現で検索する。",
        {"pattern": str, "path_glob": str},
    )
    async def grep(args: dict) -> dict:
        ctx.calls.append("grep")
        try:
            regex = re.compile(args["pattern"])
        except re.error as exc:
            return _text(f"エラー: 正規表現が不正: {exc}")

        glob = (args.get("path_glob") or "**/*.md").strip() or "**/*.md"
        roots = [ctx.index] if ctx.index.is_dir() else []
        hits: list[str] = []
        for root in roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or not path.match(glob):
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                rel = path.relative_to(ctx.corpus).as_posix()
                for number, line in enumerate(content.split("\n"), start=1):
                    if regex.search(line):
                        hits.append(f"{rel}:{number}: {line.strip()[:200]}")
                        if len(hits) >= MAX_GREP_HITS:
                            break
                if len(hits) >= MAX_GREP_HITS:
                    break
        if not hits:
            return _text("一致なし")
        return _text(_clip(f"{len(hits)} 件\n" + "\n".join(hits)))

    @tool(
        "run_python",
        "Python を実行する。作業ディレクトリはコーパス直下で、原本は files/ 以下にある。"
        "openpyxl / python-docx / python-pptx / pymupdf / pyzipper / PIL が使える。"
        "結果は print で出力すること。",
        {"code": str},
    )
    async def run_python(args: dict) -> dict:
        ctx.calls.append("run_python")
        code = args.get("code") or ""
        try:
            proc = subprocess.run(  # noqa: S603 — 実行するのはモデルが書いたコードのみ
                [sys.executable, "-c", code],
                cwd=ctx.corpus,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PYTHON_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return _text(f"エラー: {PYTHON_TIMEOUT_S} 秒で打ち切った")
        out = proc.stdout or ""
        err = proc.stderr or ""
        body = out if not err else f"{out}\n--- stderr ---\n{err}"
        return _text(_clip(body.strip() or "（出力なし）"))

    @tool(
        "view_image",
        "画像ファイル（png / jpg）を実際に見る。グラフや配置図の中身はこれでしか読めない。",
        {"path": str},
    )
    async def view_image(args: dict) -> dict:
        ctx.calls.append("view_image")
        try:
            path = ctx.resolve(args["path"])
        except PermissionError as exc:
            return _text(f"エラー: {exc}")
        mime = _IMAGE_SUFFIXES.get(path.suffix.lower())
        if mime is None or not path.is_file():
            return _text(f"エラー: 画像として開けない: {args['path']}")
        ctx.note_open(path)
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"content": [{"type": "image", "data": data, "mimeType": mime}]}

    return create_sdk_mcp_server(
        name=SERVER_NAME,
        tools=[list_files, read_file, grep, run_python, view_image],
    )


# SDK MCP のツール名は "mcp__<サーバ名>__<ツール名>" になる
TOOL_NAMES = [
    f"mcp__{SERVER_NAME}__{name}"
    for name in ("list_files", "read_file", "grep", "run_python", "view_image")
]
