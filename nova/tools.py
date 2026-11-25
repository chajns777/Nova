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

"""Nova's abilities.

Built-in tools (web, files, memory, code checking) plus *learned* tools: Python functions Nova writes
for herself. Learned tools are validated, tried out, and every update first backs up the previous
version so you can roll back (see backups/ and the Skills panel).
"""

import ast
import importlib.util
import inspect
import ipaddress
import os
import re
import shutil
import socket
import time

from urllib.parse import urlparse, parse_qs, unquote, urljoin
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.util import connection as urllib3_conn
from . import codecheck, files as filelib
from .config import (CONFIG, save_config, LEARNED_FILE, CANDIDATE_FILE, BACKUP_DIR, OUTPUT_DIR, MAX_BACKUPS)
from .llm import LLM_
from .memory import MEM, tokens

LEARNED = {}  


def _contained_path(root: str, candidate: str) -> str:
    root_real = os.path.realpath(root)
    candidate_real = os.path.realpath(candidate)
    try:
        if os.path.commonpath((root_real, candidate_real)) != root_real:
            raise ValueError("Path escapes its permitted directory.")
    except ValueError as exc:
        raise ValueError("Path escapes its permitted directory.") from exc
    return candidate_real


def save_output(filename: str, content: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        return "Error: filename cannot be empty."
    clean = filelib.safe_name(filename)
    target = _contained_path(OUTPUT_DIR, os.path.join(OUTPUT_DIR, clean))
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(content)[:300_000])
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        raise
    return f"SUCCESS: saved '{clean}' in 'output files/'."


HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}


