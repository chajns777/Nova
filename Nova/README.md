# Nova

A small desktop companion that runs entirely on your own computer: chats like a person, learns about you,
researches the web, reads your files and pictures, writes and checks code, and can teach herself new skills.

## Run it
1. Install [Ollama](https://ollama.com/download) and [Python 3.10+](https://www.python.org/downloads/).
2. Double-click **Nova.bat** (first run installs the Python packages), or run `python Nova.py`.
3. If her model isn't downloaded yet, Nova shows a **Download now** button. (Or: `ollama pull qwen3-vl:4b-instruct`)

Nova opens in an app-style window using your default browser. Close the window and she quits.

## Files and media
Drag & drop, paste or use the paperclip. Long documents aren't stuffed into the prompt: Nova picks the
parts that match your question and can read more with `read_file`. Images are shrunk first so vision is quick.

Optional extras (`pip install -r requirements-optional.txt`): **pymupdf** (scanned PDFs), **faster-whisper**
(listen to audio), **opencv-python-headless** (look at video frames).

## Changing the brain
Settings -> Brain. Weaker PC: `qwen3-vl:2b-instruct`. Stronger GPU: a larger `qwen3-vl` size. Any Ollama model
works; if it can't use tools or see images, Nova adapts (and you can set a separate vision model).
Tip when you start Ollama yourself: `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0` speed things up
(Nova sets both if she launches Ollama for you). `config.json` has `num_ctx` / `num_predict` if you want to tune.

## Safety notes
- The server only listens on 127.0.0.1 and requires a random per-launch token.
- Nova refuses to open localhost/private-network URLs, and treats web/file text as data, not instructions.
- Skills she teaches herself are checked before use (no shell, deleting, `eval`, etc.) and can only write to `output files/`.
  This is a guardrail, not a perfect sandbox - skim new skills in the Skills panel.
- Nothing is executed from your files; code is only statically checked.

## Layout
`Nova.py` launcher · `nova/agent.py` brain · `nova/memory.py` · `nova/tools.py` abilities & self-learning ·
`nova/files.py` file reading · `nova/llm.py` Ollama · `nova/server.py` · `ui/` interface · `config.json` · `memory.json`
