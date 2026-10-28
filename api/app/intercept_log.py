"""高風險攔截紀錄（spec/api-contract.md 家長 AI 幫手：時間、session_id、類別、原始訊息）。

一行一筆 JSON，寫在 INTERCEPT_LOG（預設 logs/interceptions.jsonl）。
"""

import json
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .schemas import Guardrail

LOG_PATH = Path(os.environ.get("INTERCEPT_LOG", "logs/interceptions.jsonl"))
TW = timezone(timedelta(hours=8))

_lock = threading.Lock()


def record(session_id: str, message: str, guardrail: Guardrail) -> None:
    entry = {
        "time": datetime.now(TW).isoformat(timespec="seconds"),
        "session_id": session_id,
        "category": guardrail.category,
        "action": guardrail.action,
        "message": message,
    }
    with _lock:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_all() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    with _lock:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
