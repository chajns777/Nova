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

from . import codecheck, files as filelib
from .config import (CONFIG, save_config, LEARNED_FILE, CANDIDATE_FILE, BACKUP_DIR, OUTPUT_DIR, MAX_BACKUPS)
from .llm import LLM_
from .memory import MEM, tokens

LEARNED = {}  


# === helpers ===
def save_output(filename: str, content: str) -> str:
    """Writes a file inside the 'output files' folder (the only place Nova may write)."""
    if not filename:
        return "Error: filename cannot be empty."
    clean = filelib.safe_name(filename)
    with open(os.path.join(OUTPUT_DIR, clean), "w", encoding="utf-8") as f:
        f.write(str(content))
    return f"SUCCESS: saved '{clean}' in 'output files/'."


HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}


def _public_url(url: str) -> bool:
    """Refuse localhost / private-network URLs so web pages can't steer Nova at your own machine."""
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


# === web ===
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
        res = requests.post("https://html.duckduckgo.com/html/", data={"q": q}, headers=HEADERS, timeout=10)
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
        r = requests.get("https://en.wikipedia.org/w/api.php", headers=HEADERS, timeout=10,
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
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        res = None
        for _ in range(4):
            if not _public_url(url):
                return "Error: that address isn't a public website, so I won't open it."
            res = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=False, stream=True)
            if res.is_redirect and res.headers.get("location"):
                url = urljoin(url, res.headers["location"])
                continue
            break
        ctype = res.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            return f"Can't read this kind of content ({ctype or 'unknown'})."
        raw = res.raw.read(600_000, decode_content=True).decode(res.encoding or "utf-8", errors="replace")
        if "html" not in ctype:
            return raw[:5000]
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"]):
            tag.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        title = soup.title.get_text(strip=True) if soup.title else ""
        text = re.sub(r"\s+", " ", root.get_text(" ", strip=True))
        return (f"[{title}]\n" if title else "") + (text[:5000] or "The page had no readable text.")
    except Exception as e:
        return f"Error fetching page: {e}"


# === core tools ===
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


def read_file(name: str, start: int = 0, length: int = 4000) -> str:
    rec = MEM.get_file(name)
    text = None
    if rec:
        text = filelib.full_text(rec)
        if not text and rec["kind"] in ("image", "video"):
            return f"'{rec['name']}' is {rec['kind']} - use look_at_image to see it."
    else:
        p = os.path.join(OUTPUT_DIR, filelib.safe_name(name))
        if os.path.isfile(p):
            text = filelib.full_text({"text_path": p})
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
            p = os.path.join(OUTPUT_DIR, filelib.safe_name(filename))
            if os.path.isfile(p):
                code = filelib.full_text({"text_path": p})
                language = os.path.splitext(p)[1] or language
    if not code:
        return "Error: give me some code or the name of a file."
    return codecheck.check(code, language, filename or "code")


def look_at_image(name: str, question: str = "") -> str:
    rec = MEM.get_file(name)
    if not rec or not rec.get("images"):
        return f"I don't have an image or video called '{name}'."
    return LLM_.describe_image(rec["images"], question)


def list_my_tools() -> str:
    return f"Built-in: {sorted(CORE_FUNCS)}\nLearned: {sorted(LEARNED) or 'none'}"


def read_my_tools() -> str:
    if not os.path.exists(LEARNED_FILE):
        return "No learned tools yet."
    return open(LEARNED_FILE, "r", encoding="utf-8").read()[:5000]


# === learned tools ===
BANNED_IMPORTS = {"subprocess", "shutil", "ctypes", "multiprocessing", "importlib", "pickle", "marshal",
                  "builtins", "socket", "sys", "signal", "threading"}
BANNED_NAMES = {"eval", "exec", "compile", "__import__", "exit", "quit", "getattr", "setattr", "delattr",
                "globals", "locals", "vars", "breakpoint", "input"}
BANNED_ATTRS = {"remove", "unlink", "rmdir", "rmtree", "removedirs", "system", "popen", "Popen", "kill",
                "chmod", "exit", "_exit", "execv", "execl", "startfile", "rename", "replace", "environ",
                "__globals__", "__builtins__", "__subclasses__", "__class__", "__bases__", "__code__"}


