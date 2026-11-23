"""ChatSorter client for Nova: long-term memory via the ChatSorter API (hosted or self-hosted).

Setup
    Set your key in the environment:   CHATSORTER_API_KEY=your_key   (never put it in config.json)

Everything here fails soft: if ChatSorter is down or misconfigured, Nova just carries on
with her built-in memory.
"""

import os
import requests
from .config import CONFIG

TIMEOUT = 8


def enabled() -> bool:
    return bool(CONFIG.get("chatsorter_enabled")) and bool(os.environ.get("CHATSORTER_API_KEY"))


def _url(path: str) -> str:
    return CONFIG.get("chatsorter_url", "https://api.chatsorter.com").rstrip("/") + path


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get('CHATSORTER_API_KEY', '')}",
            "Content-Type": "application/json"}


def _ids() -> dict:
    cid = CONFIG.get("chatsorter_chat_id", "nova_main")
    return {"chat_id": cid, "user_id": cid}


def store(role: str, text: str):
    if not enabled() or not (text or "").strip():
        return
    try:
        requests.post(_url("/process"), headers=_headers(), timeout=TIMEOUT,
                      json={**_ids(), "message": text[:4000], "role": role})
    except requests.RequestException as e:
        print(f"[chatsorter] store failed: {e}")


def recall(query: str, k: int = 6) -> list:
    if not enabled() or not (query or "").strip():
        return []
    try:
        r = requests.post(_url("/search"), headers=_headers(), timeout=TIMEOUT,
                          json={**_ids(), "query": query[:1000], "max_memories": k})
        r.raise_for_status()
        data = r.json()
        mems = data.get("memories") or data.get("retrieved_memories") or []
        return [m["summary"] for m in mems if isinstance(m, dict) and m.get("summary")][:k]
    except (requests.RequestException, ValueError) as e:
        print(f"[chatsorter] recall failed: {e}")
        return []
