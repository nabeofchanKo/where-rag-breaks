"""画像と PDF の生成（決定的）。

★ **SPEC §3-4「LibreOffice 不要の設計」の実装**:
    Office ファイルを画像に変換するには通常 LibreOffice が要るが、
    **画像を先に PIL / matplotlib で作り、それを Office ファイルに埋め込む**
    ことで、Office ファイルをレンダリングする必要が一度もなくなる。

決定性のために守ること:
    - matplotlib は既定で PNG に ``Software`` メタデータを書く → 明示的に消す
    - PIL は既定では何も埋め込まない → そのままでよい
    - PyMuPDF は保存のたびにランダムな ``/ID`` を書く
      → ``gen.common.normalize_pdf`` で潰す
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pymupdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from gen.common import normalize_pdf  # noqa: E402

# 日本語を出せるフォント。CJK が要るのに見つからない場合は**黙って豆腐にせず落とす**
# （気づかないまま読めないコーパスを作るほうが有害なため）。
_CJK_FONT_NAMES = ("Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP", "IPAexGothic")
_CJK_FONT_FILES = (
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
)


class MissingCJKFontError(RuntimeError):
    """日本語コーパスを作るのに CJK フォントが無い。"""


@lru_cache(maxsize=1)
def find_cjk_font_name() -> str | None:
    """matplotlib から使える CJK フォント名。"""
    from matplotlib import font_manager

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_FONT_NAMES:
        if name in available:
            return name
    return None


@lru_cache(maxsize=1)
def find_cjk_font_file() -> str | None:
    """PIL から使える CJK フォントファイルのパス。"""
    for path in _CJK_FONT_FILES:
        if Path(path).is_file():
            return path

    from matplotlib import font_manager

    for name in _CJK_FONT_NAMES:
        try:
            found = font_manager.findfont(name, fallback_to_default=False)
        except Exception:  # noqa: BLE001
            continue
        if found and Path(found).is_file():
            return found
    return None


def require_fonts(locale_code: str) -> None:
    """日本語コーパスを作る前に、フォントの有無を確かめて早期に落とす。"""
    if locale_code != "ja":
        return
    if find_cjk_font_name() is None or find_cjk_font_file() is None:
        raise MissingCJKFontError(
            "日本語コーパスの画像生成には CJK フォントが必要。\n"
            "  Windows: 通常は Yu Gothic / Meiryo が入っている\n"
            "  Linux  : sudo apt-get install -y fonts-noto-cjk\n"
            "  回避   : --locale en で英語コーパスを生成する"
        )


def _pil_font(size: int, locale_code: str) -> ImageFont.FreeTypeFont:
    path = find_cjk_font_file() if locale_code == "ja" else None
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size)


# ── グラフ画像（chart_only チャネル）────────────────────────────────
def save_bar_chart(
    path: Path,
    title: str,
    categories: list[str],
    values: list[float],
    ylabel: str,
    locale_code: str,
) -> None:
    """棒グラフの PNG を作る。**数値ラベルは描かない**。

    棒に数値を書いてしまうと OCR なしでも読めてしまい、罠として弱くなる。
    値はあくまで棒の高さと軸目盛りからしか読めない状態にする。
    """
    font_name = find_cjk_font_name() if locale_code == "ja" else None
    with plt.rc_context({"font.family": font_name} if font_name else {}):
        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        ax.bar(categories, values, color="#4C72B0")
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)
        fig.tight_layout()
        path.parent.mkdir(parents=True, exist_ok=True)
        # matplotlib は既定で Software メタデータを書く。決定性のため消す。
        fig.savefig(path, dpi=110, metadata={"Software": None})
        plt.close(fig)


# ── 配置図（layout チャネル）────────────────────────────────────────
@dataclass(frozen=True)
class Seat:
    label: str
    x: int
    y: int
    w: int = 110
    h: int = 60


def save_layout_png(
    path: Path,
    title: str,
    seats: list[Seat],
    locale_code: str,
    size: tuple[int, int] = (900, 560),
) -> None:
    """座席図・配置図を既知座標で描く。

    答えは**空間関係**（どの区画の隣か、どの列の何番目か）にしかない。
    ラベル文字列だけを抜き出しても位置関係は復元できない。
    """
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    title_font = _pil_font(22, locale_code)
    label_font = _pil_font(16, locale_code)

    draw.text((24, 18), title, fill="black", font=title_font)
    for seat in seats:
        box = (seat.x, seat.y, seat.x + seat.w, seat.y + seat.h)
        draw.rectangle(box, outline="#333333", width=2, fill="#EEF3FA")
        bbox = draw.textbbox((0, 0), seat.label, font=label_font)
        draw.text(
            (
                seat.x + (seat.w - (bbox[2] - bbox[0])) / 2,
                seat.y + (seat.h - (bbox[3] - bbox[1])) / 2,
            ),
            seat.label,
            fill="black",
            font=label_font,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")  # PIL は既定でタイムスタンプを埋めない


# ── スキャンPDF（scanned チャネル）──────────────────────────────────
def save_scanned_pdf(path: Path, pages: list[list[str]], dpi: int = 130) -> None:
    """**テキスト層のない**画像だけの PDF を作る。

    手順（SPEC §3-4）:
        1. PyMuPDF で通常のテキスト PDF を作る
        2. 各ページを ``get_pixmap`` でラスタライズする
        3. 画像だけの PDF として組み直す

    2 で文字は画素になるので、3 の PDF から ``pypdf`` / ``pdfplumber`` で
    テキストを抽出しても**何も取れない**。OCR を通すしかない。
    """
    source = pymupdf.open()
    for lines in pages:
        page = source.new_page()
        y = 80.0
        for line in lines:
            page.insert_text((64, y), line, fontsize=11, fontname="japan")
            y += 22.0

    scanned = pymupdf.open()
    for page in source:
        pixmap = page.get_pixmap(dpi=dpi)
        target = scanned.new_page(width=page.rect.width, height=page.rect.height)
        target.insert_image(target.rect, pixmap=pixmap)
    source.close()

    path.parent.mkdir(parents=True, exist_ok=True)
    scanned.save(path, deflate=True)
    scanned.close()
    normalize_pdf(path)
