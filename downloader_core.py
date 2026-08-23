# -*- coding: utf-8 -*-
"""
منطق التحميل الأساسي (بدون أي واجهة) — يُستخدم من main.py
"""

import os
import re
import sys
import json
import uuid
import time
import datetime

APP_NAME = "ProDownloader"


# ============ مسار تخزين الإعدادات والسجل (دائم بين مرات التشغيل) ============

def app_data_dir():
    """مسار قابل للكتابة يعيش برا مجلد الـ exe المؤقت (اللي بيتمسح كل مرة
    مع PyInstaller onefile) عشان الإعدادات والسجل يفضلوا محفوظين."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def default_downloads_dir():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads", APP_NAME)
    os.makedirs(downloads, exist_ok=True)
    return downloads


SETTINGS_PATH = lambda: os.path.join(app_data_dir(), "settings.json")
HISTORY_PATH = lambda: os.path.join(app_data_dir(), "history.json")

DEFAULT_SETTINGS = {
    "language": "ar",
    "theme": "dark",
    "save_path": None,  # يتحدد أول مرة تشغيل فعلي
}


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH(), "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    if not settings.get("save_path"):
        settings["save_path"] = default_downloads_dir()
    return settings


def save_settings(settings):
    try:
        with open(SETTINGS_PATH(), "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_history():
    try:
        with open(HISTORY_PATH(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    try:
        # نفضل نحتفظ بآخر 200 عملية بس عشان الملف مايكبرش من غير داعي
        with open(HISTORY_PATH(), "w", encoding="utf-8") as f:
            json.dump(history[:200], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============ التعرف على المنصة من الرابط ============

PLATFORM_PATTERNS = [
    ("yt", re.compile(r"(youtube\.com|youtu\.be)", re.I)),
    ("tt", re.compile(r"tiktok\.com", re.I)),
    ("fb", re.compile(r"(facebook\.com|fb\.watch)", re.I)),
    ("ig", re.compile(r"instagram\.com", re.I)),
]


def detect_platform(url):
    for key, pattern in PLATFORM_PATTERNS:
        if pattern.search(url or ""):
            return key
    return None


SUPPORTED_PLATFORMS_LABEL = "YouTube, TikTok, Facebook, Instagram"


# ============ خيارات الجودة ============

QUALITY_OPTIONS = [
    {"key": "8k", "label": "8K (4320p)", "height": 4320},
    {"key": "4k", "label": "4K (2160p)", "height": 2160},
    {"key": "2k", "label": "2K (1440p)", "height": 1440},
    {"key": "1080", "label": "1080p Full HD", "height": 1080},
    {"key": "720", "label": "720p HD", "height": 720},
    {"key": "480", "label": "480p", "height": 480},
    {"key": "audio", "label": "Audio only (MP3)", "height": None},
]

QUALITY_HEIGHT = {q["key"]: q["height"] for q in QUALITY_OPTIONS}


def format_selector(quality_key):
    """يبني عبارة اختيار الصيغة بتاعة yt-dlp. yt-dlp نفسه بيختار أعلى جودة
    متاحة فعليًا للفيديو ده حتى الحد المطلوب - لو الفيديو مش متاح بجودة
    عالية (شائع في تيك توك/فيسبوك/إنستجرام)، هينزل بأعلى جودة موجودة تلقائيًا
    من غير ما يفشل."""
    if quality_key == "audio":
        return "bestaudio/best"
    height = QUALITY_HEIGHT.get(quality_key, 1080)
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best[height<={height}]/best"


def human_size(num_bytes):
    if not num_bytes:
        return "—"
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def now_date_str():
    return datetime.date.today().isoformat()


def new_history_entry(url, quality_key, platform):
    return {
        "id": str(uuid.uuid4()),
        "url": url,
        "platform": platform,
        "quality": quality_key,
        "title": url,
        "date": now_date_str(),
        "size": None,
        "status": "in_progress",
        "filepath": None,
        "error": None,
    }


def download(url, quality_key, save_path, progress_callback):
    """يحمّل فيديو باستخدام yt-dlp. بيرجّع dict فيه تفاصيل النتيجة."""
    import yt_dlp

    fmt = format_selector(quality_key)
    outtmpl = os.path.join(save_path, "%(title).150B [%(id)s].%(ext)s")

    ydl_opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [lambda d: _on_progress(d, progress_callback)],
    }

    if quality_key == "audio":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    progress_callback({"status": "starting", "message": "جارٍ جلب معلومات الفيديو..."})

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
        if quality_key == "audio":
            filepath = os.path.splitext(filepath)[0] + ".mp3"

    size = None
    if filepath and os.path.isfile(filepath):
        size = os.path.getsize(filepath)

    return {
        "title": info.get("title") or url,
        "filepath": filepath,
        "size": size,
        "duration": info.get("duration"),
    }


def _on_progress(d, progress_callback):
    if d.get("status") == "downloading":
        pct_str = d.get("_percent_str", "").strip()
        speed_str = d.get("_speed_str", "").strip()
        progress_callback({
            "status": "downloading",
            "message": f"جارٍ التحميل... {pct_str} ({speed_str})",
            "percent": _parse_percent(pct_str),
        })
    elif d.get("status") == "finished":
        progress_callback({"status": "processing", "message": "جارٍ المعالجة النهائية..."})


def _parse_percent(pct_str):
    try:
        return float(pct_str.replace("%", "").strip())
    except Exception:
        return None
