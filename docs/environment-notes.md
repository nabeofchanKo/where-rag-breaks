# 環境の罠（実測記録）

SPEC.md §10 に書かれていた既知の罠に加えて、実装中に**実際に踏んだもの**を
測定値つきで記録する。どれも「エラーメッセージから原因にたどり着けない」
種類のものなので、再発時に時間を溶かさないために残す。

---

## 1. OOXML は素直に生成するとバイト再現しない

**症状**: 同じ seed で 2 回生成しても、docx/xlsx/pptx のバイト列が一致しない。
SPEC §8 の P0 完了条件「同 seed 再生成がバイト一致」が達成できない。

**原因**: OOXML の実体は zip で、以下が実行のたびに変わる。

| 埋め込まれる場所 | 中身 |
|---|---|
| zip の各エントリヘッダ | ファイルの更新時刻 |
| `docProps/core.xml` | `dcterms:created` / `dcterms:modified` |

openpyxl は両方に**実行時の壁時計**を書き込む。実測:

```
【正規化前】zip の更新時刻: [(2026, 9, 25, 11, 5, 10)]   ← 実行時刻
【正規化前】core.xml:       2026-09-25T03:05:25Z

【正規化後】zip の更新時刻: [(1980, 1, 1, 0, 0, 0)]
【正規化後】core.xml:       2026-01-01T00:00:00Z
```

**対処**: [`gen/common.py`](../gen/common.py) の `normalize_ooxml()`。生成直後に
zip を固定タイムスタンプで詰め直し、`core.xml` の日時を置換する。
`tests/test_determinism.py::test_same_seed_is_byte_identical` が固定している。

> なお python-docx 単体では既定テンプレートの `core.xml` をそのまま複製するため
> 一致することがある。**xlsx で必ず壊れる**ので、拡張子によらず全て通すこと。

---

## 2. AVG が仕込む `SSLKEYLOGFILE` で Python が無言で即死する

**症状**: HTTPS 接続を行った瞬間、Python プロセスが次の 1 行だけを残して落ちる。
Python の例外ではないのでトレースバックが出ない。

```
OPENSSL_Uplink(00007FF8B15D4AF8,08): no OPENSSL_Applink
```

`urllib` / `requests` / `huggingface_hub` のいずれでも起きる。`import ssl` は通り、
`ssl.OPENSSL_VERSION` も読めるので、SSL 自体が壊れているようには見えない。

**原因**: AVG アンチウイルスが TLS 傍受のために環境変数を設定している。

```
SSLKEYLOGFILE=\\.\avgMonFltProxy\310af07673f7662a
NODE_EXTRA_CA_CERTS=C:\ProgramData\AVG\Antivirus\wscert.pem
```

OpenSSL は `SSLKEYLOGFILE` があると、C ランタイムの `FILE*` API でその名前付き
パイプを開こうとする。Windows 版 Python に同梱される OpenSSL は
`OPENSSL_Applink` を提供していないため、この経路に入った時点でクラッシュする。

**対処**: HTTPS を使う前にこの環境変数を落とす。
[`arms/llm.py`](../arms/llm.py) の `bootstrap()` が全入口の先頭で実行する。

```python
os.environ.pop("SSLKEYLOGFILE", None)
```

あわせて `truststore.inject_into_ssl()` も入れる（傍受された証明書チェーンを
OS の証明書ストアで検証するため。SPEC §10 の既知項目）。

---

## 3. Windows コンソールの文字化け

**症状**: 日本語のログが `������` になる。

**原因**: Windows の既定コンソールコードページが cp932。

**対処**: 各エントリポイントの冒頭で標準出力を UTF-8 に張り替える。

```python
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
```

---

## 4. 日本語ファイル名の NFD 正規化（回避済み）

SPEC §10 の既知項目。Windows のファイルシステムは日本語名を NFD 正規化するため、
Python の NFC リテラルで組んだパスは `exists() == False` になる。

**このリポジトリでは踏まない設計にしてある**。コーパス本文は日本語だが、
**ファイル名・フォルダ名は常に ASCII**（案件コード `PRJ-0142` など）。
`tests/test_determinism.py::test_filenames_are_ascii` が固定している。

