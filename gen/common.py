"""コーパス生成の共通基盤。

このモジュールが担保するもの:

1. ``Item`` — 設問と正解の唯一の表現（SPEC §3-3 の契約）
2. 決定的な乱数 — 同じ seed なら同じコーパスになる
3. ``normalize_ooxml`` — OOXML（docx/xlsx/pptx）をバイト再現可能にする

3 が必要な理由:
    docx/xlsx/pptx の実体は zip で、内部に (a) 各エントリの更新時刻、
    (b) ``docProps/core.xml`` の作成・更新日時が埋め込まれる。seed を固定しても
    これらは実行のたびに変わるため、素直に生成すると SPEC §8 P0 の完了条件
    「同 seed 再生成がバイト一致」は絶対に満たせない。生成直後に zip を
    固定タイムスタンプで詰め直すことで、初めてバイト一致が成立する。
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

# ── 決定性のための固定値 ────────────────────────────────────────────
# zip のローカルヘッダが持てる最古の日時（1980-01-01）。
FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)
# OOXML の docProps/core.xml に書き込む固定日時。
FIXED_ISO_DATETIME = "2026-01-01T00:00:00Z"

ANSWER_TYPES = ("number", "identifier", "name", "list", "text")
LOCALES = ("ja", "en")


# ── Item ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Item:
    """1 設問 = 1 Item。SPEC §3-3 の契約。

    ``answer`` は **生成時に確定した値をそのまま**入れる。生成後にファイルを
    読み直して正解を作ってはいけない（読み直しのバグが正解に混入するため）。
    """

    qid: str  # 例 "formula-03"
    channel: str
    question: str
    answer: str  # 正規化前の正解文字列
    answer_type: str  # ANSWER_TYPES のいずれか
    answer_aliases: list[str] = field(default_factory=list)  # 許容表記
    source_files: list[str] = field(default_factory=list)  # 診断用。アームには渡さない
    difficulty: int = 1  # 1-3
    locale: str = "ja"

    def __post_init__(self) -> None:
        if self.answer_type not in ANSWER_TYPES:
            raise ValueError(f"unknown answer_type: {self.answer_type!r}")
        if self.locale not in LOCALES:
            raise ValueError(f"unknown locale: {self.locale!r}")
        if not 1 <= self.difficulty <= 3:
            raise ValueError(f"difficulty must be 1-3: {self.difficulty}")
        if not self.answer.strip():
            raise ValueError(f"{self.qid}: answer is empty")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def accepted(self) -> list[str]:
        """正解として受理する表記の全体（answer + aliases）。"""
        return [self.answer, *self.answer_aliases]


def write_questions_jsonl(items: list[Item], path: Path) -> None:
    """questions.jsonl を決定的な順序で書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(items, key=lambda it: it.qid)
    with path.open("w", encoding="utf-8", newline="\n") as fp:
        for item in ordered:
            fp.write(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def read_questions_jsonl(path: Path) -> list[Item]:
    items: list[Item] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                items.append(Item(**json.loads(line)))
    return items


# ── 決定的な乱数 ─────────────────────────────────────────────────────
def make_rng(seed: int, *namespace: str) -> random.Random:
    """seed と名前空間から決定的に ``random.Random`` を作る。

    Python の組込み ``hash()`` はプロセスごとに salt が変わるため使わない。
    チャネルごとに名前空間を分けることで、あるチャネルの生成内容を変えても
    他チャネルの生成結果が動かない（差分レビューが読める）。
    """
    key = f"{seed}:" + ":".join(namespace)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# ── OOXML のバイト再現性 ─────────────────────────────────────────────
_CORE_DATE_RE = re.compile(
    rb"(<(?:dcterms:)?(?:created|modified)[^>]*>)[^<]*(</(?:dcterms:)?(?:created|modified)>)"
)


def normalize_ooxml(path: Path) -> None:
    """OOXML ファイルをバイト再現可能な形に詰め直す（インプレース）。

    - 全エントリの更新時刻を 1980-01-01 に固定する
    - エントリ順をファイル名でソートする
    - ``docProps/core.xml`` の created / modified を固定日時に置換する
    """
    with zipfile.ZipFile(path) as zf:
        entries = [(info.filename, zf.read(info.filename)) for info in zf.infolist()]

    normalized: list[tuple[str, bytes]] = []
    for name, data in sorted(entries, key=lambda kv: kv[0]):
        if name == "docProps/core.xml":
            data = _CORE_DATE_RE.sub(
                rb"\g<1>" + FIXED_ISO_DATETIME.encode("ascii") + rb"\g<2>", data
            )
        normalized.append((name, data))

    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name, data in normalized:
            info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_DATETIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            info.create_system = 0  # FAT。プラットフォーム差を消す
            zf.writestr(info, data)
    tmp.replace(path)


_OOXML_SUFFIXES = {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm"}


def normalize_artifact(path: Path) -> None:
    """生成物を決定的な形に正規化する。拡張子で処理を振り分ける。

    OOXML 以外（PDF / PNG）は、生成側でタイムスタンプを埋め込まない書き方を
    しているため追加処理は不要。詳細は各チャネルの生成器を参照。
    """
    if path.suffix.lower() in _OOXML_SUFFIXES:
        normalize_ooxml(path)


# ── ハッシュ（決定性テスト用）────────────────────────────────────────
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def hash_tree(root: Path) -> dict[str, str]:
    """ディレクトリ配下の全ファイルを ``相対パス -> sha256`` で返す。"""
    return {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# ── 表記の正規化（採点と漏洩検査で共用）──────────────────────────────
_PUNCT_TAIL = "。．.、,，:：;；!！?？\"'”’)）]】"


def normalize_text(value: str) -> str:
    """採点用の正規化。

    全角半角・空白・桁区切り・末尾句読点・大文字小文字を吸収する。
    ここを緩めすぎると誤答を正解と判定してしまうので、**単位は落とさない**
    （単位違いは別の答え）。桁区切りのカンマだけを落とす。
    """
    s = unicodedata.normalize("NFKC", value)
    s = s.strip().strip(_PUNCT_TAIL).strip()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)  # 1,320 -> 1320（桁区切りのみ）
    return s.casefold()


def number_aliases(value: float | int, unit: str = "") -> list[str]:
    """数値の許容表記を作る。

    生成時に確定させること（SPEC §11: 結果を見てから alias を足さない）。
    """
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    if isinstance(value, int):
        plain = str(value)
        grouped = f"{value:,}"
    else:
        plain = f"{value:g}"
        grouped = f"{value:,g}"

    out = [plain, grouped]
    if unit:
        out += [f"{plain}{unit}", f"{grouped}{unit}"]
    # 重複を保ったまま順序を維持して除去
    seen: set[str] = set()
    uniq: list[str] = []
    for a in out:
        if a not in seen:
            seen.add(a)
            uniq.append(a)
    return uniq
