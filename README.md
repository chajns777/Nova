# Nova

A private, local-first AI desktop companion written in Python. Nova runs entirely on your own machine through [Ollama](https://ollama.com): she chats like a person, remembers what you tell her, researches the web, reads your documents and images, checks your code, and can teach herself new skills. No cloud account, no API keys, no data leaving your computer (except the web searches you let her make, and your conversation text if you choose to switch on the optional hosted [ChatSorter](#chatsorter-long-term-memory-optional) memory).

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [The interface](#the-interface)
  - [Working with files and media](#working-with-files-and-media)
  - [Configuration](#configuration)
  - [Examples](#examples)
  - [Status and error messages](#status-and-error-messages)
- [Built-in abilities](#built-in-abilities)
- [Self-learning skills](#self-learning-skills)
- [ChatSorter long-term memory (optional)](#chatsorter-long-term-memory-optional)
- [Security model](#security-model)
- [Architecture](#architecture)
  - [Project structure](#project-structure)
  - [Execution pipeline](#execution-pipeline)
- [Development and testing](#development-and-testing)
- [Licence](#licence)

---

## Features

- **Fully local:** The language model runs through Ollama on your own hardware. Conversations, memory and files are stored in plain JSON next to the app.
- **Persistent memory:** Nova extracts durable facts about you (name, job, projects, preferences) after you chat, keeps a rolling summary of older conversation, and recalls relevant notes when they matter. Everything is viewable and deletable from the Memory panel.
- **Optional long-term memory:** Connect [ChatSorter](#chatsorter-long-term-memory-optional) (hosted or self-hosted) and Nova stores your conversations there, then pulls relevant memories from past chats into each reply. Off by default, and if the service is down she simply carries on with her built-in memory.
- **Web research:** Searches the web and reads pages, with automatic fallback between DuckDuckGo (`ddgs`), DuckDuckGo HTML and Wikipedia. Results are cached for ten minutes.
- **Files, images and media:** Drag and drop PDFs, Word documents, spreadsheets, code, images, audio and video. Long documents are never stuffed into the prompt; Nova picks the passages that match your question and can read further on demand.
- **Code checking:** Static checks for Python (syntax plus `pyflakes` and common-pitfall rules), JSON and JavaScript. Nothing you share is ever executed.
- **Self-learning skills:** Nova can write new Python tools for herself, validate them against a strict safety allow-list, back up the previous version, and use them straight away. Roll back any time from the Skills panel.
- **Adaptive models:** Works with any Ollama model. Nova detects whether it supports tools, vision or thinking, and adjusts. You can set a separate vision model for image tasks.
- **Fast by design:** The model is warmed up at launch and kept loaded, replies are streamed token by token, thinking is switched off for reasoning models, and tools are only sent to the model when your message actually needs them.
- **App-style window:** Opens in a chromeless Edge, Chrome, Brave or Chromium window (or an optional native `pywebview` window). Close the window and Nova quits.

---

## Installation

### Prerequisites

- [Python](https://www.python.org/downloads/) 3.10 or newer
- [Ollama](https://ollama.com/download), installed (Nova will start it for you if it is not already running)
- A Chromium-based browser (Edge, Chrome, Brave or Chromium) for the app-style window, or any browser as a fallback

### Run from source

```bash
git clone https://github.com/chajns777/Nova.git
cd Nova
python -m pip install -r requirements.txt
python Nova.py
```

On Windows you can instead double-click **`Nova.bat`**. On first run it installs the Python dependencies and then launches Nova.

If her model has not been downloaded yet, Nova shows a **Download now** button with a progress bar. You can also pull it yourself:

```bash
ollama pull qwen3-vl:4b-instruct
```

### Optional extras

```bash
pip install -r requirements-optional.txt
```

| Package | Unlocks |
| --- | --- |
| `pymupdf` | Reading scanned PDFs by rendering their first pages as images for vision. |
| `faster-whisper` | Listening to audio files via local transcription (Whisper `base`, CPU). |
| `opencv-python-headless` | Looking at video by sampling frames across the clip. |
| `pywebview` | A native window instead of a browser app window (`"window": "webview"`). |

### Recommended Ollama settings

If you start Ollama yourself, these two environment variables make generation noticeably faster. Nova sets both automatically when she launches Ollama for you.

```bash
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
```

---

## Usage

```bash
python Nova.py
```

Nova starts a local server on a random free port, warms up the model in the background, and opens her window. Closing the window shuts everything down (after a short grace period, so a page refresh does not kill her).

### The interface

The side rail switches between five panels:

| Panel | Purpose |
| --- | --- |
| **chat** | Talk to Nova, attach files, stop a reply mid-stream. |
| **memory** | See, edit and delete the facts, learned notes and conversation summary Nova holds about you. Clear the chat history. |
| **skills** | Browse built-in abilities and self-taught skills, read their source, and roll back to a previous version. |
| **files** | Everything you have shared with Nova. |
| **settings** | Name, speaking style, model, vision model, web access and auto-learn toggles, plus model downloads. |

Press `Esc` to close an open panel.

### Working with files and media

Drag and drop, paste, or use the paperclip. Up to six files can be attached to a single message, with a 300 MB limit per upload.

| Type | Extensions | How Nova reads it |
| --- | --- | --- |
| Documents | `.pdf`, `.docx` | Text is extracted (up to 250 PDF pages). Scanned PDFs need `pymupdf`. |
| Spreadsheets | `.xlsx`, `.xlsm`, `.csv`, `.tsv` | Converted to readable text. |
| Text and code | `.txt`, `.md`, `.json`, `.yaml`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.sql`, `.html`, `.css`, `.sh`, and many more | Read as text; Python, JSON and JavaScript are also auto-checked. |
| Images | `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp` | Shrunk to 1024 px on the long side so vision is quick. |
| Audio | `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.aac`, `.wma` | Transcribed locally (needs `faster-whisper`). |
| Video | `.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, `.m4v` | Four frames sampled across the clip (needs `opencv-python-headless`). |

Large documents are stored in full (up to two million characters) but only the most relevant ~6,000 characters are placed in the prompt. When that is not enough, Nova calls `read_file` to page through the rest.

### Configuration

Most settings live in the **settings** panel. Everything else, including the ChatSorter keys, is in `config.json` only, which is created with defaults on first run and merged with any new keys after updates.

| Key | Default | Description |
| --- | --- | --- |
| `name` | `"Nova"` | What she calls herself. |
| `model` | `"qwen3-vl:4b-instruct"` | The Ollama model used for chat. |
| `vision_model` | `""` | Optional separate model used to describe images when the main model cannot see. |
| `speaking_style` | `"Calm, warm and a little witty…"` | Personality prompt. Nova can change this herself when you ask. |
| `max_history_messages` | `14` | Recent messages sent to the model verbatim. Older ones are summarised. |
| `max_steps` | `6` | Maximum tool-use steps per reply. |
| `num_ctx` | `8192` | Context window in tokens. |
| `num_predict` | `900` | Maximum tokens generated per reply. |
| `temperature` | `0.7` | Sampling temperature. |
| `keep_alive` | `"30m"` | How long Ollama keeps the model loaded. |
| `web_enabled` | `true` | Allow web search and page reading. |
| `auto_learn` | `true` | Quietly extract facts about you from your messages. |
| `window` | `"auto"` | `auto`, `app` (Chromium app window), `webview` (native window), or any other value for your default browser. |
| `window_width` / `window_height` | `1120` / `780` | Window size. |
| `chatsorter_enabled` | `false` | Turn on [ChatSorter](#chatsorter-long-term-memory-optional) long-term memory. Also needs the `CHATSORTER_API_KEY` environment variable. |
| `chatsorter_url` | `"https://api.chatsorter.com"` | ChatSorter server. Change it to your own address if you self-host, e.g. `http://localhost:5050`. |
| `chatsorter_chat_id` | `"nova_main"` | Identifier your memories are filed under (used as both the chat and user ID). Keep it the same to keep your memories; change it to start a fresh memory. |

**Choosing a model:** on a weaker PC try `qwen3-vl:2b-instruct`; on a stronger GPU, use a larger `qwen3-vl` size. Any Ollama model works. If it cannot call tools or see images, Nova adapts, and you can nominate a separate `vision_model`.

### Examples

```text
# Everyday chat, with memory
"I'm learning Rust and I work nights, so keep it short."
"What should I build next for practice?"          # uses what she learned about you

# Web research
"What's the latest stable Python release?"
"Read https://example.com/article and give me the gist."

# Files
[drop in report.pdf]  "What are the main risks they mention on page 12?"
[drop in photo.jpg]   "What's wrong with this wiring?"
"Write a README for this project and save it."     # saved to output files/

# Code
[paste a Python function]  "Why does this crash?"
[drop in script.py]        "Check this for bugs."

# Personality
"From now on, be more blunt and less chatty."      # updates her speaking style

# Self-learning
"Teach yourself how to convert a CSV into a Markdown table."
"What can you do?"                                 # lists built-in and learned skills
```

### Status and error messages

| Message | Meaning |
| --- | --- |
| *I can't reach Ollama* | Ollama is not installed or not running. Install it, start it, and try again. |
| *The model "…" isn't downloaded yet* | Use the **Download now** button or `ollama pull <model>`. |
| *I hit my step limit* | The request needed more than `max_steps` tool calls. Split it into smaller asks. |
| *busy (HTTP 409)* | Nova is mid-reply. Wait for her to finish or press stop. |

---

## Built-in abilities

Nova only receives the tools a message is likely to need. A lightweight router matches your wording to a group (web, files, code, memory, style, learning, image), which keeps small models fast and focused.

| Tool | What it does |
| --- | --- |
| `web_search` | Searches the web and returns titles, snippets and URLs. |
| `read_webpage` | Opens a public URL and extracts its readable text. |
| `save_knowledge` | Stores something she learned so she can recall it later. |
| `remember_fact` / `forget_fact` | Adds or removes a durable fact about you. |
| `update_style` | Changes her tone and personality. |
| `create_file` | Writes a text or code file into `output files/` (up to 300,000 characters). |
| `read_file` | Reads more of a shared or created file, in pages. |
| `list_files` | Lists files you shared and files she made. |
| `check_code` | Statically checks Python, JSON or JavaScript. |
| `look_at_image` | Re-examines a shared image or video with a specific question. |
| `learn_new_tool` | Teaches herself a new Python skill (see below). |
| `list_my_tools` / `read_my_tools` | Lists her abilities or shows the source of her learned skills. |

---

## Self-learning skills

When you ask Nova to learn something, she researches it online, writes one or more Python functions, and submits them through `learn_new_tool`. Each submission goes through the same pipeline:

1. **Static validation:** The code is parsed and only imports, plain constants and `def` functions are allowed at the top level. Every function needs a docstring with a short summary line.
2. **Banned constructs:** Shell and process access (`subprocess`, `os.system`), networking primitives (`socket`), deletion and renaming, `eval`, `exec`, `getattr`, `open()` in any write mode, and access to interpreter internals are all rejected.
3. **Trial load:** The merged skill file is written to a candidate and imported. If it fails, nothing changes.
4. **Backup and swap:** The previous `learned_tools.py` is copied into `backups/` (the latest ten are kept) before the new version replaces it.
5. **Immediate use:** The new tool is available in the same turn, so Nova can finish your request with it.

Learned skills can use `requests`, `json`, `re`, `math`, `datetime` and `urllib`, plus injected helpers: `web_search(query)`, `read_webpage(url)` and `save_output(filename, content)`. They can only write to `output files/`.

You can inspect every skill's source and roll back to any backup from the **skills** panel.

---

## ChatSorter long-term memory (optional)

Nova's built-in memory (facts, notes and a rolling summary in `memory.json`) works with no setup. [ChatSorter](https://chatsorter.com) adds a second layer on top: every exchange is stored in a ChatSorter memory, and before each reply Nova asks it for anything relevant from past conversations. Those memories appear in her context as *"Long-term memory (from past conversations)"*, alongside her own notes. It is off by default.

### Setup

1. Get an API key from [chatsorter.com](https://chatsorter.com), or run your own ChatSorter server.
2. Put the key in an environment variable. Never put it in `config.json`.

   ```bash
   # macOS / Linux
   export CHATSORTER_API_KEY=your_key

   # Windows (PowerShell), then open a new terminal
   setx CHATSORTER_API_KEY "your_key"
   ```

   If you launch Nova by double-clicking `Nova.bat`, a `setx` value only reaches it after you sign out and back in. As a shortcut you can add `set CHATSORTER_API_KEY=your_key` on a line above `python Nova.py` in `Nova.bat`, but that stores the key in a file, so never share or commit it.
3. In `config.json`, set `"chatsorter_enabled": true`. If you self-host, also set `chatsorter_url` (for example `http://localhost:5050`).
4. Restart Nova.

ChatSorter is active only when **both** `chatsorter_enabled` is `true` **and** `CHATSORTER_API_KEY` is set. If either is missing, Nova behaves exactly as before and makes no network calls to ChatSorter.

### What happens on each turn

| When | What Nova sends | What she does with the result |
| --- | --- | --- |
| **Before replying** | Your message (first 1,000 characters) to `/search`. | Adds up to six returned memory summaries to the turn's context. |
| **After replying** | Your message and her reply, each cut to 4,000 characters, to `/process`. | Nothing. This runs in the background queue, only once Nova is idle. |

Only the text of the conversation is sent. Files you attach, their extracted text, and the contents of `memory.json` are not.

### Privacy

With the hosted API, your messages and Nova's replies leave your computer and are stored by ChatSorter. Nova's introduction to the model still says everything stays on your machine, so keep that in mind when you enable it. To keep everything local, self-host ChatSorter and point `chatsorter_url` at it. To stop sending anything, set `chatsorter_enabled` back to `false`.

### If ChatSorter is slow or down

Every call fails soft: errors are printed to the terminal as `[chatsorter] store failed: ...` or `[chatsorter] recall failed: ...`, and Nova carries on with her built-in memory. Each call has an 8-second timeout. The lookup happens before Nova starts replying, so an unreachable or very slow service can delay a reply by up to 8 seconds. Refused connections fail instantly, so the delay mainly applies when the server hangs.

| Symptom | Likely cause |
| --- | --- |
| No `[chatsorter]` messages and no long-term memories ever appear | `chatsorter_enabled` is `false`, or `CHATSORTER_API_KEY` is not visible to the process that launched Nova. |
| `recall failed: 401` / `store failed: 401` | The API key is wrong or expired. |
| `... Connection refused` | Self-hosted server is not running, or `chatsorter_url` is wrong. |
| Replies feel slow after enabling it | ChatSorter is responding slowly; check the terminal for timeouts. |

---

## Security model

- **Local only:** The server binds to `127.0.0.1`, validates the `Host` header, and requires a random per-launch token (`X-Nova-Token`) on every API call, so no website can talk to it.
- **No private-network browsing:** `read_webpage` refuses localhost, private, link-local and reserved addresses, and re-checks every redirect hop (maximum four).
- **Data, not instructions:** Text from files and web pages is treated as untrusted data. Nova is told never to follow instructions found inside it.
- **Nothing is executed from your files:** Shared code is only ever statically analysed.
- **Confined writes:** Nova writes files only inside `output files/`, and filenames are sanitised.
- **ChatSorter is the exception:** When enabled with the hosted API, conversation text is sent to a third party. The API key is read from the `CHATSORTER_API_KEY` environment variable only and is never written to `config.json` or `memory.json`.
- **Guardrail, not a sandbox:** The skill validator is an allow-list check, not an isolated runtime. Skim new skills in the Skills panel before relying on them.

---

## Architecture

The codebase separates the UI server, the agent loop, memory, tools and model access, so each can be reasoned about on its own.

### Project structure

```text
Nova/
├── Nova.py                      # Launcher: starts the server, warms the model, opens the window
├── Nova.bat                     # Windows double-click launcher (installs dependencies on first run)
├── config.json                  # User-tunable settings
├── memory.json                  # Facts, notes, summary, history and shared-file records
├── requirements.txt             # Core dependencies
├── requirements-optional.txt    # Optional extras (scanned PDFs, audio, video, native window)
├── nova/
│   ├── agent.py                 # System prompt, tool routing, streaming turn loop, background learning
│   ├── llm.py                   # Ollama client: streaming, capabilities, warm-up, model pulls
│   ├── memory.py                # Facts, notes, rolling summary and relevance retrieval
│   ├── chatsorter.py            # Optional ChatSorter client: store exchanges, recall long-term memories
│   ├── tools.py                 # Built-in tools, web access, self-learning pipeline and backups
│   ├── files.py                 # Ingestion and text extraction for documents, images, audio and video
│   ├── codecheck.py             # Static checks for Python, JSON and JavaScript
│   ├── server.py                # Token-protected local HTTP + Server-Sent Events API
│   └── config.py                # Paths, defaults and atomic JSON load/save helpers
└── ui/
    ├── index.html               # Single-page shell
    ├── app.js                   # Chat, panels, uploads and streaming client
    ├── style.css                # Terminal-inspired theme
    └── logo.svg                 # Emblem
```

Created at runtime: `uploads/`, `output files/`, `backups/`, `learned_tools.py` (once she learns a skill) and `.window_profile/`.

### Execution pipeline

```text
  Nova.py
     │
     ├──▶ NovaServer()            Bind 127.0.0.1 on a free port, generate the session token
     ├──▶ LLM_.warmup()           Load the model in the background (keep_alive)
     └──▶ launch_ui()             Chromium --app window ▶ pywebview ▶ default browser
                │
                ▼
  POST /api/chat  (Server-Sent Events stream)
                │
                ▼
  agent.run_turn()
    ├──▶ Check Ollama is up and the model is installed
    ├──▶ LLM_.capabilities()      Detect tools / vision / thinking support
    ├──▶ route()                  Regex-match the message to tool groups
    ├──▶ _build_user_turn()       Inject time, relevant notes, ChatSorter memories (if enabled), file excerpts and code checks
    ├──▶ Step loop (≤ max_steps)
    │      ├── stream_chat() ──▶ tokens to the UI
    │      ├── tool calls ─────▶ tools.execute() ──▶ status events + results back to the model
    │      └── nudge once if she explained instead of acting
    ├──▶ MEM.add_exchange()       Persist the conversation
    └──▶ Background queue         (runs only while Nova is idle)
           ├── learn_from_message()      Extract durable facts about you
           ├── summarise_old_messages()  Fold older messages into the rolling summary
           └── chatsorter.store()        Send your message and her reply to ChatSorter (if enabled)
```

---

## Development and testing

```bash
# Run directly from a terminal to see logs
python Nova.py

# Use the native window instead of a browser app window
#   set "window": "webview" in config.json and install pywebview

# Syntax check every module
python -m compileall nova Nova.py
```

Nova has no automated test suite yet. A quick manual smoke test:

1. Launch Nova and confirm the status pill turns ready.
2. Say "Hi, I'm Sam and I like climbing", then open **memory** and check the fact was learned.
3. Ask "What's the weather like in London today?" and confirm a web search runs.
4. Drop in a PDF and ask about a specific page.
5. *(ChatSorter only)* With it enabled, tell Nova something memorable, restart her, clear the chat from the **memory** panel, then ask about it. A correct answer that her own notes don't explain suggests the long-term memory is working. Watch the terminal for `[chatsorter]` errors.

---

## Licence

This project is licensed under the MIT Licence. See the [LICENSE](LICENSE) file for details.