def validate_code(code: str):
    """Returns an error string if the code is unsafe/invalid, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}"
    funcs = 0
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs += 1
            doc = ast.get_docstring(node)
            if not doc:
                return f"Function '{node.name}' needs a docstring describing what it does."
            if len(doc.strip().splitlines()[0]) > 100:
                return f"The first docstring line of '{node.name}' must be a short summary (under 100 characters)."
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            pass
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            pass
        elif isinstance(node, ast.Assign):
            try:
                ast.literal_eval(node.value)
            except Exception:
                return "Top-level assignments may only hold plain constants (numbers, text, lists, dicts)."
        else:
            return "Only imports, constants and 'def' functions are allowed at the top level."
    if funcs == 0:
        return "No function found. Provide at least one complete 'def' function."
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in BANNED_IMPORTS:
                    return f"Import of '{a.name}' is not allowed."
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BANNED_IMPORTS:
                return f"Import from '{node.module}' is not allowed."
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            return f"Use of '{node.id}' is not allowed."
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            return f"Use of '.{node.attr}' is not allowed (no deleting, shell, exiting or poking at internals)."
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode = node.args[1] if len(node.args) > 1 else None
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode = kw.value
            if mode is not None:
                if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
                    return "open() mode must be a plain string like 'r'."
                if any(c in mode.value for c in "wax+"):
                    return "Don't open files for writing. Use save_output(filename, content) instead."
    return None


def _load_module(path: str):
    spec = importlib.util.spec_from_file_location("learned_tools", path)
    mod = importlib.util.module_from_spec(spec)
    mod.save_output, mod.OUTPUT_DIR = save_output, OUTPUT_DIR
    mod.web_search, mod.read_webpage = web_search, read_webpage
    spec.loader.exec_module(mod)
    return mod


def load_learned_tools():
    LEARNED.clear()
    if not os.path.exists(LEARNED_FILE):
        return
    try:
        mod = _load_module(LEARNED_FILE)
    except Exception as e:
        print(f"[warning] learned_tools.py failed to load: {e}\n          Roll back from the Skills panel.")
        return
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if fn.__module__ == "learned_tools" and not name.startswith("_"):
            LEARNED[name] = fn


def list_backups() -> list:
    return sorted((f for f in os.listdir(BACKUP_DIR) if f.endswith(".py")), reverse=True)


def make_backup(tag: str = "before_update") -> str:
    if not os.path.exists(LEARNED_FILE):
        return ""
    name = f"learned_tools_{time.strftime('%Y%m%d_%H%M%S')}_{tag}.py"
    shutil.copy2(LEARNED_FILE, os.path.join(BACKUP_DIR, name))
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
    make_backup("before_rollback")
    shutil.copy2(os.path.join(BACKUP_DIR, chosen), LEARNED_FILE)
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
        return f"REJECTED: {error} Fix it and call learn_new_tool again."
    new_names = {n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)}
    clash = new_names & set(CORE_FUNCS)
    if clash:
        return f"REJECTED: {sorted(clash)} clash with built-in tools. Use different names."

    segments, header = [], []
    if os.path.exists(LEARNED_FILE):
        existing = open(LEARNED_FILE, "r", encoding="utf-8").read()
        try:
            for node in ast.parse(existing).body:
                if isinstance(node, ast.FunctionDef) and node.name in new_names:
                    continue
                seg = ast.get_source_segment(existing, node)
                if seg:
                    segments.append(seg)
        except SyntaxError:
            segments = []
    segments.append(code)
    merged = "\n\n".join(segments) + "\n"

    with open(CANDIDATE_FILE, "w", encoding="utf-8") as f:
        f.write(merged)
    try:
        _load_module(CANDIDATE_FILE)
    except Exception as e:
        os.remove(CANDIDATE_FILE)
        return f"REJECTED: the code failed to load: {e}. Nothing was changed."

    backup = make_backup("before_update")    
    os.replace(CANDIDATE_FILE, LEARNED_FILE)
    load_learned_tools()
    MEM.data.setdefault("version_history", []).append(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} learned: {', '.join(sorted(new_names))}")
    MEM.save()
    return (f"SUCCESS: learned {sorted(new_names)}. Backup of the previous version: {backup or 'none (first skill)'}. "
            "You can call the new tool right now to finish the user's request.")


def skills_info() -> list:
    out = []
    for name, fn in sorted(LEARNED.items()):
        doc = (inspect.getdoc(fn) or "").strip()
        out.append({"name": name, "description": doc.splitlines()[0][:100] if doc else "", "doc": doc,
                    "signature": str(inspect.signature(fn))})
    return out


# === schemas ===
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
                          "Teach yourself a new ability by writing Python function(s). Type hints + a docstring whose first "
                          "line is a short summary. May use requests, json, re, math, datetime, urllib. Save files with "
                          "save_output(filename, content); search with web_search(q); read pages with read_webpage(url). "
                          "Becomes a permanent tool you can call straight away.",
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
    "look_at_image": "Look at images/videos again", "learn_new_tool": "Teach herself a new skill",
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
    """Tool schemas for the chosen groups, plus any learned skill that looks relevant to the message."""
    names = []
    for g in groups:
        for n in GROUPS.get(g, []):
            if n not in names:
                names.append(n)
    out = [CORE_SCHEMAS[n] for n in names]
    words = set(tokens(text))
    for name, fn in LEARNED.items():
        hay = set(tokens(name.replace("_", " ") + " " + (inspect.getdoc(fn) or "")))
        if "learn" in groups or "tools" in groups or words & hay:
            out.append(_build_schema(fn))
    return out


def execute(name: str, args) -> str:
    if not isinstance(args, dict):
        args = {}
    fn = CORE_FUNCS.get(name) or LEARNED.get(name)
    if fn is None:
        return f"Unknown tool '{name}'. {list_my_tools()}"
    try:
        return str(fn(**args))
    except TypeError as e:
        return f"Bad arguments for {name}: {e}"
    except Exception as e:
        return f"Tool '{name}' crashed: {e}"


load_learned_tools()
