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

"""Nova - a little desktop companion that runs on your own computer.

Run:  python Nova.py      (or double-click Nova.bat)
"""

import os
import shutil
import subprocess
import sys
import threading
import webbrowser

if sys.version_info < (3, 10):
    sys.exit("Nova needs Python 3.10 or newer (you have %d.%d). Please update Python." % sys.version_info[:2])

from nova.server import NovaServer, TOKEN
from nova.config import CONFIG, BASE_DIR
from nova.llm import LLM_


def find_chromium():
    names = ["msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser", "brave"]
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    candidates = []
    if sys.platform == "win32":
        pf = [os.environ.get("ProgramFiles", r"C:\Program Files"),
              os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
              os.environ.get("LOCALAPPDATA", "")]
        for base in pf:
            candidates += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"),
                           os.path.join(base, r"Google\Chrome\Application\chrome.exe"),
                           os.path.join(base, r"BraveSoftware\Brave-Browser\Application\brave.exe")]
    elif sys.platform == "darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def launch_ui(url: str, httpd) -> str:
    mode = CONFIG.get("window", "auto")
    w, h = int(CONFIG.get("window_width", 1120)), int(CONFIG.get("window_height", 780))

    if mode in ("auto", "app"):
        exe = find_chromium()
        if exe:
            profile = os.path.join(BASE_DIR, ".window_profile")
            subprocess.Popen([exe, f"--app={url}", f"--window-size={w},{h}", f"--user-data-dir={profile}",
                              "--no-first-run", "--no-default-browser-check", "--disable-sync"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "app"

    if mode in ("auto", "webview"):
        try:
            import webview
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            webview.create_window(CONFIG["name"], url, width=w, height=h, min_size=(720, 520),
                                  background_color="#000000")
            webview.start()
            httpd.shutdown()
            return "webview"
        except ImportError:
            pass
        except Exception as exc:  
            print(f"[warning] pywebview is unavailable ({exc}); falling back to the browser.")

    webbrowser.open(url)
    return "browser"


def main():
    httpd = NovaServer()
    base_url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    launch_url = f"{base_url}?t={TOKEN}"
    print(f"{CONFIG['name']} is starting...  ({base_url})")
    threading.Thread(target=LLM_.warmup, daemon=True).start()
    threading.Thread(target=httpd.watch_for_close, daemon=True).start()

    mode = launch_ui(launch_url, httpd)
    if mode == "webview":
        return
    print("Close the Nova window (or press Ctrl+C here) to quit.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
