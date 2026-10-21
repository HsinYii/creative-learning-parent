import os
import re
from pathlib import Path
import httpx
import numpy as np
from rank_bm25 import BM25Okapi

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")


def embed(texts: list[str]) -> np.ndarray:
    # 用 httpx.post 呼叫 /api/embed（timeout 設 120）
    response = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120
    )
    response.raise_for_status()
    # 把回傳的 embeddings 轉成 np.array
    embeddings = np.array(response.json()["embeddings"])
    # 每一列除以自己的長度做正規化（np.linalg.norm(..., axis=1, keepdims=True)）
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / norms


DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")) / "parent"


def load_chunks() -> list[dict]:
    chunks = []
    for path in sorted(DATA_DIR.glob("*.md")):
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            # 遇到 "### " 開頭 → 把 current 存進 chunks，開新的 current
            if line.startswith("### "):
                if current:
                    chunks.append(current)
                pid, _, title = line[4:].partition(" ")
                current = {"id": pid, "title": title, "text": ""}
            # 遇到 "#" 開頭的其他標題 → 跳過
            elif line.startswith("#"):
                continue
            # 一般內文且 current 存在 → 接到 current["text"]
            elif current:
                current["text"] += line + "\n"   
        # 檔案結束時別忘了存最後一塊
        if current:
            chunks.append(current)

        # 去掉每塊內文前後多餘的換行
    for c in chunks:
        c["text"] = c["text"].strip()
    return chunks

#### 建立索引 ####
_index: tuple[list[dict], np.ndarray] | None = None

def get_index() -> tuple[list[dict], np.ndarray]:
    global _index
    if _index is None:
        chunks = load_chunks()
        if not chunks:
            raise RuntimeError(f"在 {DATA_DIR} 找不到任何切塊，請檢查 DATA_DIR")
        # 用標題 + 內文（2-3 的選擇）
        vecs = embed([c["title"] + "\n" + c["text"] for c in chunks])
        _index = (chunks, vecs)
    return _index

# 連續的中文字，或連續的英數字（標點、空白會被當成分隔）
_SEGMENT = re.compile(r"[一-鿿]+|[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    # 中文用字元二元組（bigram）：「請假期間」→ 請假、假期、期間
    # 不需要詞典，不會像 jieba 把「請假期間」斷成「請／假期／間」
    tokens = []
    for seg in _SEGMENT.findall(text):
        if seg.isascii():
            tokens.append(seg.lower())
        elif len(seg) == 1:
            tokens.append(seg)
        else:
            tokens += [seg[i:i + 2] for i in range(len(seg) - 1)]
    return tokens

_bm25: BM25Okapi | None = None


def get_bm25() -> BM25Okapi:
    global _bm25
    if _bm25 is None:
        chunks, _ = get_index()
        # 每塊用「標題 + 內文」斷詞（和向量版本用同樣的文字，比較公平）
        tokenized_chunks = [tokenize(c["title"] + "\n" + c["text"]) for c in chunks]
        _bm25 = BM25Okapi(tokenized_chunks)
    return _bm25


#### 檢索 ####
RAG_VERSION = os.environ.get("RAG_VERSION", "A")


def to_ranks(scores: np.ndarray) -> np.ndarray:
    """把分數轉成名次：分數最高的是 0，第二高的是 1……"""
    order = np.argsort(-scores)
    ranks = np.empty(len(scores), dtype=int)
    ranks[order] = np.arange(len(scores))
    return ranks


def search(query: str, k: int = 3, version: str = RAG_VERSION) -> list[dict]:
    chunks, vecs = get_index()
    q = embed([query])[0]
    dense = vecs @ q                      # 向量分數（版本 A 原本的 scores）

    if version == "B":
        bm25 = get_bm25().get_scores(tokenize(query))   # 33 個 BM25 分數
        # BM25 為 0 代表沒有任何詞比對到，名次沒有意義，不給 BM25 的分數
        bm25_part = np.where(bm25 > 0, 1 / (60 + to_ranks(bm25) + 1), 0.0)
        scores = 1 / (60 + to_ranks(dense) + 1) + bm25_part
    else:
        scores = dense

    top = np.argsort(-scores)[:k]
    return [{**chunks[i], "score": float(scores[i])} for i in top]

# if __name__ == "__main__":
#     chunks, vecs = get_index()
#     print(vecs.shape)
#     for c, v in zip(chunks, vecs):
#         print(c["id"], c["title"], repr(c["text"][:40]), v[:4])

if __name__ == "__main__":
    qs = ["小孩發燒要怎麼請假", "段考那天請假怎麼辦", "孩子在學校被欺負", "我孩子昨天說他不想活了"]
    for q in qs:
        print(q)
        for v in ["A", "B"]:
            ids = [r["id"] for r in search(q, version=v)]
            print(f"  {v}: {ids}")

