"""失敗案例驗證：版本 B 的兩個假設。不改 retriever.py，只在這裡重算分數。

1. 平手（tie）：向量與 BM25 的第 1、2 名互換時，RRF 分數完全相同，名次由 argsort 任意決定。
   驗證：加上極小的向量分數當 tie-break，看 E02、E04 是否回到第 1。
2. 常見詞（stop）：「孩子」「可以」等詞讓無關段落拿到 BM25 分數。
   驗證：BM25 斷詞時去掉這些詞，看 E07、E08 是否改善。

用法（repo 根目錄）：
    python eval/exp_b_variants.py
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
sys.path.insert(0, str(ROOT))

from api.app.retriever import embed, get_index, to_ranks, tokenize  # noqa: E402

K = 3
# 家長提問常見、但不帶主題的 bigram
STOPWORDS = {"孩子", "可以", "什麼", "怎麼", "請問", "需要", "要怎"}


def build_bm25(chunks: list[dict], stop: bool) -> BM25Okapi:
    docs = [tokenize(c["title"] + "\n" + c["text"]) for c in chunks]
    if stop:
        docs = [[t for t in d if t not in STOPWORDS] for d in docs]
    return BM25Okapi(docs)


def scores_b(dense: np.ndarray, bm25: np.ndarray, tiebreak: bool) -> np.ndarray:
    # 與 retriever.search() 版本 B 相同的 RRF（k=60，BM25 為 0 不計分）
    bm25_part = np.where(bm25 > 0, 1 / (60 + to_ranks(bm25) + 1), 0.0)
    scores = 1 / (60 + to_ranks(dense) + 1) + bm25_part
    if tiebreak:
        scores = scores + 1e-6 * dense  # 遠小於 RRF 名次間距，只在平手時起作用
    return scores


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    items = [json.loads(line) for line in (ROOT / "eval" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    chunks, vecs = get_index()
    ids = [c["id"] for c in chunks]
    bm25 = {stop: build_bm25(chunks, stop) for stop in (False, True)}

    variants = {
        "A（向量）": None,
        "B（現行）": (False, False),
        "B + tie-break": (False, True),
        "B + 停用詞": (True, False),
        "B + 停用詞 + tie-break": (True, True),
    }
    ranks = {name: [] for name in variants}
    tops = {name: {} for name in variants}

    for item in items:
        q = item["question"]
        dense = vecs @ embed([q])[0]
        for name, opt in variants.items():
            if opt is None:
                s = dense
            else:
                stop, tiebreak = opt
                qt = [t for t in tokenize(q) if not (stop and t in STOPWORDS)]
                s = scores_b(dense, bm25[stop].get_scores(qt), tiebreak)
            top = [ids[i] for i in np.argsort(-s)[:K]]
            tops[name][item["id"]] = top
            ranks[name].append(next((i + 1 for i, pid in enumerate(top) if pid in item["expected"]), None))

    n = len(items)
    print(f"| 版本 | hit@{K} | hit@1 | MRR |")
    print("| --- | --- | --- | --- |")
    for name, rk in ranks.items():
        hit = sum(r is not None for r in rk)
        hit1 = sum(r == 1 for r in rk)
        mrr = sum(1 / r for r in rk if r) / n
        print(f"| {name} | {hit / n:.2f}（{hit}/{n}） | {hit1 / n:.2f}（{hit1}/{n}） | {mrr:.3f} |")

    print("\n關注的題目（Top-3）：")
    for qid in ("E02", "E04", "E07", "E08", "E20"):
        print(f"\n{qid}")
        for name in variants:
            print(f"  {name}: {', '.join(tops[name][qid])}")


if __name__ == "__main__":
    main()
