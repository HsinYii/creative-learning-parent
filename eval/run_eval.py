"""評測集：比較版本 A、B 的檢索命中，輸出報告第 4 節的表格。

直接呼叫 retriever.search()，不經過 /chat，不需要 Docker；需要主機的 Ollama 有 bge-m3。

用法（repo 根目錄）：
    python eval/run_eval.py
    python eval/run_eval.py --k 3 --out docs/results/eval-AB.md

命中的定義：Top-K 中至少有一個「應命中」段落。
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# retriever 在 import 時就讀 DATA_DIR，要先設定
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
sys.path.insert(0, str(ROOT))

from api.app.retriever import search  # noqa: E402

VERSIONS = ("A", "B")


def evaluate(items: list[dict], k: int) -> list[dict]:
    rows = []
    for item in items:
        row = {**item}
        for v in VERSIONS:
            ids = [r["id"] for r in search(item["question"], k=k, version=v)]
            # 第一個應命中段落的名次（1 起算），沒命中為 None
            rank = next((i + 1 for i, pid in enumerate(ids) if pid in item["expected"]), None)
            row[v] = {"ids": ids, "rank": rank}
        rows.append(row)
    return rows


def summarize(rows: list[dict], v: str) -> dict:
    n = len(rows)
    ranks = [r[v]["rank"] for r in rows]
    return {
        "hit": sum(rk is not None for rk in ranks) / n,
        "hit1": sum(rk == 1 for rk in ranks) / n,
        "mrr": sum(1 / rk for rk in ranks if rk) / n,
    }


def to_markdown(rows: list[dict], k: int) -> str:
    lines = [
        f"| # | 問題 | 類型 | 應命中 | 版本 A 實際命中（Top-{k}） | A 命中？ | 版本 B 實際命中（Top-{k}） | B 命中？ |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        cells = [str(i), r["question"], r["type"], ", ".join(r["expected"])]
        for v in VERSIONS:
            cells += [", ".join(r[v]["ids"]), "✅" if r[v]["rank"] else "❌"]
        lines.append("| " + " | ".join(cells) + " |")

    stats = {v: summarize(rows, v) for v in VERSIONS}
    n = len(rows)
    lines += [
        "",
        "| | 版本 A | 版本 B |",
        "| --- | --- | --- |",
        f"| 命中率（hit@{k}） | " + " | ".join(
            f"{stats[v]['hit']:.2f}（{round(stats[v]['hit'] * n)}/{n}）" for v in VERSIONS) + " |",
        "| hit@1 | " + " | ".join(f"{stats[v]['hit1']:.2f}" for v in VERSIONS) + " |",
        "| MRR | " + " | ".join(f"{stats[v]['mrr']:.3f}" for v in VERSIONS) + " |",
    ]

    # 失敗案例候選：任一版本沒命中，或 A、B 排名不同
    misses = [r for r in rows if not all(r[v]["rank"] for v in VERSIONS)]
    if misses:
        lines += ["", "失敗案例候選（至少一個版本沒命中）：", ""]
        for r in misses:
            lines.append(f"- {r['id']} {r['question']}：應命中 {', '.join(r['expected'])}；"
                         + "；".join(f"{v}={', '.join(r[v]['ids'])}" for v in VERSIONS))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default=str(ROOT / "eval" / "eval_set.jsonl"))
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--out", default=str(ROOT / "docs" / "results" / "eval-AB.md"))
    args = parser.parse_args()

    items = [json.loads(line) for line in Path(args.set).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = evaluate(items, args.k)
    md = to_markdown(rows, args.k)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 終端機預設 cp950，印不出 ✅
    print(md)
    print(f"已存檔：{out}、{out.with_suffix('.json')}")


if __name__ == "__main__":
    main()
