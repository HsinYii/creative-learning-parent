import os
from pathlib import Path
import httpx
import numpy as np

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

#### 檢索 ####
def search(query: str, k: int = 3) -> list[dict]:
    chunks, vecs = get_index()
    # 問題embedding，取第一列 (問題也轉成 1024 個數字，形狀 (1024,))
    q = embed([query])[0]
    # 問題和每個切塊的相似度(已正規化，內積就是 cosine 相似度)
    scores = vecs @ q
    # 分數由高到低，取前 k 個的索引
    top = np.argsort(-scores)[:k]
    # 回傳 [{"id", "title", "text", "score"} ...]
    return [ {**chunks[i], "score": float(scores[i])} for i in top ]

# if __name__ == "__main__":
#     chunks, vecs = get_index()
#     print(vecs.shape)
#     for c, v in zip(chunks, vecs):
#         print(c["id"], c["title"], repr(c["text"][:40]), v[:4])

if __name__ == "__main__":
    for q in ["小孩發燒要怎麼請假", "段考那天請假怎麼辦", "孩子在學校被欺負"]:
        print(q)
        for r in search(q):
            print(f"  {r['id']} {r['title']} {r['score']:.3f}")

