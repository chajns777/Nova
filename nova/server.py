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
import ipaddress

from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from . import agent, files as filelib, tools
from .config import CONFIG, UI_DIR, save_config
from .llm import LLM_
from .memory import MEM

TOKEN = secrets.token_urlsafe(24)
SETTINGS_TYPES = {"name": str, "speaking_style": str, "model": str, "vision_model": str,
                  "web_enabled": bool, "auto_learn": bool}

STATIC_ASSETS = {
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
}

SAFE_UPLOAD_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}

class Handler(BaseHTTPRequestHandler):
    server_version = "Nova"
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(60)

    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _body(self, limit=1_000_000) -> bytes:
        raw = self.headers.get("Content-Length")
        if raw is None:
            raise ValueError("missing content length")
        if not raw.isdigit():
            raise ValueError("invalid content length")
        n = int(raw)
        if n < 0 or n > limit:
            raise ValueError("too large")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("transfer encoding is not supported")
        data = self.rfile.read(n) if n else b""
        if len(data) != n:
            raise ValueError("incomplete request body")
        return data

    def _read_json(self) -> dict:
        try:
            data = json.loads(self._body() or b"{}")
            return data if isinstance(data, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def _host_ok(self) -> bool:
        expected_port = self.server.server_address[1]
        host_header = (self.headers.get("Host") or "").strip()
        try:
            parsed = urlparse("http://" + host_header)
            host = (parsed.hostname or "").lower()
            if host not in ("127.0.0.1", "localhost"):
                return False
            if parsed.username or parsed.password or parsed.path not in ("", "/"):
                return False
            if parsed.port != expected_port:
                return False
        except ValueError:
            return False

        origin = self.headers.get("Origin")
        if origin:
            try:
                o = urlparse(origin)
                if (o.scheme != "http" or (o.hostname or "").lower() not in ("127.0.0.1", "localhost")
                        or o.port != expected_port or o.username or o.password
                        or o.path not in ("", "/") or o.query or o.fragment):
                    return False
            except ValueError:
                return False
        return True

    def _authed(self, query) -> bool:
        tok = self.headers.get("X-Nova-Token") or (query.get("t") or [""])[0]
        if not tok and self.headers.get("Cookie"):
            try:
                cookie = SimpleCookie()
                cookie.load(self.headers["Cookie"])
                if "nova_session" in cookie:
                    tok = cookie["nova_session"].value
            except Exception:
                return False
        return bool(tok) and secrets.compare_digest(tok, TOKEN)

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
        path = url.path
        q = parse_qs(url.query)
        if path in ("/", "/index.html"):
            if not self._authed(q):
                return self._json({"error": "unauthorised"}, 401)
            with open(os.path.join(UI_DIR, "index.html"), "r", encoding="utf-8") as f:
                html = f.read()
            body = html.replace("__NOVA_TOKEN__", TOKEN).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Set-Cookie", f"nova_session={TOKEN}; HttpOnly; SameSite=Strict; Path=/")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in STATIC_ASSETS:
            filename, content_type = STATIC_ASSETS[path]
            fp = os.path.join(UI_DIR, filename)
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
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
                fp = filelib._assert_within_upload_dir(fp)
                with open(fp, "rb") as f:
                    body = f.read(50 * 1024 * 1024 + 1)
                if len(body) > 50 * 1024 * 1024:
                    return self._json({"error": "file too large"}, 413)
            except OSError:
                return self._json({"error": "gone"}, 404)
            ext = os.path.splitext(fp)[1].lower()
            content_type = SAFE_UPLOAD_MIMES.get(ext, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("X-Content-Type-Options", "nosniff")
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
            if not self.server.upload_slots.acquire(blocking=False):
                return self._json({"error": "another upload is being processed; try again shortly"}, 429)
            try:
                name = unquote((q.get("name") or ["file"])[0])[:240]
                try:
                    data = self._body(filelib.MAX_UPLOAD_BYTES)
                except ValueError as exc:
                    return self._json({"error": f"Upload rejected: {str(exc)[:160]} (limit {filelib.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."}, 413)
                if not data:
                    return self._json({"error": "empty file"}, 400)
                try:
                    rec = filelib.ingest(data, name)
                    MEM.add_file(rec)
                except (ValueError, OSError) as exc:
                    return self._json({"error": str(exc)[:240]}, 400)
                return self._json({k: rec[k] for k in ("id", "name", "kind", "size", "chars", "note", "check")})
            finally:
                self.server.upload_slots.release()

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
                    if k in ("name", "model", "vision_model"):
                        val = val[:120]
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
                try:
                    MEM.forget_note(int(data.get("id", 0)))
                except (TypeError, ValueError, OverflowError):
                    return self._json({"error": "invalid note id"}, 400)
            elif kind == "history":
                MEM.clear_history()
            return self._json({"ok": True})

        if path == "/api/skills/rollback":
            try:
                idx = int(self._read_json().get("index", 1))
            except (TypeError, ValueError, OverflowError):
                return self._json({"error": "invalid backup index"}, 400)
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
    request_queue_size = 16

    def __init__(self, port=0, chrome="native"):
        super().__init__(("127.0.0.1", port), Handler)
        self.last_ping = None
        self.bye_at = None
        self.chrome = chrome
        self.upload_slots = threading.BoundedSemaphore(2)
        self.request_slots = threading.BoundedSemaphore(32)

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()

    def watch_for_close(self):
        while True:
            time.sleep(1)
            now = time.time()
            if self.bye_at and now - self.bye_at > 6:
                break
            if self.last_ping and now - self.last_ping > 300:
                break
        self.shutdown()