def _is_global_ip(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return bool(ip.is_global and not (ip.is_private or ip.is_loopback or ip.is_link_local
                                          or ip.is_multicast or ip.is_reserved or ip.is_unspecified))
    except ValueError:
        return False


def _resolve_public_ip(url: str) -> str | None:
    """Resolve an HTTP(S) URL and reject it unless every answer is globally routable."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        host = parsed.hostname.rstrip(".").lower()
        if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal", ".test")):
            return None
        expected_port = 443 if parsed.scheme.lower() == "https" else 80
        port = parsed.port or expected_port
        if port != expected_port:
            return None
        try:
            literal = ipaddress.ip_address(host)
            ips = [str(literal)]
        except ValueError:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            ips = list(dict.fromkeys(info[4][0] for info in infos))
        if not ips or not all(_is_global_ip(ip) for ip in ips):
            return None
        return ips[0]
    except (ValueError, OSError, socket.gaierror):
        return None


class _PinnedIPAdapter(HTTPAdapter):
    """Connect to a previously validated IP while retaining URL host/TLS verification."""
    def __init__(self, pinned_ip: str, *args, **kwargs):
        self._pinned_ip = pinned_ip
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pinned_ip = self._pinned_ip

        class PinnedHTTPConnection(HTTPConnection):
            def _new_conn(self):
                return urllib3_conn.create_connection(
                    (pinned_ip, self.port), self.timeout,
                    source_address=self.source_address, socket_options=self.socket_options)

        class PinnedHTTPSConnection(HTTPSConnection):
            def _new_conn(self):
                return urllib3_conn.create_connection(
                    (pinned_ip, self.port), self.timeout,
                    source_address=self.source_address, socket_options=self.socket_options)

        class PinnedHTTPPool(HTTPConnectionPool):
            ConnectionCls = PinnedHTTPConnection

        class PinnedHTTPSPool(HTTPSConnectionPool):
            ConnectionCls = PinnedHTTPSConnection

        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)
        # Give THIS pool manager its own pool classes. Assigning ConnectionCls on the shared urllib3
        # classes would pin every other requests call in the process to this IP as well.
        self.poolmanager.pool_classes_by_scheme = {"http": PinnedHTTPPool, "https": PinnedHTTPSPool}


def _public_url(url: str) -> bool:
    return _resolve_public_ip(url) is not None


_search_cache = {}


def _fmt(results) -> str:
    return "\n".join(f"{i}. {t}\n   {s[:300]}\n   {u}" for i, (t, s, u) in enumerate(results, 1))[:3000]


def _search_ddgs(q):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return None, "ddgs not installed (pip install ddgs)"
    try:
        hits = DDGS().text(q, max_results=6)
        return [(h.get("title", ""), h.get("body", ""), h.get("href", "")) for h in hits], None
    except Exception as e:
        return None, f"ddgs error: {e}"


def _clean_ddg_url(href: str) -> str:
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    return href


def _search_ddg_html(q):
    try:
        res = requests.post("https://html.duckduckgo.com/html/", data={"q": q}, headers=HEADERS, timeout=(4, 10), allow_redirects=False)
    except Exception as e:
        return None, f"request failed: {e}"
    if res.status_code != 200 or "captcha" in res.text.lower() or "anomaly" in res.text.lower():
        return None, f"blocked (HTTP {res.status_code})"
    soup = BeautifulSoup(res.text, "html.parser")
    out = []
    for r in soup.select("div.result")[:6]:
        a, s = r.select_one("a.result__a"), r.select_one(".result__snippet")
        if a:
            out.append((a.get_text(strip=True), s.get_text(" ", strip=True) if s else "",
                        _clean_ddg_url(a.get("href", ""))))
    return (out or None), (None if out else "no results parsed")


def _search_wikipedia(q):
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", headers=HEADERS, timeout=(4, 10),
                         allow_redirects=False,
                         params={"action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 5})
        hits = r.json().get("query", {}).get("search", [])
        out = [(h["title"], re.sub(r"<[^>]+>", "", h.get("snippet", "")),
                "https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_")) for h in hits]
        return (out or None), (None if out else "no Wikipedia hits")
    except Exception as e:
        return None, f"wikipedia error: {e}"


def web_search(query: str) -> str:
    if not CONFIG.get("web_enabled", True):
        return "Web access is switched off in Settings."
    query = (query or "").strip()
    if not query:
        return "Error: empty query."
    hit = _search_cache.get(query.lower())
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    notes = []
    for name, fn in (("ddgs", _search_ddgs), ("duckduckgo", _search_ddg_html), ("wikipedia", _search_wikipedia)):
        results, err = fn(query)
        if results:
            out = f"[source: {name}]\n" + _fmt(results)
            _search_cache[query.lower()] = (time.time(), out)
            return out
        notes.append(f"{name}: {err or 'no results'}")
    return "SEARCH FAILED (" + " | ".join(notes) + "). Try different, simpler keywords."


def read_webpage(url: str) -> str:
    if not CONFIG.get("web_enabled", True):
        return "Web access is switched off in Settings."
    url = (url or "").strip()
    if len(url) > 4096:
        return "Error: URL is too long."
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        for _ in range(6):
            pinned_ip = _resolve_public_ip(url)
            if not pinned_ip:
                return "Error: that address isn't a public website, so I won't open it."
            with requests.Session() as sess:
                sess.trust_env = False
                adapter = _PinnedIPAdapter(pinned_ip, max_retries=0, pool_connections=1, pool_maxsize=1)
                sess.mount("http://", adapter)
                sess.mount("https://", adapter)
                with sess.get(url, headers=HEADERS, timeout=(4, 10), allow_redirects=False,
                              stream=True, verify=True) as res:
                    if res.is_redirect or res.is_permanent_redirect:
                        location = res.headers.get("location")
                        if not location:
                            return "Error: redirect had no destination."
                        url = urljoin(url, location)
                        continue
                    res.raise_for_status()
                    ctype = res.headers.get("content-type", "").lower()
                    if not any(t in ctype for t in ("html", "text", "json", "xml")):
                        return f"Can't read this kind of content ({ctype or 'unknown'})."
                    declared = res.headers.get("content-length")
                    if declared and int(declared) > 1_000_000:
                        return "Error: webpage is larger than the 1 MB reading limit."
                    raw_bytes = res.raw.read(1_000_001, decode_content=True)
                    if len(raw_bytes) > 1_000_000:
                        return "Error: webpage is larger than the 1 MB reading limit."
                    encoding = res.encoding or "utf-8"
                    raw = raw_bytes.decode(encoding, errors="replace")
                    if "html" not in ctype:
                        return raw[:5000]
                    soup = BeautifulSoup(raw, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
                        tag.decompose()
                    root = soup.find("article") or soup.find("main") or soup.body or soup
                    title = soup.title.get_text(strip=True) if soup.title else ""
                    text = re.sub(r"\s+", " ", root.get_text(" ", strip=True))
                    return (f"[{title}]\n" if title else "") + (text[:5000] or "The page had no readable text.")
        return "Error: too many redirects."
    except (requests.RequestException, OSError, ValueError) as e:
        return f"Error fetching page: {type(e).__name__}: {str(e)[:240]}"


def save_knowledge(topic: str, summary: str, source: str = "") -> str:
    if not (topic and summary):
        return "Error: need both a topic and a summary."
    MEM.add_note(f"{topic}: {summary}", kind="knowledge", source=source)
    return f"SUCCESS: saved what I learned about '{topic}'."


def remember_fact(key: str, value: str) -> str:
    return f"SUCCESS: remembered {key} = {value}" if MEM.set_fact(key, value) else "Error: nothing to remember."


def forget_fact(key: str) -> str:
    return f"SUCCESS: forgot '{key}'." if MEM.forget_fact(key) else f"I had nothing stored as '{key}'."


def update_style(style: str) -> str:
    style = " ".join(str(style).split())[:300]
    if not style:
        return "Error: style cannot be empty."
    CONFIG["speaking_style"] = style
    save_config()
    return f"SUCCESS: from now on my style is: {style}"


def create_file(filename: str, content: str = "") -> str:
    try:
        return save_output(filename, str(content)[:300_000])
    except Exception as e:
        return f"Error creating file: {e}"


def _read_output_text(name: str) -> str | None:
    clean = filelib.safe_name(name)
    path = _contained_path(OUTPUT_DIR, os.path.join(OUTPUT_DIR, clean))
    if os.path.islink(path) or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(2_000_000)


def read_file(name: str, start: int = 0, length: int = 4000) -> str:
    rec = MEM.get_file(name)
    text = None
    if rec:
        text = filelib.full_text(rec)
        if not text and rec["kind"] in ("image", "video"):
            return f"'{rec['name']}' is {rec['kind']} - use look_at_image to see it."
    else:
        try:
            text = _read_output_text(name)
        except (OSError, ValueError):
            text = None
    if text is None:
        return f"No file called '{name}'. Use list_files to see what's available."
    try:
        start, length = max(0, int(start)), max(200, min(int(length), 8000))
    except (TypeError, ValueError):
        start, length = 0, 4000
    return f"[chars {start}-{min(start + length, len(text))} of {len(text)}]\n" + text[start:start + length]


def list_files() -> str:
    shared = [f"{f['name']} ({f['kind']}, shared by you)" for f in MEM.data["files"][-15:]]
    made = [f"{n} (made by me)" for n in sorted(os.listdir(OUTPUT_DIR))[:15]]
    return "\n".join(shared + made) or "No files yet."


def check_code(code: str = "", filename: str = "", language: str = "python") -> str:
    if not code and filename:
        rec = MEM.get_file(filename)
        if rec:
            code = filelib.full_text(rec)
            language = os.path.splitext(rec["name"])[1] or language
        else:
            try:
                output_text = _read_output_text(filename)
            except (OSError, ValueError):
                output_text = None
            if output_text is not None:
                code = output_text
                language = os.path.splitext(filelib.safe_name(filename))[1] or language
    if not code:
        return "Error: give me some code or the name of a file."
    return codecheck.check(code, language, filename or "code")


def look_at_image(name: str, question: str = "") -> str:
    rec = MEM.get_file(name)
    if not rec or not rec.get("images"):
        return f"I don't have an image or video called '{name}'."
    return LLM_.describe_image(rec["images"], question)


def list_my_tools() -> str:
    stored = [item["name"] for item in skills_info()]
    return (f"Built-in: {sorted(CORE_FUNCS)}\n"
            f"Stored skill source (not executed): {stored or 'none'}")


def read_my_tools() -> str:
    if not os.path.exists(LEARNED_FILE):
        return "No learned tools yet."
    return open(LEARNED_FILE, "r", encoding="utf-8").read()[:5000]


ALLOWED_IMPORTS = {
    "base64", "bisect", "bs4", "calendar", "collections", "copy", "csv",
    "dataclasses", "datetime", "decimal", "difflib", "enum", "fractions",
    "functools", "hashlib", "heapq", "hmac", "html", "itertools", "json",
    "math", "operator", "pprint", "random", "re", "requests", "statistics",
    "string", "textwrap", "time", "typing", "unicodedata", "urllib", "uuid",
    "zoneinfo",
}
BANNED_IMPORTS = {"subprocess", "shutil", "ctypes", "multiprocessing", "importlib", "pickle", "marshal",
                  "builtins", "socket", "sys", "signal", "threading", "os", "pathlib"}
BANNED_NAMES = {"eval", "exec", "compile", "__import__", "exit", "quit", "getattr", "setattr", "delattr",
                "globals", "locals", "vars", "breakpoint", "input"}
BANNED_ATTRS = {"remove", "unlink", "rmdir", "rmtree", "removedirs", "system", "popen", "Popen", "kill",
                "chmod", "exit", "_exit", "execv", "execl", "startfile", "rename", "replace", "environ",
                "__globals__", "__builtins__", "__subclasses__", "__class__", "__bases__", "__code__"}


def validate_code(code: str):
    """Static review only. This is deliberately NOT treated as a Python sandbox."""
    if not isinstance(code, str) or not code.strip():
        return "No code supplied."
    if len(code) > 100_000:
        return "Skill source exceeds the 100 KB limit."
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}"
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not functions:
        return "No function found. Provide at least one complete 'def' function."
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node)
            if not doc:
                return f"Function '{node.name}' needs a docstring."
            if node.decorator_list or node.args.defaults or any(x is not None for x in node.args.kw_defaults):
                return "Decorators and evaluated default expressions are not accepted in skill source."
        elif isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)):
            if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                return "Only docstrings may appear as top-level expressions."
            if isinstance(node, ast.ImportFrom) and node.level:
                return "Relative imports are not allowed."
            modules = ([a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import)
                       else [(node.module or "").split(".")[0]])
            for module in modules:
                if module not in ALLOWED_IMPORTS:
                    return f"Import of '{module}' is not in the review allow-list."
        elif isinstance(node, ast.Assign):
            try:
                ast.literal_eval(node.value)
            except Exception:
                return "Top-level assignments must contain literal constants only."
        else:
            return "Only imports, literal constants and function definitions are accepted at top level."
    return None


def _load_module(path: str):
    raise RuntimeError("Learned Python code is never imported or executed by Nova. Review it manually instead.")


def load_learned_tools():
    """Do not import learned code into Nova's process. Keep skills visible as source only."""
    LEARNED.clear()
    if os.path.exists(LEARNED_FILE):
        print("[security] Learned Python skills are stored for review but are not executed.")


def list_backups() -> list:
    out = []
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if name.endswith(".py") and not os.path.islink(path) and os.path.isfile(path):
            out.append(name)
    return sorted(out, reverse=True)


def make_backup(tag: str = "before_update") -> str:
    if not os.path.exists(LEARNED_FILE):
        return ""
    if os.path.islink(LEARNED_FILE) or not os.path.isfile(LEARNED_FILE):
        raise ValueError("The learned-skills source is not a regular file.")
    name = f"learned_tools_{time.strftime('%Y%m%d_%H%M%S')}_{tag}.py"
    target = _contained_path(BACKUP_DIR, os.path.join(BACKUP_DIR, name))
    shutil.copyfile(LEARNED_FILE, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    for old in list_backups()[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    return name


def rollback(index: int = 1) -> str:
    backups = list_backups()
    if not backups:
        return "No backups available."
    if not 1 <= index <= len(backups):
        return f"Pick a number between 1 and {len(backups)}."
    chosen = backups[index - 1]
    source = _contained_path(BACKUP_DIR, os.path.join(BACKUP_DIR, chosen))
    if os.path.islink(source) or not os.path.isfile(source):
        return "That backup is not a regular file."
    make_backup("before_rollback")
    target = _contained_path(os.path.dirname(LEARNED_FILE), LEARNED_FILE)
    shutil.copyfile(source, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    load_learned_tools()
    return f"Restored {chosen}. Skills now: {', '.join(LEARNED) or 'none'}"


def strip_fences(code: str) -> str:
    code = (code or "").strip()
    if code.startswith("```"):
        lines = code.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines)
    return code.strip()


def learn_new_tool(func_code: str) -> str:
    code = strip_fences(func_code)
    error = validate_code(code)
    if error:
        return f"REJECTED: {error}"
    new_names = {n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)}
    clash = new_names & set(CORE_FUNCS)
    if clash:
        return f"REJECTED: {sorted(clash)} clash with built-in tools."
    existing = ""
    if os.path.exists(LEARNED_FILE):
        try:
            existing = open(LEARNED_FILE, "r", encoding="utf-8").read()
        except OSError:
            return "REJECTED: existing skill file could not be read."
    try:
        old_tree = ast.parse(existing) if existing.strip() else ast.Module(body=[], type_ignores=[])
        segments = []
        for node in old_tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in new_names:
                continue
            seg = ast.get_source_segment(existing, node)
            if seg:
                segments.append(seg)
    except SyntaxError:
        return "REJECTED: existing skills file has a syntax error; repair or back it up first."
    merged = "\n\n".join(segments + [code]) + "\n"
    try:
        ast.parse(merged)
    except SyntaxError as e:
        return f"REJECTED: merged source has a syntax error on line {e.lineno}."
    backup = make_backup("before_update")
    tmp = CANDIDATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(merged)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, LEARNED_FILE)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
    MEM.data.setdefault("version_history", []).append(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} stored for review (not executable): {', '.join(sorted(new_names))}")
    MEM.save()
    return (f"STORED FOR REVIEW: {sorted(new_names)}. Backup: {backup or 'none (first skill)'}. "
            "Nova will not execute learned Python code. A separate OS sandbox is required to enable that safely.")


def skills_info() -> list:
    if not os.path.isfile(LEARNED_FILE) or os.path.islink(LEARNED_FILE):
        return []
    try:
        source = open(LEARNED_FILE, "r", encoding="utf-8").read(100_001)
        if len(source) > 100_000:
            return []
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeError):
        return []
    out = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            doc = ast.get_docstring(node) or ""
            args = [a.arg for a in node.args.args]
            signature = "(" + ", ".join(args) + ")"
            out.append({"name": node.name, "description": doc.splitlines()[0][:100] if doc else "",
                        "doc": doc[:1000], "signature": signature, "executable": False})
    return out[:100]


