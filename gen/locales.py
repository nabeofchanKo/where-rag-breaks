"""コーパスの言語切り替え。

既定は日本語（``ja``）。``--locale en`` で英語コーパスも生成できる。

**ファイル名・フォルダ名は常に ASCII** にすること（SPEC §10）。
Windows のファイルシステムは日本語名を NFD 正規化するため、Python の NFC
リテラルで組んだパスは ``exists() == False`` になる。中身だけを日本語に
することでこの罠を完全に回避する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Locale:
    """1言語ぶんの語彙と文面テンプレート。"""

    code: str

    # 語彙（文書中に登場する固有名）
    people: tuple[str, ...]
    departments: tuple[str, ...]
    sites: tuple[str, ...]
    project_names: tuple[str, ...]
    items: tuple[str, ...]
    statuses: tuple[str, ...]  # (承認済, 保留) の順

    # 文面テンプレート
    s: dict[str, str]

    def fmt(self, key: str, **kw: object) -> str:
        return self.s[key].format(**kw)


JA = Locale(
    code="ja",
    people=(
        "佐藤 健一", "鈴木 美咲", "高橋 直樹", "田中 彩", "伊藤 大輔",
        "渡辺 結衣", "山本 拓也", "中村 さくら", "小林 悠真", "加藤 玲奈",
        "吉田 翔太", "山田 陽菜", "佐々木 健", "山口 真由", "松本 亮",
        "井上 綾香", "木村 隆", "林 芽衣", "清水 淳", "斎藤 千尋",
    ),
    departments=(
        "営業一部", "営業二部", "経営企画部", "情報システム部", "品質保証部",
        "調達部", "製造技術部", "財務経理部", "法務部", "設備保全部",
    ),
    sites=(
        "横浜工場", "川崎事業所", "名古屋工場", "大阪支社",
        "仙台営業所", "福岡支社", "郡山工場", "神戸事業所",
    ),
    project_names=(
        "配電盤更新", "生産ライン自動化", "受変電設備更新", "空調設備更新",
        "排水処理設備改修", "倉庫自動搬送導入", "検査装置更新",
        "太陽光発電設備導入", "防火設備改修", "ネットワーク基盤刷新",
        "非常用発電機更新", "計装システム更新",
    ),
    items=(
        "高圧受電盤", "低圧配電盤", "動力制御盤", "計装ケーブル", "接地工事",
        "搬入据付費", "試験調整費", "既設撤去費", "仮設電源費", "設計技術費",
        "保守部品一式", "遠隔監視装置",
    ),
    statuses=("承認済", "保留"),
    s={
        # ── text チャネル ─────────────────────────────────────
        "doc_title": "案件概要書",
        "doc_header": "{title}（案件コード: {code}）",
        "sec_outline": "1. 案件概要",
        "sec_scope": "2. 作業範囲",
        "sec_schedule": "3. 実施スケジュール",
        "sec_contact": "4. 体制および連絡先",
        "sec_notes": "5. 特記事項",
        "outline_body": (
            "本件は{site}における{project}を目的とする。"
            "現行設備は設置から年数が経過しており、更新により稼働率の改善を図る。"
            "本書は関係者間の認識合わせを目的として作成したものであり、"
            "契約条件の詳細は別途取り交わす契約書に従う。"
        ),
        "scope_body": (
            "作業範囲は{site}構内に限る。既設設備の撤去、新設機器の搬入据付、"
            "試験調整および取扱説明までを含む。構外の配線工事は本件の範囲外とする。"
        ),
        "schedule_body": (
            "着手予定は{start}、完了予定は{end}とする。"
            "工程の変更が生じた場合は、遅くとも2週間前までに書面で通知する。"
        ),
        "contact_body": (
            "本件の主管部署は{department}である。"
            "契約に関する窓口は{owner}が務め、技術的な照会は{engineer}が対応する。"
        ),
        "notes_body": (
            "本件の予算区分は設備投資枠とし、支出決裁は{approver}長の承認を要する。"
            "納入後の保証期間は引渡し日から12か月とする。"
        ),
        "q_owner": "案件コード {code} の契約に関する窓口を務めるのは誰か。氏名を答えよ。",
        "q_engineer": "案件コード {code} で技術的な照会に対応するのは誰か。氏名を答えよ。",
        "q_department": "案件コード {code} の主管部署はどこか。",
        "q_site": "案件コード {code} の作業を実施する場所はどこか。",
        "q_end": "案件コード {code} の完了予定日はいつか。YYYY-MM-DD 形式で答えよ。",
        "q_approver": (
            "案件コード {code} で支出決裁の承認を行うのはどの部署の長か。部署名を答えよ。"
        ),
        # ── formula チャネル ──────────────────────────────────
        "xl_sheet_detail": "明細",
        "xl_sheet_summary": "サマリ",
        "xl_sheet_config": "設定",
        "xl_title": "{project} 見積明細（{code}）",
        "xl_h_item": "品目",
        "xl_h_qty": "数量",
        "xl_h_unit_price": "単価",
        "xl_h_amount": "金額",
        "xl_h_status": "区分",
        "xl_l_subtotal": "明細合計",
        "xl_l_approved": "承認済合計",
        "xl_l_tax": "消費税額",
        "xl_l_total": "税込総額",
        "xl_l_tax_rate": "消費税率",
        "xl_note": "金額欄は数量×単価で自動計算される。表示値ではなく計算式を正とする。",
        "q_subtotal": "見積 {code} の明細合計（税抜）はいくらか。円単位の数値で答えよ。",
        "q_approved": (
            "見積 {code} のうち、区分が「承認済」となっている品目だけの合計金額"
            "（税抜）はいくらか。円単位の数値で答えよ。"
        ),
        "q_total": "見積 {code} の税込総額はいくらか。円単位の数値で答えよ。",
    },
)


EN = Locale(
    code="en",
    people=(
        "James Whitfield", "Marta Olsen", "Daniel Reyes", "Aisha Karim", "Peter Lindqvist",
        "Hannah Boateng", "Victor Nakamura", "Clara Dubois", "Omar Haddad", "Ingrid Solberg",
        "Ethan Caldwell", "Priya Raman", "Lukas Berger", "Naomi Fletcher", "Tomas Novak",
        "Sofia Marchetti", "Gabriel Santos", "Elena Petrova", "Marcus Obi", "Yuki Tanaka",
    ),
    departments=(
        "Sales Division I", "Sales Division II", "Corporate Planning", "IT Systems",
        "Quality Assurance", "Procurement", "Manufacturing Engineering", "Finance",
        "Legal Affairs", "Facilities Maintenance",
    ),
    sites=(
        "Yokohama Plant", "Kawasaki Works", "Nagoya Plant", "Osaka Branch",
        "Sendai Office", "Fukuoka Branch", "Koriyama Plant", "Kobe Works",
    ),
    project_names=(
        "switchgear replacement", "production line automation", "substation renewal",
        "HVAC replacement", "wastewater facility refit", "automated warehouse rollout",
        "inspection equipment renewal", "rooftop solar installation",
        "fire protection refit", "network backbone renewal",
        "standby generator replacement", "instrumentation system upgrade",
    ),
    items=(
        "HV switchboard", "LV distribution board", "motor control panel",
        "instrumentation cable", "earthing works", "delivery and installation",
        "commissioning and testing", "removal of existing equipment",
        "temporary power supply", "engineering design", "spare parts set",
        "remote monitoring unit",
    ),
    statuses=("Approved", "On hold"),
    s={
        "doc_title": "Project Overview",
        "doc_header": "{title} (project code: {code})",
        "sec_outline": "1. Overview",
        "sec_scope": "2. Scope of work",
        "sec_schedule": "3. Schedule",
        "sec_contact": "4. Organisation and contacts",
        "sec_notes": "5. Remarks",
        "outline_body": (
            "This project covers the {project} at {site}. "
            "The existing equipment has been in service for many years, and the "
            "replacement is intended to improve availability. "
            "This document exists to align the parties involved; the detailed "
            "contractual terms are governed by the contract executed separately."
        ),
        "scope_body": (
            "The scope is limited to the premises of {site}. It covers removal of the "
            "existing equipment, delivery and installation of the new units, "
            "commissioning and handover training. Cabling outside the premises is "
            "excluded from this project."
        ),
        "schedule_body": (
            "Work is scheduled to start on {start} and to complete on {end}. "
            "Any change to the schedule shall be notified in writing at least two "
            "weeks in advance."
        ),
        "contact_body": (
            "The department responsible for this project is {department}. "
            "Contractual matters are handled by {owner}, and technical enquiries are "
            "answered by {engineer}."
        ),
        "notes_body": (
            "This project is funded from the capital expenditure budget, and "
            "disbursement requires approval from the head of {approver}. "
            "The warranty period is twelve months from the date of handover."
        ),
        "q_owner": "Who handles contractual matters for project code {code}? Give the name.",
        "q_engineer": "Who answers technical enquiries for project code {code}? Give the name.",
        "q_department": "Which department is responsible for project code {code}?",
        "q_site": "At which location is the work for project code {code} carried out?",
        "q_end": (
            "What is the scheduled completion date of project code {code}? "
            "Answer as YYYY-MM-DD."
        ),
        "q_approver": (
            "For project code {code}, the head of which department must approve "
            "disbursement? Give the department name."
        ),
        "xl_sheet_detail": "Detail",
        "xl_sheet_summary": "Summary",
        "xl_sheet_config": "Config",
        "xl_title": "{project} - quotation detail ({code})",
        "xl_h_item": "Item",
        "xl_h_qty": "Qty",
        "xl_h_unit_price": "Unit price",
        "xl_h_amount": "Amount",
        "xl_h_status": "Status",
        "xl_l_subtotal": "Subtotal",
        "xl_l_approved": "Approved subtotal",
        "xl_l_tax": "Tax",
        "xl_l_total": "Total incl. tax",
        "xl_l_tax_rate": "Tax rate",
        "xl_note": (
            "The amount column is computed as qty x unit price. "
            "The formula, not any displayed value, is authoritative."
        ),
        "q_subtotal": (
            "What is the subtotal excluding tax of quotation {code}? Answer as a number."
        ),
        "q_approved": (
            "In quotation {code}, what is the combined amount excluding tax of only "
            "the items whose status is 'Approved'? Answer as a number."
        ),
        "q_total": "What is the total including tax of quotation {code}? Answer as a number.",
    },
)


_LOCALES = {"ja": JA, "en": EN}


def get_locale(code: str) -> Locale:
    try:
        return _LOCALES[code]
    except KeyError:
        raise ValueError(f"unknown locale: {code!r} (choose from {sorted(_LOCALES)})") from None
