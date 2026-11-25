"""Nova's memory: what she knows about you, things she has learned, and the conversation so far.

memory.json layout
  history        full recent chat (also used to redraw the UI after a restart)
  summary        rolling summary of older messages that fell out of the context window
  user_facts     {key: value} things Nova knows about you - always in her prompt
  notes          things she learned (from you, files or the web) - recalled when relevant
  files          the files you've shared with her
  version_history  log of skills she taught herself
"""

import math
import re
import threading
import time

from .config import MEMORY_FILE, CONFIG, load_json, save_json

DEFAULT_MEMORY = {
    "history": [],
    "summary": "",
    "summary_upto": 0,
    "user_facts": {},
    "notes": [],
    "files": [],
    "version_history": [],
    "next_id": 1,
}

STOP = set("""the and for are but not you your yours with that this have has had was were will would can could
should what when where which who whom how why from they them their there then than into about just like
also been being its it's i'm i've i'll don't doesn't isn't really very some any all out our let get got
please thanks thank hey hello yeah yes okay""".split())

MAX_FACTS = 80
MAX_NOTES = 300

def tokens(text: str) -> list:
    return [w for w in re.findall(r"[a-z0-9']{3,}", (text or "").lower()) if w not in STOP]


def norm_key(key: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", str(key).strip().lower()).strip("_")
    return k[:40]


class Memory:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = load_json(MEMORY_FILE, DEFAULT_MEMORY)
        self._migrate()

    def _migrate(self):
        d = self.data
        for k, v in DEFAULT_MEMORY.items():
            d.setdefault(k, type(v)() if isinstance(v, (list, dict)) else v)
        if not isinstance(d["user_facts"], dict):
            d["user_facts"] = {}
        top = max([m.get("id", 0) for m in d["history"]] + [0])
        for m in d["history"]:
            if "id" not in m:
                top += 1
                m["id"] = top
            m.setdefault("ts", time.time())
        d["next_id"] = max(d.get("next_id", 1), top + 1)
        d["files"] = [f for f in d["files"]
                      if isinstance(f, dict) and all(k in f for k in ("id", "name", "kind", "path"))]
        for n in d["notes"]:
            n.setdefault("id", self._take_id())
        self.save()

    def _take_id(self) -> int:
        i = self.data["next_id"]
        self.data["next_id"] = i + 1
        return i

    def save(self):
        with self.lock:
            save_json(MEMORY_FILE, self.data)

    def add_exchange(self, user_text: str, reply: str, file_names=None):
        with self.lock:
            now = time.time()
            self.data["history"].append({"id": self._take_id(), "role": "user", "content": user_text,
                                         "ts": now, "files": list(file_names or [])})
            self.data["history"].append({"id": self._take_id(), "role": "assistant", "content": reply, "ts": now})
            self.data["history"] = self.data["history"][-300:]
            self.save()

    def _window_start(self) -> int:
        h = self.data["history"]
        n = max(2, int(CONFIG["max_history_messages"]))
        if len(h) <= n:
            return 0
        start = ((len(h) - n) // 4 + 1) * 4
        start = min(start, len(h))
        while start < len(h) and h[start]["role"] != "user":
            start += 1
        return start

    def recent(self) -> list:
        h = self.data["history"]
        return [{"role": m["role"], "content": m["content"]} for m in h[self._window_start():]]

    def pending_summary_batch(self):
        with self.lock:
            h = self.data["history"]
            out = [m for m in h[:self._window_start()] if m["id"] > self.data["summary_upto"]]
            return out if len(out) >= 8 else None

    def set_summary(self, text: str, upto_id: int):
        with self.lock:
            self.data["summary"] = text.strip()[:1800]
            self.data["summary_upto"] = upto_id
            self.save()

    def clear_history(self):
        with self.lock:
            self.data["history"] = []
            self.data["summary"] = ""
            self.data["summary_upto"] = 0
            self.save()

    def ui_history(self, limit=60) -> list:
        return [{"role": m["role"], "content": m["content"], "files": m.get("files", [])}
                for m in self.data["history"][-limit:]]

    def set_fact(self, key: str, value: str) -> bool:
        key, value = norm_key(key), str(value).strip()[:160]
        if not key or not value:
            return False
        with self.lock:
            facts = self.data["user_facts"]
            if key not in facts and len(facts) >= MAX_FACTS:
                facts.pop(next(iter(facts)))
            facts[key] = value
            self.save()
        return True

    def forget_fact(self, key: str) -> bool:
        key = norm_key(key)
        with self.lock:
            if key in self.data["user_facts"]:
                del self.data["user_facts"][key]
                self.save()
                return True
        return False

    def facts_text(self) -> str:
        facts = self.data["user_facts"]
        if not facts:
            return "(nothing yet - get to know them naturally)"
        return "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items())

    def add_note(self, text: str, kind: str = "note", source: str = "") -> int:
        text = " ".join(str(text).split())[:700]
        if not text:
            return 0
        with self.lock:
            notes = self.data["notes"]
            for n in notes:
                if n["text"].lower() == text.lower():
                    return n["id"]
            nid = self._take_id()
            notes.append({"id": nid, "kind": kind, "text": text, "source": source, "ts": time.time()})
            if len(notes) > MAX_NOTES:
                del notes[0]
            self.save()
            return nid

    def forget_note(self, nid: int) -> bool:
        with self.lock:
            before = len(self.data["notes"])
            self.data["notes"] = [n for n in self.data["notes"] if n["id"] != nid]
            if len(self.data["notes"]) != before:
                self.save()
                return True
        return False

    def retrieve(self, query: str, k: int = 4) -> list:
        q = set(tokens(query))
        if not q:
            return []
        now = time.time()
        scored = []
        for n in self.data["notes"]:
            t = tokens(n["text"])
            if not t:
                continue
            overlap = len(q & set(t))
            if not overlap:
                continue
            age_days = (now - n.get("ts", now)) / 86400
            score = overlap / math.sqrt(len(t)) * (1.0 / (1.0 + age_days / 60))
            scored.append((score, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored[:k]]

    def add_file(self, rec: dict):
        with self.lock:
            self.data["files"] = [f for f in self.data["files"] if f["id"] != rec["id"]]
            self.data["files"].append(rec)
            self.data["files"] = self.data["files"][-40:]
            self.save()

    def get_file(self, ref: str):
        ref = (ref or "").strip().lower()
        if not ref:
            return None
        for f in reversed(self.data["files"]):
            if f["id"] == ref or f["name"].lower() == ref:
                return f
        for f in reversed(self.data["files"]):
            if ref in f["name"].lower():
                return f
        return None

    def files_summary(self, n=6) -> str:
        fs = self.data["files"][-n:]
        if not fs:
            return ""
        lines = []
        for f in fs:
            cap = f" - {f['caption']}" if f.get("caption") else ""
            lines.append(f"- {f['name']} ({f['kind']}){cap}")
        return "\n".join(lines)


MEM = Memory()
