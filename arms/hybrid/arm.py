"""Arm C `hybrid` — Arm A でファイル候補を絞ってから Arm B（SPEC §4-2）。

    ベクトル検索でファイルを N 件に選ぶ → その範囲だけをエージェントに渡す

**H3**（SPEC §2）の検証対象:
    「コーパスが大きくなるほど agentic 単体より有利になる。破綻点が存在する」

    Arm B はコーパス全体を相手にするので、ファイル数が増えるほど探索に
    往復とコストがかかる。Arm C は検索で先に絞るぶん、その増加が抑えられる
    ——というのが仮説。**この run の規模（311ファイル）では差が出ない可能性が
    高い。** H3 は P4 のスケーリング測定（50 / 500 / 5,000）で判定する。

★ **絞り込みは「チャンク」ではなく「ファイル」単位で行う**
    Arm A は top-k チャンクを LLM に渡すが、Arm C が渡すのはチャンクではなく
    **ファイルへのアクセス権**である。エージェントは渡されたファイルを
    原本ごと開けるので、Arm A が落とすもの（塗り色・画像・ノート）にも届く。
    絞り込みが効きすぎて正解のファイルが外れたら、そこで詰む——それが
    このアームの固有のリスクであり、測りたいところでもある。

★ **絞ったらカタログもミラーも連動して絞る**
    候補を N 件にしてもカタログに全ファイルが並んでいたら、エージェントは
    そこから好きなものを選べてしまい「絞ってから渡す」設計が成立しない。
    ``ToolContext.allowed`` を通じて ``list_files`` / ``read_file`` /
    ``grep`` / ``run_python`` のすべてが同じ範囲に閉じる。
"""

from __future__ import annotations

from pathlib import Path

from arms.agentic.arm import AgenticArm
from arms.base import AnswerMode, ArmAnswer
from arms.classical.arm import ClassicalArm

# 候補として渡すファイル数。cross_file は 1 問で 11 ファイルを要するので、
# それを下回ると構造的に解けなくなる。既定はそこに余裕を持たせた値。
DEFAULT_N_FILES = 20
# ファイルを N 件集めるために、チャンクは多めに引く
CHUNK_POOL_MULTIPLIER = 6


class HybridArm:
    """SPEC §4-2 の Arm C。"""

    name = "hybrid"
    sweeps_k = True  # 絞り込み件数 N を k として掃く
    uses_tools = True  # 絞った範囲でエージェントが動く

    def __init__(
        self,
        k: int = DEFAULT_N_FILES,
        model: str | None = None,
        max_turns: int | None = None,
    ) -> None:
        self.k = k
        self.classical = ClassicalArm(k=k, model=model)
        self.agentic = AgenticArm(model=model, **({"max_turns": max_turns} if max_turns else {}))
        self.model = self.agentic.model

    def prepare(self, corpus: Path, locale: str) -> None:
        # 両方の索引が要る（ベクトル検索用のチャンクと、エージェント用のカタログ）
        self.classical.prepare(corpus, locale)
        self.agentic.prepare(corpus, locale)

    def reindex_for_k(self, k: int) -> None:
        self.k = k
        self.classical.reindex_for_k(k)

    @property
    def index_stats(self) -> dict:
        return {
            "retrieval": self.classical.index_stats,
            "agent": self.agentic.index_stats,
            "n_candidate_files": self.k,
            "narrowing": "file-level (not chunk-level)",
        }

    def _candidate_files(self, question: str) -> list[str]:
        """ベクトル検索で候補ファイルを N 件選び、付随ファイルを足す。

        チャンク単位のスコア順に、**ファイル名の重複を除きながら**上から N 件。
        同じファイルの複数チャンクが上位を占めても候補数を食い潰さない。

        ★ **付随ファイルを足す理由（ここを省くと Arm C が不当に弱くなる）**

        PNG・画像だけの PDF・暗号化 zip は**チャンクを 1 つも生まない**ので、
        チャンク検索では永久に候補に入らない。素朴に実装すると、Arm C は
        グラフ画像も座席図も暗号化ファイルも**触れることすらできない**。
        それは hybrid という方式の性質ではなく、絞り込みの手抜きである
        （SPEC §4-1 の steel-man 原則は Arm C にも及ぶ）。

        そこで、選ばれたファイルと**同じディレクトリまたはその配下**にある
        索引不能ファイルを候補に加える。実際の文書管理でも、資料本体と
        その図版は同じ場所に置かれる。

        ★ **それでも届かないものは残る。** 選ばれたファイルが 1 つも無い
        ディレクトリの索引不能ファイル（例: 添え状の無いスキャンPDF）は
        候補に入らない。これは手抜きではなく、
        **テキスト検索で絞るという方式そのものの限界**であり、
        測定結果として報告すべきもの。
        """
        index = self.classical._require_index()  # noqa: SLF001 — 同じパッケージ内の協調
        hits = index.search(question, self.k * CHUNK_POOL_MULTIPLIER)

        ordered: list[str] = []
        for hit in hits:
            if hit.chunk.path not in ordered:
                ordered.append(hit.chunk.path)
            if len(ordered) >= self.k:
                break

        return ordered + self._companions(ordered)

    def _companions(self, selected: list[str]) -> list[str]:
        """選ばれたファイルの近くにある、索引不能なファイル。"""
        from pathlib import PurePosixPath

        indexable = {c.path for c in self.classical._require_index().chunks}  # noqa: SLF001
        roots = {PurePosixPath(path).parent for path in selected}

        files_dir = self.agentic._require_corpus() / "files"  # noqa: SLF001
        found: list[str] = []
        for path in sorted(files_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(files_dir).as_posix()
            if rel in indexable or rel in selected:
                continue
            parent = PurePosixPath(rel).parent
            if any(parent == root or root in parent.parents for root in roots):
                found.append(rel)
                if len(found) >= self.k * 2:  # 候補が膨らみすぎないように頭打ち
                    break
        return found

    def answer(self, question: str, mode: AnswerMode) -> ArmAnswer:
        candidates = self._candidate_files(question)

        # ★ 絞った範囲をエージェントに渡す。カタログもミラーも連動して絞られる。
        self.agentic.allowed_files = set(candidates)
        try:
            out = self.agentic.answer(question, mode)
        finally:
            self.agentic.allowed_files = None

        out.k = self.k
        # 診断用。候補に正解のファイルが入っていたかを後から確かめられる。
        out.retrieved = candidates
        return out
