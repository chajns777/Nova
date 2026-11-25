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

"""Turns anything you drop on Nova into something she can read.

text/code/markdown/json/log/html -> text          pdf (+scanned via PyMuPDF)  -> text / page images
docx, xlsx, csv                  -> text          images                     -> resized for the vision model
audio (optional faster-whisper)  -> transcript    video (optional opencv)    -> a few key frames
zip                              -> file listing
"""

import csv
import os
import re
import time
import uuid
import zipfile

from .config import UPLOAD_DIR
from .memory import tokens

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
TEXT_EXT = {".txt", ".md", ".markdown", ".log", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg",
            ".xml", ".html", ".htm", ".css", ".scss", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".vue", ".py",
            ".pyw", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".bat",
            ".ps1", ".sql", ".lua", ".kt", ".swift", ".r", ".tex", ".rtf", ".env", ".gitignore", ".srt", ".vtt"}
MAX_STORE_CHARS = 2_000_000
MAX_UPLOAD_BYTES = 300 * 1024 * 1024


def kind_of(name: str) -> str:
    ext = os.path.splitext(name.lower())[1]
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in (".xlsx", ".xlsm"):
        return "spreadsheet"
    if ext in (".csv", ".tsv"):
        return "table"
    if ext in (".zip",):
        return "archive"
    if ext in TEXT_EXT or ext == "":
        return "text"
    return "other"


def safe_name(name: str) -> str:
    name = os.path.basename(name or "file").strip() or "file"
    return re.sub(r"[^\w.\- ()]", "_", name)[:120]


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024

def _read_text(path: str) -> str:
    path = _assert_within_upload_dir(path)
    raw = open(path, "rb").read(MAX_STORE_CHARS * 2)
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)[:MAX_STORE_CHARS]
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("latin-1")[:MAX_STORE_CHARS]