実データ検証（SPEC §9 / P5）で外部ファイルを扱うときは、`listdir` で実名を
取得して NFC 比較する処理が必要になる。

---

## 5. Claude Agent SDK が実行者の MCP 設定を引き込む

**症状**: ツールを渡していないはずの Arm A の呼出に、`tool_calls=1` が記録される。
ツール名は `mcp__claude_ai_Claude_Docs__guide` で、このベンチマークとは無関係。

**原因**: SDK が起動する `claude` サブプロセスは、既定で実行者の環境に設定された
MCP サーバを読み込む。`setting_sources=None` を指定しても MCP サーバは止まらない。

**なぜ致命的か**: 呼出は権限で拒否されるためデータは漏れない。しかし
「ベースラインが実行者の手元の設定を見られる」状態で測った数字は他人の環境で
再現できない。公平な比較を前提にするベンチマークではこれだけで run が無効になる。

**対処**: [`arms/llm.py`](../arms/llm.py) で外から入る経路を全部塞ぐ。

```python
mcp_servers={}, strict_mcp_config=True,
setting_sources=None, skills=None, plugins=[],
```

あわせて呼出ごとに `tool_names` / `tool_results` / `permission_denials` を記録し、
`eval/run.py` が実行の最後に「ツールが結果を返した回数」を表示する。Arm A で
これが 0 でない run は無効として扱う。

発覚時の経緯と破棄した run は
[`results/discarded-20260925-nonhermetic/`](../results/discarded-20260925-nonhermetic/README.md)。

---

## 6. PDF の `/ID` は「同じ長さで置換」では潰しきれない

**症状**: `scanned` チャネルだけが、200 ファイル中 1 件の頻度でバイト一致しない。

**原因**: PyMuPDF は保存のたびにランダムな `/ID` を書く。このとき 2 要素は
16進文字列 `<...>` とは限らず、乱数の中身によってはリテラル文字列 `(...)` に
なる。エスケープが入るぶん**ファイル全長まで変わる**ので、長さを保つ置換では
そもそも追いつかない。さらにリテラル文字列の中に `]` が入ると、
`\[(.*?)\]` のような非貪欲マッチが途中で切れて置換結果が壊れる。

**対処**: `gen/common.py` の `normalize_pdf`。

- `/ID` は trailer にあり、trailer は xref テーブルより**後ろ**にある。
  xref のエントリも `startxref` も前方しか指さないので、
  **trailer 内に限れば長さを変えても壊れない**。正規形に置き換える
- 中身の切り出しは正規表現ではなく、PDF の文字列構文（`<...>` と `(...)`、
  エスケープとネスト）を追う走査で行う
- xref ストリーム形式で ID がオブジェクト内にある場合に備え、
  trailer 外では従来どおり同じ長さの詰め替えに落とす

150 回連続生成でバイト一致を確認済み。

---

## 7. AES zip は salt がランダムなので、そのままでは決定的にならない

**症状**: `locked` チャネルの暗号化ファイルが毎回違うバイト列になる。

**原因**: AES はエントリごとにランダムな salt を使う（pyzipper は
`Cryptodome.Random` から取る）。

**対処**: `gen/common.py` の `deterministic_aes_zip` が、生成中だけ乱数源を
ファイル名から導いた固定シードの PRNG に差し替える。

> **ここで生成するのは合成コーパスであり、パスワードは同じコーパス内の別文書に
> 規則として公開されている。** 秘匿が目的ではなく「プログラムから素直には
> 開けないファイル」を再現可能に作ることが目的なので、salt の固定で困る人は
> いない。当然ながら、本物の秘密をこの関数で守ってはいけない。

なお SPEC §3-5 は `locked` の暗号化方式を「msoffcrypto-tool → 不可なら
pyzipper の AES zip」としていた。msoffcrypto-tool は暗号化側の対応が
確認できなかったため、**退避先の pyzipper を採用**している。
「パスワード規則が別文書にある」という構造は変わらない。
