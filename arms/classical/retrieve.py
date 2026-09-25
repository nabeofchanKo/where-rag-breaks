"""Arm A の検索 — BM25（疎） + 密ベクトルの hybrid retrieval。

SPEC §4-1 は dense 単体を明確に禁じている。手を抜いた baseline を叩いても
誰も納得しないため、疎と密を RRF（Reciprocal Rank Fusion）で融合する。

日本語の扱い:
    BM25 は空白区切りを前提にしているので、日本語をそのまま渡すと 1 文が
    1 トークンになり検索が完全に死ぬ。それは「古典的RAGの限界」ではなく
    ただの実装ミスなので、janome で形態素解析してから渡す。

埋め込み:
    既定はローカルの BGE-m3。API キー不要・課金なし・完全に再現可能。
    ``WRB_EMBEDDING_MODEL`` で差し替えられる。使ったモデル名は必ず結果の
    meta.json に記録する（SPEC §12-3: 変えるなら結果に明記）。
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from arms.classical.chunk import Chunk

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
RRF_K0 = 60  # RRF の平滑化定数。慣例値
CACHE_DIR = Path(".cache") / "embeddings"

_WORD = re.compile(r"[0-9A-Za-z_]+")


def embedding_model_name() -> str:
    return os.environ.get("WRB_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


# ── トークナイズ ────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _janome_tokenizer():
    from janome.tokenizer import Tokenizer

    return Tokenizer()


def tokenize(text: str, locale: str) -> list[str]:
    """BM25 用のトークン列。

    日本語は形態素に割る。英数字は言語によらず 1 トークンとして拾う
    （"PRJ-1234" のような案件コードが検索の鍵になるため、ここは落とせない）。
    """
    codes = [m.group(0).lower() for m in _WORD.finditer(text)]
    if locale == "en":
        return codes

    morphemes = [
        token.surface.lower()
        for token in _janome_tokenizer().tokenize(text)
        if token.surface.strip()
    ]
    return morphemes + codes


# ── 埋め込み ────────────────────────────────────────────────────────
@lru_cache(maxsize=2)
def _sentence_transformer(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _cache_path(model_name: str, texts: list[str]) -> Path:
    h = hashlib.sha256(model_name.encode("utf-8"))
    for t in texts:
        h.update(t.encode("utf-8"))
        h.update(b"\x00")
    return CACHE_DIR / f"{h.hexdigest()[:32]}.npy"


def embed_documents(texts: list[str], model_name: str) -> np.ndarray:
    """文書側の埋め込み。同一コーパス・同一モデルならディスクから再利用する。

    k スイープと N=3 反復で同じコーパスを何度も索引するため、ここを毎回
    計算し直すと実験が回らない。埋め込みは決定的なのでキャッシュしてよい。
    """
    cache = _cache_path(model_name, texts)
    if cache.is_file():
        return np.load(cache)

    model = _sentence_transformer(model_name)
    vectors = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, vectors)
    return vectors


def embed_query(text: str, model_name: str) -> np.ndarray:
    model = _sentence_transformer(model_name)
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vector, dtype=np.float32)[0]


# ── 索引 ────────────────────────────────────────────────────────────
@dataclass
class Hit:
    chunk: Chunk
    rrf_score: float
    bm25_rank: int | None
    dense_rank: int | None


class HybridIndex:
    """BM25 + 密ベクトルの hybrid retrieval。"""

    def __init__(self, chunks: list[Chunk], locale: str, model_name: str | None = None) -> None:
        self.chunks = chunks
        self.locale = locale
        self.model_name = model_name or embedding_model_name()

        # BM25 は「出所 + 本文」で索引する。案件コードは見出しや A1 セルにある
        texts = [f"{c.path} {c.locator}\n{c.text}" for c in chunks]
        self._bm25 = BM25Okapi([tokenize(t, locale) for t in texts])
        self._vectors = embed_documents(texts, self.model_name)

    def search(self, question: str, k: int) -> list[Hit]:
        """RRF で疎と密を融合して上位 k 件を返す。"""
        bm25_scores = np.asarray(self._bm25.get_scores(tokenize(question, self.locale)))
        dense_scores = self._vectors @ embed_query(question, self.model_name)

        bm25_rank = _ranks(bm25_scores)
        dense_rank = _ranks(dense_scores)

        fused = 1.0 / (RRF_K0 + bm25_rank) + 1.0 / (RRF_K0 + dense_rank)
        order = np.argsort(-fused, kind="stable")[:k]

        return [
            Hit(
                chunk=self.chunks[i],
                rrf_score=float(fused[i]),
                bm25_rank=int(bm25_rank[i]),
                dense_rank=int(dense_rank[i]),
            )
            for i in order
        ]


def _ranks(scores: np.ndarray) -> np.ndarray:
    """スコアの降順順位（1 始まり）。同点は出現順で安定させる。"""
    order = np.argsort(-scores, kind="stable")
    ranks = np.empty_like(order)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks
