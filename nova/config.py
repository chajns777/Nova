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

"""Paths, config.json and small JSON helpers shared by every module."""

import json
import os
import threading

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PKG_DIR)
UI_DIR = os.path.join(BASE_DIR, "ui")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")
LEARNED_FILE = os.path.join(BASE_DIR, "learned_tools.py")
CANDIDATE_FILE = os.path.join(BASE_DIR, "learned_tools.candidate.py")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
OUTPUT_DIR = os.path.join(BASE_DIR, "output files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_BACKUPS = 10

for _d in (BACKUP_DIR, OUTPUT_DIR, UPLOAD_DIR):
    os.makedirs(_d, exist_ok=True)

DEFAULT_CONFIG = {
    "name": "Nova",
    "model": "qwen3-vl:4b-instruct",
    "vision_model": "",
    "speaking_style": "Calm, warm and a little witty. Talks like a close friend, not a customer-service bot.",
    "max_history_messages": 14,  
    "max_steps": 6,           
    "num_ctx": 8192,       
    "num_predict": 900,        
    "temperature": 0.7,
    "keep_alive": "30m",       
    "web_enabled": True,
    "auto_learn": True,        
    "window": "auto",            
    "window_width": 1120,
    "window_height": 780,
    "chatsorter_enabled": False,
    "chatsorter_url": "https://api.chatsorter.com",
    "chatsorter_chat_id": "nova_main",
}

_lock = threading.RLock()


def save_json(path: str, data: dict):
    with _lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)


def load_json(path: str, default: dict) -> dict:
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, OSError):
            print(f"[warning] {os.path.basename(path)} was unreadable, using defaults.")
            data = {}
    merged = {**default, **data}
    if not os.path.exists(path) or merged != data:
        save_json(path, merged)
    return merged


CONFIG = load_json(CONFIG_FILE, DEFAULT_CONFIG)


def save_config():
    save_json(CONFIG_FILE, CONFIG)