def _fn(name, desc, props=None, required=()):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": list(required)}}}


S = {"type": "string"}
CORE_SCHEMAS = {
    "web_search": _fn("web_search", "Search the web. Returns titles, snippets and URLs. Use short keyword queries.",
                      {"query": S}, ["query"]),
    "read_webpage": _fn("read_webpage", "Open a URL (from search results or the user) and read its text.",
                        {"url": S}, ["url"]),
    "save_knowledge": _fn("save_knowledge", "Store something useful you learned so you can recall it later.",
                          {"topic": S, "summary": {"type": "string", "description": "1-3 sentences, the key facts"},
                           "source": {"type": "string", "description": "URL if any"}}, ["topic", "summary"]),
    "remember_fact": _fn("remember_fact", "Permanently remember a fact about the user (name, job, likes, goals...).",
                         {"key": {"type": "string", "description": "short label e.g. 'favourite_food'"}, "value": S},
                         ["key", "value"]),
    "forget_fact": _fn("forget_fact", "Forget a stored fact about the user.", {"key": S}, ["key"]),
    "update_style": _fn("update_style", "Change how you speak (tone, personality) from now on, as the user asked.",
                        {"style": {"type": "string", "description": "one or two sentences describing your new style"}},
                        ["style"]),
    "create_file": _fn("create_file", "Create a text or code file in the 'output files' folder.",
                       {"filename": {"type": "string", "description": "e.g. notes.txt or app.py"},
                        "content": {"type": "string", "description": "the full exact content"}},
                       ["filename", "content"]),
    "read_file": _fn("read_file", "Read more of a file the user shared (or one you made). For long files, page with start.",
                     {"name": S, "start": {"type": "integer"}, "length": {"type": "integer"}}, ["name"]),
    "list_files": _fn("list_files", "List files the user shared and files you created."),
    "check_code": _fn("check_code", "Check code for syntax errors and common bugs. Pass code or the name of a shared file.",
                      {"code": S, "filename": S, "language": {"type": "string", "description": "python, javascript, json"}}),
    "look_at_image": _fn("look_at_image", "Look at a shared image or video again and answer a specific question about it.",
                         {"name": S, "question": S}, ["name"]),
    "learn_new_tool": _fn("learn_new_tool",
                          "Draft Python skill source and store it for human review. Nova never imports or executes "
                          "AI-written Python. Include type hints and a docstring. Stored code is not callable.",
                          {"func_code": {"type": "string", "description": "imports and def functions only"}}, ["func_code"]),
    "list_my_tools": _fn("list_my_tools", "List every tool and learned skill you have."),
    "read_my_tools": _fn("read_my_tools", "Read the source code of skills you have taught yourself."),
}

