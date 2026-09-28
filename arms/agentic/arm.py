"""Arm B `agentic` — カタログを読んで自分で探す（SPEC §4-2）。

索引はカタログ（1ファイル1行）+ Markdown ミラー。検索はモデル自身が
``list_files`` / ``read_file`` / ``grep`` / ``run_python`` / ``view_image``
で行う。**LLM 呼出は 1 invoke**で、その内部で複数回ツールを呼ぶ。

★ **Arm A との公平性**
    - 同じモデル・同じ設問文（SPEC §4-2「アーム間でモデルを揃えること」）
    - 出力契約も棄権モードも共通（``arms/base.py``）
    - ミラーは **Arm A とまったく同じ抽出器**で作る。前処理で優遇しない
      （``ingest/build.py`` の冒頭を参照）
    - 道具はコーパスの中に閉じる

    したがって Arm B の優位が出るなら、それは**エージェントが自力で
    原本に到達したから**であって、索引が良かったからではない。
"""

from __future__ import annotations

from pathlib import Path

from arms.agentic.tools import TOOL_NAMES, ToolContext, build_server
from arms.base import AnswerMode, ArmAnswer, contract_for
from arms.llm import complete, parse_json_answer, resolve_model

# 1 invoke の中で許すツール往復の上限。青天井にすると 1 問に数十分かかる。
DEFAULT_MAX_TURNS = 40

SYSTEM_PROMPT_JA = """\
あなたは社内文書の集まりから質問に答える調査担当である。

道具を使って自分で探すこと。使える道具:
  list_files   ファイルを列挙する
  read_file    テキスト（カタログ、Markdown ミラー）を読む
  grep         ミラーを正規表現で検索する
  run_python   Python を実行する。原本（xlsx / docx / pptx / pdf / zip）を
               直接開ける。openpyxl / python-docx / python-pptx / pymupdf /
               pyzipper / PIL が使える
  view_image   画像（png / jpg）を実際に見る

進め方の目安:
  1. カタログ（_index/catalog.md）で当たりをつける
  2. ミラー（_index/mirror/…）を grep / read_file で読む
  3. **ミラーに無いものは原本にしかない。** 書式・グラフ画像・発表者ノート・
     暗号化ファイルの中身などは、run_python や view_image で取りに行くこと
  4. 数が多くて数えきれない場合も、run_python で全部開いて集計すればよい

分からないことは推測で埋めず、道具で確かめること。
"""

SYSTEM_PROMPT_EN = """\
You are an analyst answering questions from a collection of internal documents.

Find things yourself with the tools. Available tools:
  list_files   list files
  read_file    read text (the catalog, the markdown mirror)
  grep         search the mirror with a regular expression
  run_python   run Python. It can open the originals (xlsx / docx / pptx / pdf /
               zip) directly; openpyxl, python-docx, python-pptx, pymupdf,
               pyzipper and PIL are available
  view_image   actually look at an image (png / jpg)

Suggested approach:
  1. Get oriented with the catalog (_index/catalog.md)
  2. Read the mirror (_index/mirror/...) with grep / read_file
  3. **Anything missing from the mirror exists only in the original.**
     Formatting, chart images, presenter notes, the contents of encrypted
     files: go and get them with run_python or view_image
  4. When there is too much to count by hand, open everything with run_python
     and aggregate

Do not fill gaps with guesses; check with the tools.
"""

USER_TEMPLATE_JA = """\
## 調査対象

コーパスの場所: 作業ディレクトリ直下
  `files/`            原本
  `_index/catalog.md` 全ファイルの一覧
  `_index/mirror/`    テキスト抽出できたファイルの Markdown

## 質問

{question}

## 出力形式

道具での調査を終えたら、最後に次の形式だけを出力すること。

{contract}"""

USER_TEMPLATE_EN = """\
## What you are searching

The corpus sits in the working directory:
  `files/`            the originals
  `_index/catalog.md` a list of every file
  `_index/mirror/`    markdown for files whose text could be extracted

## Question

{question}

## Output format

When you have finished investigating, output only the following.

{contract}"""


class AgenticArm:
    """SPEC §4-2 の Arm B。"""

    name = "agentic"
    sweeps_k = False  # 検索はモデルが行うので top-k が無い

    def __init__(self, model: str | None = None, max_turns: int = DEFAULT_MAX_TURNS) -> None:
        self.model = model or resolve_model()
        self.max_turns = max_turns
        self.locale = "ja"
        self.corpus: Path | None = None
        # Arm C（hybrid）が設問ごとに候補を絞るためのフック
        self.allowed_files: set[str] | None = None

    def prepare(self, corpus: Path, locale: str) -> None:
        from ingest.build import build

        self.corpus = corpus.resolve()
        self.locale = locale
        index = self.corpus / "_index"
        if not (index / "catalog.md").is_file():
            build(self.corpus, index)

    def reindex_for_k(self, k: int) -> None:
        """Arm A と同じ呼び出し口を持たせるためのダミー。Arm B に k は無い。"""

    @property
    def index_stats(self) -> dict:
        corpus = self._require_corpus()
        mirror = corpus / "_index" / "mirror"
        return {
            "index": "catalog + markdown mirror",
            "n_files": sum(1 for p in (corpus / "files").rglob("*") if p.is_file()),
            "n_mirrored": sum(1 for p in mirror.rglob("*.md")) if mirror.is_dir() else 0,
            "tools": TOOL_NAMES,
            "max_turns": self.max_turns,
            # ミラーは Arm A と同一の抽出器で作る（前処理で優遇しない）
            "mirror_extractor": "arms.classical.extract",
        }

    def answer(self, question: str, mode: AnswerMode) -> ArmAnswer:
        corpus = self._require_corpus()
        ctx = ToolContext(corpus, allowed=self.allowed_files)
        server = build_server(ctx)

        template = USER_TEMPLATE_EN if self.locale == "en" else USER_TEMPLATE_JA
        system = SYSTEM_PROMPT_EN if self.locale == "en" else SYSTEM_PROMPT_JA
        prompt = template.format(question=question, contract=contract_for(self.locale, mode))

        result = complete(
            prompt,
            system_prompt=system,
            model=self.model,
            allowed_tools=TOOL_NAMES,
            cwd=corpus,
            max_turns=self.max_turns,
            mcp_servers={"wrb": server},
        )
        payload = parse_json_answer(result.text)

        return ArmAnswer.from_payload(
            payload,
            latency_s=result.latency_s,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            tool_calls=result.tool_calls,
            tool_names=ctx.calls,
            tool_results=result.tool_results,
            permission_denials=result.permission_denials,
            num_turns=result.num_turns,
            files_opened=sorted(set(ctx.files_opened)),
            k=None,
            model=result.model,
            error=result.error,
        )

    def _require_corpus(self) -> Path:
        if self.corpus is None:
            raise RuntimeError("prepare() を先に呼ぶこと")
        return self.corpus
