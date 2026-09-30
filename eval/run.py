"""アーム × 設問を走らせて raw.jsonl を吐く（SPEC §5-3）。

    uv run python -m eval.run --corpus corpus/ --arms classical --k 4,8,16

設計上の要点:

**再開可能にする。**
    N=3 × 棄権2モード × k スイープ × チャネル数 で呼出回数は簡単に数百に
    なる。途中で落ちたときに全部やり直すと費用が無駄になるので、raw.jsonl に
    追記しつつ、既に記録済みの (qid, arm, mode, k, repeat) は必ず飛ばす。

**アームに Item を渡さない。**
    渡すのは設問文とモードだけ。qid もチャネル名も source_files も見せない
    （SPEC §11「設問ごとの特別扱い」を構造的に不可能にする）。

**N=3 を既定にする。**
    temperature 0 でも LLM は非決定になりうる（SPEC §5-4）。1発取りの数字を
    結論にしないため、既定で 3 回走らせる。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from arms.agentic import AgenticArm
from arms.base import AnswerMode, ArmAnswer
from arms.classical import ClassicalArm
from arms.hybrid import HybridArm
from arms.llm import bootstrap, resolve_auth, resolve_model
from gen.common import Item, read_questions_jsonl

ARMS = {"classical": ClassicalArm, "agentic": AgenticArm, "hybrid": HybridArm}
DEFAULT_K = (4, 8, 16)
DEFAULT_REPEATS = 3
MODES: tuple[AnswerMode, ...] = ("abstain_ok", "forced")


def _key(qid: str, arm: str, mode: str, k: int | None, repeat: int) -> str:
    return f"{arm}|{mode}|{k}|{repeat}|{qid}"


def _load_done(raw_path: Path) -> set[str]:
    """既に記録済みの実行キー。再開のために使う。"""
    if not raw_path.is_file():
        return set()
    done: set[str] = set()
    with raw_path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            done.add(_key(row["qid"], row["arm"], row["mode"], row.get("k"), row["repeat"]))
    return done


def _row(
    item: Item, arm_name: str, mode: str, repeat: int, run_id: str, seed: int, out: ArmAnswer
) -> dict:
    """SPEC §5-3 の記録項目。正誤判定は score.py が後から付ける。"""
    row = asdict(out)
    row.update(
        {
            "run_id": run_id,
            "seed": seed,
            "qid": item.qid,
            "channel": item.channel,
            "difficulty": item.difficulty,
            "locale": item.locale,
            "arm": arm_name,
            "mode": mode,
            "repeat": repeat,
        }
    )
    return row


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.run", description="アーム × 設問を走らせて raw.jsonl を吐く。"
    )
    p.add_argument("--corpus", type=Path, default=Path("corpus"))
    p.add_argument("--arms", default="classical", help=f"カンマ区切り。実装済み: {','.join(ARMS)}")
    p.add_argument(
        "--k",
        default=",".join(str(k) for k in DEFAULT_K),
        help="Arm A の top-k スイープ（カンマ区切り）。SPEC §4-1: k=5 固定で殴らない",
    )
    p.add_argument(
        "--repeats", type=int, default=DEFAULT_REPEATS, help="反復回数（SPEC §5-4: 既定 3）"
    )
    p.add_argument(
        "--modes",
        default=",".join(MODES),
        help="棄権の扱い（SPEC §4-2）。既定は abstain_ok と forced の両方",
    )
    p.add_argument("--channels", default="", help="対象チャネルを絞る（カンマ区切り、既定は全部）")
    p.add_argument(
        "--qids", default="", help="対象の設問を qid で絞る（カンマ区切り。パイロット用）"
    )
    p.add_argument("--limit", type=int, default=0, help="設問数の上限（0 で無制限。動作確認用）")
    p.add_argument("--run-id", default="", help="既存の run に追記して再開する場合に指定")
    p.add_argument("--results", type=Path, default=Path("results"))
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    bootstrap()
    args = build_parser().parse_args(argv)

    corpus_meta = json.loads((args.corpus / "meta.json").read_text(encoding="utf-8"))
    locale = corpus_meta["locale"]
    seed = corpus_meta["seed"]

    items = read_questions_jsonl(args.corpus / "questions.jsonl")
    if args.channels:
        wanted = {c.strip() for c in args.channels.split(",") if c.strip()}
        items = [it for it in items if it.channel in wanted]
    if args.qids:
        wanted_qids = {q.strip() for q in args.qids.split(",") if q.strip()}
        missing = wanted_qids - {it.qid for it in items}
        if missing:
            print(f"コーパスに無い qid: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
        items = [it for it in items if it.qid in wanted_qids]
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("対象の設問が 0 件", file=sys.stderr)
        return 2

    arm_names = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in arm_names if a not in ARMS]
    if unknown:
        print(f"未実装のアーム: {', '.join(unknown)}", file=sys.stderr)
        return 2

    ks = [int(k) for k in args.k.split(",") if k.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.results / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw.jsonl"

    # ★ 再開時は同じコーパスであることを確かめる。P4 では規模違いのコーパスが
    #   並ぶので、--corpus を取り違えると別コーパスの結果が同じ run に混ざる
    #   （qid は規模をまたいで同じなので、記録済みとして黙ってスキップされる）。
    previous_meta = run_dir / "meta.json"
    if previous_meta.is_file():
        previous = json.loads(previous_meta.read_text(encoding="utf-8")).get("corpus")
        if previous != corpus_meta:
            print(
                f"エラー: {run_id} は別のコーパスで記録されている"
                f"（記録: {previous.get('n_files_written') if previous else '?'} ファイル、"
                f"今回: {corpus_meta.get('n_files_written')} ファイル）。--corpus を確かめること",
                file=sys.stderr,
            )
            return 2
    done = _load_done(raw_path)

    planned = sum(
        len(items)
        * len(modes)
        * args.repeats
        * (len(ks) if getattr(ARMS[name], "sweeps_k", True) else 1)
        for name in arm_names
    )
    print(f"run_id       : {run_id}")
    print(f"設問         : {len(items)} 問")
    print(f"アーム       : {', '.join(arm_names)}")
    print(f"k            : {ks}")
    print(f"モード       : {', '.join(modes)}")
    print(f"反復         : {args.repeats}")
    print(f"呼出予定     : {planned} 回（うち記録済み {len(done)} 回はスキップ）")
    print()

    meta = {
        "run_id": run_id,
        "started_at": datetime.now(UTC).isoformat(),
        "corpus": corpus_meta,
        "model": resolve_model(),
        # cli = 契約プランの利用枠を消費（API 従量課金なし）。このとき cost_usd は
        # 実請求額ではなく定価換算の参考値である。アーム間の比較には使えるが、
        # 「いくら払ったか」としては読めない。
        "auth": resolve_auth(),
        "arms": arm_names,
        "k_values": ks,
        "modes": modes,
        "repeats": args.repeats,
        "n_questions": len(items),
    }

    executed = 0
    with raw_path.open("a", encoding="utf-8", newline="\n") as sink:
        for arm_name in arm_names:
            arm = ARMS[arm_name]()
            arm.prepare(args.corpus, locale)
            meta.setdefault("arm_config", {})[arm_name] = arm.index_stats
            (run_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            # k を持たないアーム（Arm B）で k をスイープすると、同じ設定を
            # 何度も実行するだけになる。アーム側の宣言を見て畳む。
            arm_ks: list[int | None] = list(ks) if getattr(arm, "sweeps_k", True) else [None]
            if arm_ks != list(ks):
                print(f"  ({arm_name} は k を持たないため k スイープを畳んだ)")
            meta.setdefault("k_values_per_arm", {})[arm_name] = arm_ks

            for k in arm_ks:
                if k is not None:
                    arm.reindex_for_k(k)
                for mode in modes:
                    for repeat in range(args.repeats):
                        for item in items:
                            key = _key(item.qid, arm_name, mode, k, repeat)
                            if key in done:
                                continue
                            # 1 件の失敗で数百回ぶんのスイープを落とさない。
                            # 失敗も「そのアームの性能」なので記録して先へ進む。
                            try:
                                out = arm.answer(item.question, mode)  # type: ignore[arg-type]
                            except Exception as exc:  # noqa: BLE001
                                out = ArmAnswer(
                                    answer="",
                                    abstained=True,
                                    k=k,
                                    error=f"{type(exc).__name__}: {exc}",
                                )
                            row = _row(item, arm_name, mode, repeat, run_id, seed, out)
                            sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                            sink.flush()  # 途中で落ちても再開できるように毎回流す
                            executed += 1
                            # k を持たないアームでは k が None になる
                            shown_k = "-" if k is None else str(k)
                            print(
                                f"  [{executed:4d}] {arm_name} k={shown_k:<3} {mode:<10} "
                                f"r{repeat} {item.qid:<12} -> {out.answer[:40]!r}"
                                + ("  ⚠️" if out.error else "")
                            )

    meta["finished_at"] = datetime.now(UTC).isoformat()
    meta["executed_calls"] = executed
    (run_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    # ── 道具の使われ方の検証（SPEC §4-2）────────────────────────
    # ★ 検査の向きはアームごとに違う。
    #     道具を使わないアーム（Arm A）で道具が結果を返した
    #       → 定義が破れている。測定として無効
    #     道具を使うアーム（Arm B）で一度も返っていない
    #       → 道具が渡っていない。設定ミス
    #   どちらも黙って通すと、後から数字だけ見ても気づけない。
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines() if line]
    print()
    for arm_name in arm_names:
        mine = [r for r in rows if r["arm"] == arm_name]
        if not mine:
            continue
        returned = sum(r.get("tool_results", 0) for r in mine)
        expects_tools = getattr(ARMS[arm_name], "uses_tools", False)
        if expects_tools and returned == 0:
            print(f"⚠️  {arm_name}: 道具が一度も結果を返していない。設定ミスの疑い")
        elif not expects_tools and returned:
            print(f"⚠️  {arm_name}: 道具が {returned} 回結果を返した。定義が破れている")
        elif expects_tools:
            print(f"✅ {arm_name}: 道具が結果を返した回数 {returned}（道具を使うアーム）")
        else:
            print(f"✅ {arm_name}: 道具が結果を返した回数 0（道具なしで動作した）")
    print(f"完了: {executed} 回実行 → {raw_path}")
    print(f"採点: uv run python -m eval.score --run {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
