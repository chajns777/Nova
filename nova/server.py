# Copyright 2026 Chajns777
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tiny local web server that connects the UI to Nova's brain. Listens on 127.0.0.1 only and
requires a random per-launch token, so no website can talk to it."""

import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

from . import agent, files as filelib, tools
from .config import CONFIG, UI_DIR, save_config
from .llm import LLM_
from .memory import MEM

TOKEN = secrets.token_urlsafe(24)
SETTINGS_TYPES = {"name": str, "speaking_style": str, "model": str, "vision_model": str,
                  "web_enabled": bool, "auto_learn": bool}


class Handler(BaseHTTPRequestHandler):
    server_version = "Nova"
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=1_000_000) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("too large")
        return self.rfile.read(n) if n else b""

    def _read_json(self) -> dict:
        try:
            data = json.loads(self._body() or b"{}")
            return data if isinstance(data, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _authed(self, query) -> bool:
        tok = self.headers.get("X-Nova-Token") or (query.get("t") or [""])[0]
        return secrets.compare_digest(tok, TOKEN)

    def _sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def _sse(self, obj) -> bool:
        try:
            self.wfile.write(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            agent.CANCEL.set()
            return False

    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "bad host"}, 403)
        url = urlparse(self.path)
        q = parse_qs(url.query)
        path = url.path

        if path in ("/", "/index.html"):
            html = open(os.path.join(UI_DIR, "index.html"), "r", encoding="utf-8").read()
            body = html.replace("__NOVA_TOKEN__", TOKEN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/style.css", "/app.js", "/logo.svg"):
            fp = os.path.join(UI_DIR, path.lstrip("/"))
            body = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(fp)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if not path.startswith("/api/") or not self._authed(q):
            return self._json({"error": "unauthorised"}, 401)

        if path == "/api/state":
            return self._json(self.state())
        if path == "/api/memory":
            return self._json({"facts": MEM.data["user_facts"], "notes": MEM.data["notes"][-60:],
                               "summary": MEM.data.get("summary", "")})
        if path == "/api/skills":
            return self._json({"builtin": tools.CORE_HELP, "learned": tools.skills_info(),
                               "backups": tools.list_backups(), "code": tools.read_my_tools()})
        if path == "/api/models":
            return self._json({"installed": LLM_.installed()})
        if path == "/api/files":
            return self._json({"files": [{k: f[k] for k in ("id", "name", "kind", "size")} for f in MEM.data["files"]]})
        if path.startswith("/api/file/"):
            rec = MEM.get_file(unquote(path[len("/api/file/"):]))
            if not rec:
                return self._json({"error": "not found"}, 404)
            fp = (rec.get("images") or [rec["path"]])[0] if rec["kind"] == "image" else rec["path"]
            try:
                body = open(fp, "rb").read()
            except OSError:
                return self._json({"error": "gone"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(fp)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._host_ok():
            return self._json({"error": "bad host"}, 403)
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self._authed(q):
            return self._json({"error": "unauthorised"}, 401)
        path = url.path

        if path == "/api/ping":
            self.server.last_ping, self.server.bye_at = time.time(), None
            return self._json({"ok": True})
        if path == "/api/bye":
            self.server.bye_at = time.time()
            return self._json({"ok": True})

        if path == "/api/chat":
            data = self._read_json()
            text = str(data.get("message", "")).strip()
            file_ids = [str(i) for i in data.get("files", [])][:6]
            if not text and not file_ids:
                return self._json({"error": "empty"}, 400)
            if not agent.TURN_LOCK.acquire(blocking=False):
                return self._json({"error": "busy"}, 409)
            try:
                self._sse_start()
                agent.run_turn(text or "Have a look at what I've shared.", file_ids, self._sse)
            finally:
                agent.TURN_LOCK.release()
            return

        if path == "/api/stop":
            agent.CANCEL.set()
            return self._json({"ok": True})

        if path == "/api/upload":
            name = unquote((q.get("name") or ["file"])[0])
            try:
                data = self._body(filelib.MAX_UPLOAD_BYTES)
            except ValueError:
                return self._json({"error": "That file is too big (limit 300 MB)."}, 413)
            if not data:
                return self._json({"error": "empty file"}, 400)
            rec = filelib.ingest(data, name)
            MEM.add_file(rec)
            return self._json({k: rec[k] for k in ("id", "name", "kind", "size", "chars", "note", "check")})

        if path == "/api/settings":
            data = self._read_json()
            changed_model = False
            for k, typ in SETTINGS_TYPES.items():
                if k in data and isinstance(data[k], typ):
                    val = data[k].strip() if typ is str else data[k]
                    if k == "name" and not val:
                        continue
                    if k in ("model",) and not val:
                        continue
                    if k == "speaking_style":
                        val = val[:300]
                    if k == "model" and val != CONFIG["model"]:
                        changed_model = True
                    CONFIG[k] = val
            save_config()
            if changed_model:
                LLM_.state = "loading"
                threading.Thread(target=LLM_.warmup, daemon=True).start()
            return self._json(self.state())

        if path == "/api/memory/forget":
            data = self._read_json()
            kind = data.get("kind")
            if kind == "fact":
                MEM.forget_fact(str(data.get("key", "")))
            elif kind == "note":
                MEM.forget_note(int(data.get("id", 0)))
            elif kind == "history":
                MEM.clear_history()
            return self._json({"ok": True})

        if path == "/api/skills/rollback":
            idx = int(self._read_json().get("index", 1))
            return self._json({"message": tools.rollback(idx)})

        if path == "/api/pull":
            return self._json(LLM_.start_pull(str(self._read_json().get("model", ""))))

        return self._json({"error": "not found"}, 404)

    def state(self) -> dict:
        up = LLM_.ping() if LLM_.state in ("offline", "missing", "starting") else True
        return {
            "name": CONFIG["name"], "model": CONFIG["model"], "vision_model": CONFIG.get("vision_model", ""),
            "style": CONFIG["speaking_style"], "web_enabled": CONFIG.get("web_enabled", True),
            "auto_learn": CONFIG.get("auto_learn", True),
            "status": LLM_.state if up else "offline", "can_see": LLM_.can_see() if up and LLM_.state == "ready" else None,
            "tps": LLM_.last_stats.get("tps"), "busy": agent.BUSY.is_set(),
            "history": MEM.ui_history(), "facts": len(MEM.data["user_facts"]), "notes": len(MEM.data["notes"]),
            "skills": len(tools.LEARNED), "installed": LLM_.installed() if up else [],
            "chrome": self.server.chrome, "pull": dict(LLM_.pull_state),
        }


class NovaServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port=0, chrome="native"):
        super().__init__(("127.0.0.1", port), Handler)
        self.last_ping = None
        self.bye_at = None
        self.chrome = chrome  

    def watch_for_close(self):
        while True:
            time.sleep(1)
            now = time.time()
            if self.bye_at and now - self.bye_at > 6:
                break
            if self.last_ping and now - self.last_ping > 300:
                break
        self.shutdown()
