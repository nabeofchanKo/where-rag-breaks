"""Arm A `classical` — chunk + embed + BM25 + top-k → LLM 1 回。

SPEC §4-2。このアームがこのベンチマークの主役であり、**本気で作ること**が
結果の信頼性そのもの（SPEC §4-1）。ここでやっていること:

    - 構造を見たチャンク分割（``chunk.py``）
    - hybrid retrieval: BM25 + dense を RRF で融合（``retrieve.py``）
    - 抽出は実務で普通にやる範囲を丁寧に（``extract.py``）
    - k はパラメータ。``eval/run.py`` がスイープして**チャネルごとの最良 k**で評価する

やっていないこと（意図的、かつ結果に明記すべきこと）:
    - reranker を入れていない（SPEC §12-4 の既定どおり。P3 以降で検討）
"""

from __future__ import annotations

from pathlib import Path

from arms.base import AnswerMode, ArmAnswer, contract_for
from arms.classical.chunk import DEFAULT_CHUNK_CHARS, DEFAULT_OVERLAP_CHARS, chunk_blocks
from arms.classical.extract import extract_corpus
from arms.classical.retrieve import HybridIndex, embedding_model_name
from arms.llm import complete, parse_json_answer, resolve_model

SYSTEM_PROMPT_JA = """\
あなたは社内文書の検索結果から質問に答えるアシスタントである。

与えられた抜粋だけを根拠に答えること。抜粋に無いことを推測で補ってはならない。
抜粋が不足していて確実に答えられない場合は、その旨を出力形式に従って示すこと。
"""

SYSTEM_PROMPT_EN = """\
You answer questions from search results over internal documents.

Answer only from the excerpts provided. Do not fill gaps with guesses.
If the excerpts are insufficient to answer confidently, say so through the
required output format.
"""

USER_TEMPLATE_JA = """\
## 検索で得られた抜粋（{n} 件）

{context}

## 質問

{question}

## 出力形式

{contract}"""

USER_TEMPLATE_EN = """\
## Retrieved excerpts ({n})

{context}

## Question

{question}

## Output format

{contract}"""


class ClassicalArm:
    """SPEC §4-2 の Arm A。"""

    name = "classical"

    def __init__(
        self,
        k: int = 8,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
        model: str | None = None,
    ) -> None:
        self.k = k
        self.chunk_chars = chunk_chars
        self.overlap_chars = overlap_chars
        self.model = model or resolve_model()
        self.locale = "ja"
        self._index: HybridIndex | None = None

    # ── 索引構築（コーパスごとに1回）──────────────────────────
    def prepare(self, corpus: Path, locale: str) -> None:
        self.locale = locale
        blocks = extract_corpus(corpus / "files")
        chunks = chunk_blocks(blocks, self.chunk_chars, self.overlap_chars)
        if not chunks:
            raise RuntimeError(f"チャンクが 0 件。抽出に失敗している: {corpus}")
        self._index = HybridIndex(chunks, locale)

    def reindex_for_k(self, k: int) -> None:
        """k スイープ用。索引は使い回し、取得件数だけ変える。"""
        self.k = k

    @property
    def index_stats(self) -> dict:
        index = self._require_index()
        return {
            "n_chunks": len(index.chunks),
            "chunk_chars": self.chunk_chars,
            "overlap_chars": self.overlap_chars,
            "embedding_model": embedding_model_name(),
            "retrieval": "bm25 + dense (RRF)",
            "reranker": None,
        }

    # ── 回答 ──────────────────────────────────────────────────
    def answer(self, question: str, mode: AnswerMode) -> ArmAnswer:
        index = self._require_index()
        hits = index.search(question, self.k)

        context = "\n\n".join(f"### 抜粋 {i + 1}\n{h.chunk.render()}" for i, h in enumerate(hits))
        template = USER_TEMPLATE_EN if self.locale == "en" else USER_TEMPLATE_JA
        system = SYSTEM_PROMPT_EN if self.locale == "en" else SYSTEM_PROMPT_JA

        prompt = template.format(
            n=len(hits),
            context=context,
            question=question,
            contract=contract_for(self.locale, mode),
        )

        result = complete(prompt, system_prompt=system, model=self.model, allowed_tools=[])
        payload = parse_json_answer(result.text)

        return ArmAnswer.from_payload(
            payload,
            latency_s=result.latency_s,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            tool_calls=result.tool_calls,
            tool_names=result.tool_names,
            tool_results=result.tool_results,
            permission_denials=result.permission_denials,
            num_turns=result.num_turns,
            files_opened=[],  # Arm A はファイルを開かない。これが定義そのもの
            k=self.k,
            model=result.model,
            retrieved=[f"{h.chunk.path}::{h.chunk.locator}" for h in hits],
            error=result.error,
        )

    def _require_index(self) -> HybridIndex:
        if self._index is None:
            raise RuntimeError("prepare() を先に呼ぶこと")
        return self._index
