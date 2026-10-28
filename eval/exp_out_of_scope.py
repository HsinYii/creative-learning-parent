"""失敗案例驗證：答案不在教材中時，模型會不會把別的段落套用到問題上。

問題「校外教學要繳多少錢？」：教材完全沒有校外教學的費用，
但版本 A 的 Top-3 含 P3-3-1（課後輔導「每學期收費依教育局規定辦理」）。
假設：模型把課後輔導的收費規定當成校外教學的答案，而不是回答不知道。
驗證：同一個問題、同一段 system prompt，比較「原始 Top-3」與「拿掉 P3-3-1」各跑 N 次。

不經過 /chat，直接呼叫 Ollama；需要主機的 Ollama 有 bge-m3 與 qwen2.5:3b。

用法（repo 根目錄）：
    python eval/exp_out_of_scope.py
"""

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))
sys.path.insert(0, str(ROOT))

from api.app.retriever import get_index, search  # noqa: E402

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "qwen2.5:3b")
QUESTION = "校外教學要繳多少錢？"
N = 5
REFUSE = ("不知道", "找不到", "沒有提到", "沒有提及", "未提及", "沒有相關", "聯絡導師", "聯繫導師")


def ask(source_ids: list[str], texts: dict[str, str]) -> str:
    # 與 pipeline.handle() 相同的 system prompt（不含對話歷史）
    context = "\n\n".join(f"[{pid}] {texts[pid]}" for pid in source_ids)
    messages = [
        {"role": "system", "content": (
            "你是星河國中的家長 AI 幫手，請用繁體中文回答家長的問題。"
            "只根據下方參考資料回答，並在句尾用 [段落id] 標註出處，例如 [P2-1-1]。"
            "參考資料沒有提到的內容，請回答不知道，並建議家長聯絡導師。\n\n"
            f"參考資料：\n{context or '（無）'}"
        )},
        {"role": "user", "content": QUESTION},
    ]
    r = httpx.post(f"{OLLAMA_URL}/api/chat",
                   json={"model": LOCAL_MODEL, "messages": messages, "stream": False}, timeout=300)
    r.raise_for_status()
    return r.json()["message"]["content"]


def judge(answer: str) -> str:
    # 教材中只有 P3-3-1 提到「教育局規定」；出現代表回答引用了課後輔導的收費。
    # 是否明確說成「校外教學費用依教育局規定」，仍需人工判讀
    if "教育局" in answer or "課後輔導" in answer:
        return "引用 P3-3-1"
    if any(w in answer for w in REFUSE):
        return "回答不知道"
    return "其他（人工判讀）"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    chunks, _ = get_index()
    texts = {c["id"]: c["text"] for c in chunks}
    top = {v: [r["id"] for r in search(QUESTION, k=3, version=v)] for v in ("A", "B")}
    print(f"問題：{QUESTION}")
    for v, ids in top.items():
        print(f"版本 {v} Top-3：{', '.join(ids)}")

    conditions = {
        "原始 Top-3（版本 A）": top["A"],
        "拿掉 P3-3-1": [pid for pid in top["A"] if pid != "P3-3-1"],
    }
    results = {}
    for name, ids in conditions.items():
        print(f"\n## {name}：{', '.join(ids)}")
        runs = []
        for i in range(N):
            ans = ask(ids, texts)
            runs.append({"answer": ans, "judge": judge(ans)})
            print(f"{i + 1}. [{runs[-1]['judge']}] {ans}", flush=True)
        results[name] = {"sources": ids, "runs": runs}

    print("\n| 條件 | 參考資料 | 引用 P3-3-1 | 回答不知道 | 其他 |")
    print("| --- | --- | --- | --- | --- |")
    for name, r in results.items():
        cnt = [sum(x["judge"].startswith(j) for x in r["runs"]) for j in ("引用", "回答", "其他")]
        print(f"| {name} | {', '.join(r['sources'])} | " + " | ".join(f"{c}/{N}" for c in cnt) + " |")

    out = ROOT / "docs" / "results" / "eval-failure-out-of-scope.json"
    out.write_text(json.dumps({"question": QUESTION, "top3": top, "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已存檔：{out}")


if __name__ == "__main__":
    main()
