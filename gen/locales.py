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
        "site_premises": "{site}構内",
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
        "xl_revision": "改訂: 第{n}版（明細の数量を見直し済み）",
        "xl_item_numbered": "{item} 枝番{n:03d}",
        "q_subtotal": "見積 {code} の明細合計（税抜）はいくらか。円単位の数値で答えよ。",
        "q_approved": (
            "見積 {code} のうち、区分が「承認済」となっている品目だけの合計金額"
            "（税抜）はいくらか。円単位の数値で答えよ。"
        ),
        "q_total": "見積 {code} の税込総額はいくらか。円単位の数値で答えよ。",
        # ── format チャネル ──────────────────────────────────
        "fm_sheet": "検査記録",
        "fm_title": "{site} 受入検査記録（{code}）",
        "fm_h_id": "管理番号",
        "fm_h_item": "品目",
        "fm_h_value": "測定値",
        "fm_h_spec": "規格値",
        "fm_h_note": "備考",
        "fm_note_flagged": "要再検査",
        "fm_note_decoy": "確認中",
        "q_format": (
            "検査記録 {code} で、背景が黄色く塗られている行の管理番号を答えよ。"
        ),
        # ── hidden チャネル ──────────────────────────────────
        "hd_title": "{project} ご提案（{code}）",
        "hd_slide_overview": "提案概要",
        "hd_slide_price": "お見積り",
        "hd_slide_schedule": "スケジュール",
        "hd_body_overview": "{site}における{project}をご提案いたします。",
        "hd_body_price": "詳細は別紙見積書をご参照ください。",
        "hd_body_schedule": "着手から完了までおよそ{months}か月を想定しています。",
        "hd_note_discount": (
            "社内メモ: 本件の値引き上限は{rate}%。これを超える場合は部長決裁が必要。"
        ),
        "hd_body_discount_shown": "想定値引き率: {rate}%",
        "hd_body_discount_decoy": "参考: 前回案件の値引き率は{rate}%でした。",
        "q_hidden": (
            "提案 {code} において、社内で定めている値引きの上限は何パーセントか。"
            "数値のみ答えよ。"
        ),
        # ── cross_file チャネル ──────────────────────────────
        "cf_doc_title": "案件台帳（{code}）",
        "cf_body": "案件コード {code} の契約金額は {amount} 円である。主管は{department}。",
        "cf_summary_title": "案件シリーズ {series} 集計表",
        "cf_summary_body": "本シリーズの契約金額合計は {amount} 円（{asof}時点の集計）。",
        "q_cross_file": (
            "案件シリーズ {series} に属する全案件（{first} 〜 {last}）の"
            "契約金額の合計はいくらか。円単位の数値で答えよ。"
        ),
        # ── chart_only チャネル ──────────────────────────────
        "co_deck_title": "{period} 事業説明資料（{code}）",
        "co_slide_chart": "拠点別 出荷実績",
        "co_chart_title": "{period} 拠点別 出荷実績",
        "co_chart_ylabel": "出荷数（台）",
        "co_body_caption": "各拠点の出荷実績は下図のとおり。",
        "co_body_total": "参考: 全社合計は {total} 台。",
        "co_table_header": "拠点 | 出荷数（台）",
        "q_chart_only": (
            "事業説明資料 {code} の図表によると、{site} の出荷数は何台か。数値のみ答えよ。"
        ),
        # ── layout チャネル ──────────────────────────────────
        "ly_doc_title": "{room} 座席配置（{code}）",
        "ly_caption": "座席の配置は下図のとおり。",
        "ly_seat_rule": "A列は左から A-1、A-2、A-3 の順に並ぶ。",
        "ly_roster_heading": "在席者一覧（五十音順）",
        "ly_table_heading": "座席割当",
        "q_layout": "座席配置 {code} において、{person} のすぐ右隣の席に座っているのは誰か。",
        # ── scanned チャネル ─────────────────────────────────
        "sc_title": "受入検査成績書",
        "sc_line_code": "報告番号: {code}",
        "sc_line_site": "検査場所: {site}",
        "sc_line_item": "対象品目: {item}",
        "sc_line_lot": "ロット番号: {lot}",
        "sc_line_value": "測定値: {value}",
        "sc_line_judge": "判定: {judge}",
        "sc_cover_title": "検査成績書 送付状（{code}）",
        "sc_cover_body": (
            "標記の検査成績書を送付いたします。詳細は添付の成績書本体をご確認ください。"
        ),
        "sc_cover_decoy": "なお、前回ロット（{lot}）の判定は {judge} でした。",
        "q_scanned": "検査成績書 {code} のロット番号は何か。",
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
        "site_premises": "the premises of {site}",
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
        "xl_revision": "Revision {n} (line item quantities revised)",
        "xl_item_numbered": "{item} no.{n:03d}",
        "q_subtotal": (
            "What is the subtotal excluding tax of quotation {code}? Answer as a number."
        ),
        "q_approved": (
            "In quotation {code}, what is the combined amount excluding tax of only "
            "the items whose status is 'Approved'? Answer as a number."
        ),
        "q_total": "What is the total including tax of quotation {code}? Answer as a number.",
        # ── format ───────────────────────────────────────────
        "fm_sheet": "Inspection log",
        "fm_title": "{site} incoming inspection log ({code})",
        "fm_h_id": "Record no.",
        "fm_h_item": "Item",
        "fm_h_value": "Measured",
        "fm_h_spec": "Spec",
        "fm_h_note": "Note",
        "fm_note_flagged": "Re-inspection required",
        "fm_note_decoy": "Under review",
        "q_format": (
            "In inspection log {code}, give the record number of the row whose "
            "background is filled yellow."
        ),
        # ── hidden ───────────────────────────────────────────
        "hd_title": "{project} proposal ({code})",
        "hd_slide_overview": "Overview",
        "hd_slide_price": "Quotation",
        "hd_slide_schedule": "Schedule",
        "hd_body_overview": "We propose the {project} at {site}.",
        "hd_body_price": "Please refer to the separate quotation for details.",
        "hd_body_schedule": "We expect roughly {months} months from start to completion.",
        "hd_note_discount": (
            "Internal note: the discount ceiling for this deal is {rate}%. "
            "Anything beyond that needs director approval."
        ),
        "hd_body_discount_shown": "Planned discount: {rate}%",
        "hd_body_discount_decoy": "For reference, the previous deal was discounted {rate}%.",
        "q_hidden": (
            "For proposal {code}, what is the internally agreed discount ceiling, "
            "in percent? Answer with the number only."
        ),
        # ── cross_file ───────────────────────────────────────
        "cf_doc_title": "Case record ({code})",
        "cf_body": "The contract value of case {code} is {amount}. Owned by {department}.",
        "cf_summary_title": "Case series {series} roll-up",
        "cf_summary_body": "Total contract value for this series is {amount} (as of {asof}).",
        "q_cross_file": (
            "What is the combined contract value of every case in series {series} "
            "({first} through {last})? Answer as a number."
        ),
        # ── chart_only ───────────────────────────────────────
        "co_deck_title": "{period} business review ({code})",
        "co_slide_chart": "Shipments by site",
        "co_chart_title": "{period} shipments by site",
        "co_chart_ylabel": "Units shipped",
        "co_body_caption": "Shipments by site are shown below.",
        "co_body_total": "For reference, the company-wide total is {total} units.",
        "co_table_header": "Site | Units shipped",
        "q_chart_only": (
            "According to the figure in business review {code}, how many units did "
            "{site} ship? Answer with the number only."
        ),
        # ── layout ───────────────────────────────────────────
        "ly_doc_title": "{room} seating plan ({code})",
        "ly_caption": "The seating arrangement is shown below.",
        "ly_seat_rule": "Row A runs left to right as A-1, A-2, A-3.",
        "ly_roster_heading": "Occupants (alphabetical)",
        "ly_table_heading": "Seat assignments",
        "q_layout": (
            "In seating plan {code}, who sits in the seat immediately to the right "
            "of {person}?"
        ),
        # ── scanned ──────────────────────────────────────────
        "sc_title": "Incoming inspection report",
        "sc_line_code": "Report no.: {code}",
        "sc_line_site": "Location: {site}",
        "sc_line_item": "Item: {item}",
        "sc_line_lot": "Lot number: {lot}",
        "sc_line_value": "Measured: {value}",
        "sc_line_judge": "Result: {judge}",
        "sc_cover_title": "Inspection report cover note ({code})",
        "sc_cover_body": (
            "Please find the inspection report enclosed. See the report itself for details."
        ),
        "sc_cover_decoy": "Note that the previous lot ({lot}) was judged {judge}.",
        "q_scanned": "What is the lot number on inspection report {code}?",
    },
)


_LOCALES = {"ja": JA, "en": EN}


def get_locale(code: str) -> Locale:
    try:
        return _LOCALES[code]
    except KeyError:
        raise ValueError(f"unknown locale: {code!r} (choose from {sorted(_LOCALES)})") from None
