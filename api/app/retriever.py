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
    return chunks


if __name__ == "__main__":
    chunks = load_chunks()
    vecs = embed([c["title"] + "\n" + c["text"] for c in chunks])
    print(vecs.shape)                    # 應該是 (33, 1024)
    print(np.linalg.norm(vecs, axis=1)[:3])  # 正規化後應該都是 1.0