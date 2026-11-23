"""Everything that talks to Ollama lives here.

Speed tricks: model stays loaded (keep_alive) and is warmed up at launch, tokens are streamed,
thinking is switched off for reasoning models, tools are only sent when needed, and Ollama is
told to use a modest context window.
"""

import os
import shutil
import subprocess
import sys
import threading
import time

import ollama

from .config import CONFIG

class OllamaDown(Exception):
    pass


class ModelMissing(Exception):
    def __init__(self, model):
        super().__init__(model)
        self.model = model


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _norm(name: str) -> str:
    name = (name or "").strip()
    return name if ":" in name else name + ":latest"


def _fmt(n) -> str:
    n = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u in ("B", "KB") else f"{n:.1f} {u}"
        n /= 1024


VISION_HINTS = ("vl", "vision", "llava", "gemma3", "gemma4", "qwen3.5", "minicpm-v", "moondream", "bakllava")


class LLM:
    def __init__(self):
        self.client = ollama.Client()
        self._caps = {}
        self.state = "starting"  
        self.last_stats = {}
        self._pull_lock = threading.Lock()
        self.pull_state = {"active": False, "model": "", "percent": None, "status": "", "detail": "", "error": ""}

    def ping(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False

    def ensure_server(self, wait=20) -> bool:
        """Start `ollama serve` in the background if it isn't running (and is installed)."""
        if self.ping():
            return True
        exe = shutil.which("ollama")
        if not exe:
            return False
        env = dict(os.environ)
        env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
        env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
        flags = 0x08000000 if sys.platform == "win32" else 0  
        try:
            subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=env, creationflags=flags)
        except Exception:
            return False
        end = time.time() + wait
        while time.time() < end:
            if self.ping():
                return True
            time.sleep(0.5)
        return False

    def installed(self) -> list:
        try:
            res = self.client.list()
        except Exception:
            return []
        models = _get(res, "models", []) or []
        return sorted({_get(m, "model") or _get(m, "name") for m in models if (_get(m, "model") or _get(m, "name"))})

    def has_model(self, name: str) -> bool:
        have = {_norm(m) for m in self.installed()}
        return _norm(name) in have

    def capabilities(self, model: str) -> set:
        model = model or CONFIG["model"]
        if model in self._caps:
            return self._caps[model]
        caps = None
        try:
            info = self.client.show(model)
            c = _get(info, "capabilities")
            if c:
                caps = set(c)
        except Exception:
            pass
        if caps is None:  
            caps = {"completion", "tools"}
            if any(h in model.lower() for h in VISION_HINTS):
                caps.add("vision")
        else:
            self._caps[model] = caps
        return caps

    def can_see(self, model=None) -> bool:
        return "vision" in self.capabilities(model or CONFIG["model"])

    def warmup(self):
        """Load the model into memory so the first message is instant."""
        model = CONFIG["model"]
        if not self.ensure_server():
            self.state = "offline"
            return
        if not self.has_model(model):
            self.state = "missing"
            return
        self.state = "loading"
        try:
            self.client.generate(model=model, prompt="", keep_alive=CONFIG["keep_alive"])
            self.capabilities(model)
            self.state = "ready"
        except Exception:
            self.state = "ready" if self.ping() else "offline"

    def start_pull(self, model: str) -> dict:
        model = (model or "").strip()
        if not model or len(model) > 120 or any(c.isspace() for c in model):
            return {"error": "Enter a model name, like qwen3-vl:4b-instruct."}
        with self._pull_lock:
            if self.pull_state["active"]:
                if self.pull_state["model"] == model:
                    return {"ok": True}
                return {"error": f"Already downloading {self.pull_state['model']}. Wait for it to finish."}
            self.pull_state = {"active": True, "model": model, "percent": None,
                               "status": "starting", "detail": "Starting...", "error": ""}
        threading.Thread(target=self._pull_worker, args=(model,), daemon=True).start()
        return {"ok": True}

    def _pull_worker(self, model: str):
        st = self.pull_state
        try:
            if not self.ensure_server():
                raise OllamaDown()
            layers, t0 = {}, time.time()
            for p in self.client.pull(model, stream=True):
                status = _get(p, "status", "") or ""
                digest, total, done = _get(p, "digest"), _get(p, "total"), _get(p, "completed")
                if digest and total:
                    layers[digest] = (done or 0, total)
                tot = sum(t for _, t in layers.values())
                got = sum(min(d, t) for d, t in layers.values())
                if tot:
                    st["percent"] = min(99, int(got * 100 / tot))
                    st["detail"] = f"{_fmt(got)} / {_fmt(tot)} - {_fmt(got / max(time.time() - t0, 0.5))}/s"
                else:
                    st["detail"] = status
                st["status"] = status
            st.update(percent=100, status="success", detail="Done")
            self._caps.pop(model, None)
        except OllamaDown:
            st["error"] = "Can't reach Ollama. Is it installed and running?"
        except ollama.ResponseError as e:
            st["error"] = f"Download failed: {getattr(e, 'error', None) or e}"
        except Exception as e:
            st["error"] = f"Download failed: {e}"
        warm = not st["error"] and model == CONFIG["model"]
        if warm:
            self.state = "loading"
        st["active"] = False
        if warm:
            self.warmup()

    def _options(self, extra=None) -> dict:
        o = {"num_ctx": int(CONFIG["num_ctx"]), "temperature": float(CONFIG["temperature"]),
             "num_predict": int(CONFIG["num_predict"])}
        o.update(extra or {})
        return o

    def stream_chat(self, messages, tools=None, model=None, options=None, fmt=None):
        """Generator of ('content', str) | ('tools', [{name, args}]) | ('stats', dict)."""
        model = model or CONFIG["model"]
        caps = self.capabilities(model)
        kwargs = dict(model=model, messages=messages, stream=True,
                      options=self._options(options), keep_alive=CONFIG["keep_alive"])
        if tools and "tools" in caps:
            kwargs["tools"] = tools
        if fmt:
            kwargs["format"] = fmt
        if "thinking" in caps:
            kwargs["think"] = False

        for _attempt in range(4):
            started = False
            try:
                for chunk in self.client.chat(**kwargs):
                    msg = _get(chunk, "message")
                    piece = _get(msg, "content") or ""
                    if piece:
                        started = True
                        yield ("content", piece)
                    calls = _get(msg, "tool_calls")
                    if calls:
                        started = True
                        out = []
                        for c in calls:
                            fn = _get(c, "function")
                            args = _get(fn, "arguments") or {}
                            if not isinstance(args, dict):
                                args = {}
                            out.append({"name": _get(fn, "name"), "args": args})
                        yield ("tools", out)
                    if _get(chunk, "done"):
                        n, dur = _get(chunk, "eval_count"), _get(chunk, "eval_duration")
                        if n and dur:
                            self.last_stats = {"tokens": n, "tps": round(n / (dur / 1e9), 1)}
                            yield ("stats", self.last_stats)
                return
            except ollama.ResponseError as e:
                text = str(getattr(e, "error", "") or e).lower()
                if started:
                    raise
                if "does not support tools" in text and "tools" in kwargs:
                    kwargs.pop("tools")
                    caps.discard("tools")
                    continue
                if "does not support thinking" in text and "think" in kwargs:
                    kwargs.pop("think")
                    caps.discard("thinking")
                    continue
                if getattr(e, "status_code", 0) == 404 or "not found" in text:
                    raise ModelMissing(model)
                raise
            except TypeError:
                if "think" in kwargs and not started:
                    kwargs.pop("think")
                    continue
                raise
            except ConnectionError:
                raise OllamaDown()
            except Exception as e:  
                if e.__class__.__name__ in ("ConnectError", "ConnectTimeout", "ReadTimeout") and not started:
                    raise OllamaDown()
                raise

    def complete(self, system: str, user: str, json_mode=False, max_tokens=300, model=None) -> str:
        """Small non-streaming helper for background jobs (fact extraction, summaries)."""
        text = ""
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        for kind, val in self.stream_chat(msgs, model=model, fmt="json" if json_mode else None,
                                          options={"temperature": 0.1, "num_predict": max_tokens}):
            if kind == "content":
                text += val
        return text.strip()

    def describe_image(self, image_paths, question: str) -> str:
        """Ask a vision-capable model about one or more images."""
        model = CONFIG.get("vision_model") or CONFIG["model"]
        if not self.has_model(model):
            return f"(I can't look at images because the model '{model}' isn't installed.)"
        if not self.can_see(model):
            return "(The current model can't see images. Set a vision model in Settings.)"
        msgs = [{"role": "user", "content": question or "Describe this image in detail, including any text.",
                 "images": list(image_paths)}]
        text = ""
        for kind, val in self.stream_chat(msgs, model=model, options={"num_predict": 500}):
            if kind == "content":
                text += val
        return text.strip()


LLM_ = LLM()
