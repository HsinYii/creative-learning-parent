import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")) / "parent"


def load_chunks() -> list[dict]:
    chunks = []
    for path in sorted(DATA_DIR.glob("*.md")):
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            # TODO: 遇到 "### " 開頭 → 把 current 存進 chunks，開新的 current
            if line.startswith("### "):
                if current:
                    chunks.append(current)
                #current = {"id": line[4:].strip(), "title": line[4:].strip(), "text": ""}\
                pid, _, title = line[4:].partition(" ")
                current = {"id": pid, "title": title, "text": ""}
            # TODO: 遇到 "#" 開頭的其他標題 → 跳過
            elif line.startswith("#"):
                continue
            # TODO: 一般內文且 current 存在 → 接到 current["text"]
            elif current:
                current["text"] += line + "\n"
            
        # TODO: 檔案結束時別忘了存最後一塊
        if current:
            chunks.append(current)
    return chunks


if __name__ == "__main__":
    for c in load_chunks():
        print(c["id"], c["title"], len(c["text"]))