def _read_html(path: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(_read_text(path), "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def _read_pdf(path: str, out_stem: str):
    text, pages, images, note = "", 0, [], ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return "", [], "This PDF is password-protected."
        pages = len(reader.pages)
        parts = []
        for i, page in enumerate(reader.pages[:250], 1):
            t = (page.extract_text() or "").strip()
            if t:
                parts.append(f"--- page {i} ---\n{t}")
        text = "\n\n".join(parts)
    except Exception as e:
        note = f"Couldn't read the PDF text ({e})."
    if len(text) < 40 * max(1, min(pages, 5)):
        try:
            import fitz
            MAX_PAGE_PX = 2400
            MAX_PAGE_PIXELS = 4_000_000  # ~12 MB RGB cap per page
            doc = fitz.open(path)
            try:
                for i in range(min(3, len(doc))):
                    page = doc[i]
                    w, h = page.rect.width, page.rect.height
                    if w <= 0 or h <= 0:
                        continue
                    scale = 110.0 / 72.0
                    scale = min(scale, MAX_PAGE_PX / w, MAX_PAGE_PX / h, (MAX_PAGE_PIXELS / (w * h)) ** 0.5)
                    if scale <= 0:
                        continue
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    p = f"{out_stem}.page{i + 1}.png"
                    pix.save(p)
                    images.append(p)
            finally:
                doc.close()
            note = (note + " " if note else "") + \
                   f"This PDF looks scanned, so I rendered its first {len(images)} page(s) as images."
        except ImportError:
            note = (note + " " if note else "") + \
                   "This PDF has little or no text (probably scanned). Install PyMuPDF (pip install pymupdf) so I can look at the pages."
        except Exception as e:
            note = f"{note} Couldn't render pages: {e}".strip()


MAX_ZIP_ENTRIES = 1000
MAX_UNCOMPRESSED_BYTES = 30 * 1024 * 1024  # 30 MB
MAX_COMPRESSION_RATIO = 100

def _check_zip_bomb(path: str):
    if not zipfile.is_zipfile(path):
        raise ValueError("Invalid or corrupted archive.")
    total_uncompressed = 0
    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise ValueError("Archive contains too many entries.")
        for info in infos:
            if info.file_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("Archive entry exceeds uncompressed size limit.")
            if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_COMPRESSION_RATIO:
                raise ValueError("Archive compression ratio exceeds safety limit.")
            with zf.open(info, "r") as stream:
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    total_uncompressed += len(chunk)
                    if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                        raise ValueError("Decompressed archive exceeds memory limit.")


def _read_docx(path: str) -> str:
    _check_zip_bomb(path)
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(path)
    out, chars = [], 0
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        line = ""
        if tag == "p":
            p = Paragraph(child, d)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            if style.startswith("Heading"):
                level = re.sub(r"\D", "", style) or "1"
                line = "#" * min(int(level), 4) + " " + t
            else:
                line = t
        elif tag == "tbl":
            rows = [" | ".join(c.text.strip().replace("\n", " ") for c in row.cells)
                    for row in Table(child, d).rows]
            line = "\n".join(rows)
        if line:
            out.append(line)
            chars += len(line)
            if chars >= MAX_STORE_CHARS:
                break
    return "\n".join(out)[:MAX_STORE_CHARS]


def _read_xlsx(path: str) -> str:
    _check_zip_bomb(path)
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        out = []
        for ws in wb.worksheets[:8]:
            rows, count = [], 0
            for row in ws.iter_rows(values_only=True):
                count += 1
                if count <= 60:
                    rows.append("\t".join("" if v is None else str(v) for v in row[:20]))
                if count >= 20000:
                    break
            out.append(f"## Sheet: {ws.title} ({count}{'+' if count >= 20000 else ''} rows)\n" + "\n".join(rows))
        return "\n\n".join(out)[:MAX_STORE_CHARS]
    finally:
        wb.close()


def _read_docx(path: str) -> str:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    d = docx.Document(path)
    out = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            t = p.text.strip()
            if not t:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            if style.startswith("Heading"):
                level = re.sub(r"\D", "", style) or "1"
                out.append("#" * min(int(level), 4) + " " + t)
            else:
                out.append(t)
        elif tag == "tbl":
            for row in Table(child, d).rows:
                out.append(" | ".join(c.text.strip().replace("\n", " ") for c in row.cells))
    return "\n".join(out)


def _read_xlsx(path: str) -> str:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets[:8]:
        rows, count = [], 0
        for row in ws.iter_rows(values_only=True):
            count += 1
            if count <= 60:
                rows.append("\t".join("" if v is None else str(v) for v in row[:20]))
            if count >= 20000:
                break
        out.append(f"## Sheet: {ws.title} ({count}{'+' if count >= 20000 else ''} rows)\n" + "\n".join(rows))
    return "\n\n".join(out)


def _read_csv(path: str) -> str:
    text = _read_text(path)
    delim = "\t" if path.lower().endswith(".tsv") else ","
    try:
        delim = csv.Sniffer().sniff(text[:4000], delimiters=",;\t|").delimiter
    except csv.Error:
        pass
    rows = list(csv.reader(text.splitlines(), delimiter=delim))
    if not rows:
        return ""
    head = f"{len(rows) - 1} data rows, {len(rows[0])} columns. Columns: {', '.join(rows[0][:30])}\n"
    return head + "\n".join("\t".join(r[:20]) for r in rows[:60])


def _transcribe(path: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "", "I can't listen to audio yet. Run 'pip install faster-whisper' and I will."
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(path, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments)
        return text, f"Transcribed locally ({info.language}, {info.duration:.0f}s)."
    except Exception as e:
        return "", f"Transcription failed: {e}"


def _video_frames(path: str, out_stem: str):
    try:
        import cv2
    except ImportError:
        return [], "Install opencv (pip install opencv-python-headless) and I can look at video frames."
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames = []
    for i in range(4):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / 4) if total else 0)
        ok, frame = cap.read()
        if ok:
            p = f"{out_stem}.frame{i + 1}.jpg"
            cv2.imwrite(p, frame)
            frames.append(p)
    cap.release()
    dur = f"{total / fps:.0f}s" if fps and total else "unknown length"
    return frames, f"Video {w}x{h}, {dur}. I'm looking at {len(frames)} frames spread across it."


def prepare_image(path: str, out_path: str, max_side: int = 1024) -> str:
    try:
        from PIL import Image
        im = Image.open(path)
        im.seek(0)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        im.save(out_path, "JPEG", quality=85)
        return out_path
    except Exception:
        return path


def ingest(data: bytes, original_name: str) -> dict:
    name = safe_name(original_name)
    fid = uuid.uuid4().hex[:10]
    upload_root = os.path.realpath(UPLOAD_DIR)
    stem = os.path.join(upload_root, fid)
    ext = os.path.splitext(name)[1].lower()
    path = os.path.realpath(f"{stem}{ext}")
    if os.path.commonpath([upload_root, path]) != upload_root:
        raise ValueError("Invalid upload path")
    with open(path, "wb") as f:
        f.write(data)

    kind = kind_of(name)
    text, images, note = "", [], ""
    try:
        if kind == "image":
            images = [prepare_image(path, f"{stem}.vis.jpg")]
        elif kind == "pdf":
            text, images, note = _read_pdf(path, stem)
        elif kind == "docx":
            text = _read_docx(path)
        elif kind == "spreadsheet":
            text = _read_xlsx(path)
        elif kind == "table":
            text = _read_csv(path)
        elif kind == "audio":
            text, note = _transcribe(path)
        elif kind == "video":
            images, note = _video_frames(path, stem)
        elif kind == "archive":
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            text = f"Zip with {len(names)} items:\n" + "\n".join(names[:200])
        elif kind == "text":
            text = _read_html(path) if ext in (".html", ".htm") else _read_text(path)
        else:
            note = "I don't know how to read this file type yet."
    except Exception as e:
        note = f"I couldn't read this file: {e}"

    check = ""
    if kind == "text" and ext in (".py", ".pyw", ".json", ".js", ".mjs"):
        from . import codecheck
        check = codecheck.check(text, ext, name)

    text_path = os.path.realpath(f"{stem}.txt")
    if os.path.commonpath([upload_root, text_path]) != upload_root:
        raise ValueError("Invalid text path")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"id": fid, "name": name, "kind": kind, "size": len(data), "path": path, "text_path": text_path,
            "images": images, "chars": len(text), "note": note, "check": check, "caption": "", "ts": time.time()}


def full_text(rec: dict) -> str:
    try:
        return open(rec["text_path"], "r", encoding="utf-8").read()
    except OSError:
        return ""


def best_chunks(text: str, query: str, budget: int = 5000, size: int = 900) -> str:
    if len(text) <= budget:
        return text
    paras = re.split(r"\n\s*\n|\n(?=---)", text)
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            chunks.append(cur)
            cur = ""
        cur += p + "\n"
        while len(cur) > size * 2:
            chunks.append(cur[:size * 2])
            cur = cur[size * 2:]
    if cur.strip():
        chunks.append(cur)
    q = set(tokens(query))
    scored = []
    for i, c in enumerate(chunks):
        t = tokens(c)
        score = len(q & set(t)) / (len(t) ** 0.5 + 1) if q else 0
        scored.append((score, i))
    chosen, used = set(), 0
    if chunks:                                
        chosen.add(0)
        used += len(chunks[0])
    for score, i in sorted(scored, key=lambda x: -x[0]):
        if i in chosen or score <= 0:
            continue
        if used + len(chunks[i]) > budget:
            continue
        chosen.add(i)
        used += len(chunks[i])
    return "\n[...]\n".join(chunks[i].strip() for i in sorted(chosen))
