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

"""Quick, safe static checks for code (nothing is ever executed)."""

import ast
import io
import json
import os
import shutil
import subprocess
import tempfile

LANG_BY_EXT = {".py": "python", ".pyw": "python", ".json": "json", ".js": "javascript",
               ".mjs": "javascript", ".cjs": "javascript"}


def check(code: str, language: str = "python", filename: str = "code") -> str:
    lang = (language or "").lower().lstrip(".")
    lang = {"py": "python", "js": "javascript", "node": "javascript"}.get(lang, lang)
    if lang == "python":
        return _python(code, filename)
    if lang == "json":
        try:
            json.loads(code)
            return "OK: valid JSON."
        except json.JSONDecodeError as e:
            return f"JSON error on line {e.lineno}, column {e.colno}: {e.msg}"
    if lang == "javascript":
        return _javascript(code)
    return f"No automatic checker for '{lang or 'this language'}'. Review it by reading carefully."


def _python(code: str, filename: str) -> str:
    try:
        tree = ast.parse(code, filename)
    except SyntaxError as e:
        line = (e.text or "").rstrip()
        return f"Syntax error on line {e.lineno}: {e.msg}\n> {line}"

    problems = []
    try:
        from pyflakes.api import check as pf_check
        from pyflakes.reporter import Reporter
        out, err = io.StringIO(), io.StringIO()
        pf_check(code, filename, Reporter(out, err))
        for ln in out.getvalue().splitlines():
            parts = ln.split(":", 3)
            problems.append(f"Line {parts[1]}: {parts[3].strip()}" if len(parts) == 4 else ln)
    except ImportError:
        pass

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            problems.append(f"Line {node.lineno}: bare 'except:' hides errors - catch a specific exception.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    problems.append(f"Line {node.lineno}: '{node.name}' has a mutable default argument.")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
            problems.append(f"Line {node.lineno}: {node.func.id}() on dynamic input is risky.")
        elif isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    problems.append(f"Line {node.lineno}: compare to None with 'is' / 'is not'.")

    funcs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    head = f"{len(code.splitlines())} lines; defines: {', '.join(funcs[:12]) or 'no functions/classes'}."
    if not problems:
        return f"OK: no syntax errors or common problems found. {head}"
    return f"{len(problems)} issue(s) found. {head}\n" + "\n".join(problems[:25])


def _javascript(code: str) -> str:
    node = shutil.which("node")
    if not node:
        return "Can't check JavaScript here (Node.js isn't installed). Review it by reading."
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return "OK: JavaScript syntax is valid."
        return "Syntax error:\n" + (r.stderr or "").replace(path, "code.js")[:800]
    except Exception as e:
        return f"Couldn't run the JavaScript check: {e}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