CORE_FUNCS = {
    "web_search": web_search, "read_webpage": read_webpage, "save_knowledge": save_knowledge,
    "remember_fact": remember_fact, "forget_fact": forget_fact, "update_style": update_style,
    "create_file": create_file, "read_file": read_file, "list_files": list_files, "check_code": check_code,
    "look_at_image": look_at_image, "learn_new_tool": learn_new_tool, "list_my_tools": list_my_tools,
    "read_my_tools": read_my_tools,
}

GROUPS = {
    "web": ["web_search", "read_webpage", "save_knowledge"],
    "learn": ["web_search", "read_webpage", "learn_new_tool", "save_knowledge", "list_my_tools", "read_my_tools"],
    "files": ["create_file", "read_file", "list_files", "check_code"],
    "code": ["check_code", "read_file", "create_file"],
    "memory": ["remember_fact", "forget_fact"],
    "style": ["update_style"],
    "image": ["look_at_image"],
    "tools": ["list_my_tools", "read_my_tools"],
}

CORE_HELP = {
    "web_search": "Search the web", "read_webpage": "Open and read a web page",
    "save_knowledge": "Keep what she learns for later", "remember_fact": "Remember things about you",
    "forget_fact": "Forget something about you", "update_style": "Change how she talks",
    "create_file": "Create a text/code file", "read_file": "Read shared files in depth",
    "list_files": "List shared and created files", "check_code": "Check code for bugs",
    "look_at_image": "Look at images/videos again", "learn_new_tool": "Draft a skill for review (not executed)",
    "list_my_tools": "List her abilities", "read_my_tools": "Show the code of her skills",
}


def _build_schema(fn) -> dict:
    py = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}
    props, required = {}, []
    for pname, p in inspect.signature(fn).parameters.items():
        props[pname] = {"type": py.get(p.annotation, "string")}
        if p.default is inspect.Parameter.empty:
            required.append(pname)
    return _fn(fn.__name__, (inspect.getdoc(fn) or fn.__name__)[:400], props, required)


def schemas_for(groups, text: str = "") -> list:
    names = []
    for g in groups:
        for n in GROUPS.get(g, []):
            if n not in names:
                names.append(n)
    out = [CORE_SCHEMAS[n] for n in names]
    words = set(tokens(text))
    # Stored skill source is deliberately not exposed as executable tools.
    return out


def execute(name: str, args) -> str:
    if not isinstance(args, dict):
        args = {}
    fn = CORE_FUNCS.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. {list_my_tools()}"
    try:
        return str(fn(**args))
    except TypeError as e:
        return f"Bad arguments for {name}: {e}"
    except Exception as e:
        return f"Tool '{name}' crashed: {e}"


load_learned_tools()
