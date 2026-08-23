# -*- coding: utf-8 -*-
"""
Pro Downloader — نسخة كاملة شغالة فعليًا (pywebview + yt-dlp)
------------------------------------------------------------------
المتطلبات (تُثبَّت مرة واحدة عن طريق build_program.bat):
    pip install yt-dlp pyperclip pywebview pythonnet pyinstaller
"""

import os
import sys
import json
import threading
import traceback

import webview

from downloader_core import (
    QUALITY_OPTIONS,
    detect_platform,
    download,
    human_size,
    load_history,
    load_settings,
    new_history_entry,
    save_history,
    save_settings,
)


# ============ الموارد المرفقة (ffmpeg + الأيقونة) ============

def _resource_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _setup_bundled_ffmpeg():
    ffmpeg_path = os.path.join(_resource_dir(), "ffmpeg.exe")
    if os.path.isfile(ffmpeg_path):
        os.environ["PATH"] = _resource_dir() + os.pathsep + os.environ.get("PATH", "")


def _set_windows_app_id():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "ProDownloader.App.1")
        except Exception:
            pass


_set_windows_app_id()
_setup_bundled_ffmpeg()


# ============ الـ API المعروض للواجهة (JS) ============

class Api:
    def __init__(self):
        self.window = None
        self.settings = load_settings()
        self.history = load_history()
        self._busy = False
        self._lock = threading.Lock()

    # ---- بيانات أولية تحتاجها الواجهة عند الفتح ----
    def get_bootstrap(self):
        return {
            "settings": self.settings,
            "history": self.history,
            "qualities": QUALITY_OPTIONS,
        }

    # ---- لصق الرابط من الحافظة ----
    def paste_clipboard(self):
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    # ---- اختيار مجلد الحفظ ----
    def pick_folder(self):
        try:
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        except Exception:
            result = None
        if not result:
            return None
        path = result[0] if isinstance(result, (list, tuple)) else result
        self.settings["save_path"] = path
        save_settings(self.settings)
        return path

    # ---- حفظ الإعدادات (لغة / ثيم) ----
    def save_settings_api(self, partial):
        self.settings.update(partial or {})
        save_settings(self.settings)
        return True

    # ---- بدء التحميل ----
    def start_download(self, url, quality_key):
        url = (url or "").strip()
        if not url:
            self._push_error(None, "حطي رابط الفيديو الأول.")
            return False

        platform = detect_platform(url)
        if not platform:
            self._push_error(None, "الرابط ده مش من منصة مدعومة (يوتيوب، تيك توك، فيسبوك، إنستجرام).")
            return False

        with self._lock:
            if self._busy:
                self._push_error(None, "في تحميل شغال دلوقتي، استني لحد ما يخلص.")
                return False
            self._busy = True

        entry = new_history_entry(url, quality_key, platform)
        self.history.insert(0, entry)
        save_history(self.history)
        self._push(f"window.onDownloadStarted({json.dumps(entry)})")

        threading.Thread(target=self._download_worker, args=(entry, url, quality_key), daemon=True).start()
        return True

    def retry_download(self, entry_id):
        original = next((h for h in self.history if h.get("id") == entry_id), None)
        if not original:
            self._push_error(None, "العملية دي مش موجودة في السجل.")
            return False
        return self.start_download(original["url"], original["quality"])

    def _download_worker(self, entry, url, quality_key):
        try:
            def cb(progress):
                self._push(f"window.onDownloadProgress({json.dumps(dict(progress, id=entry['id']))})")

            result = download(url, quality_key, self.settings["save_path"], cb)

            entry["status"] = "success"
            entry["title"] = result["title"]
            entry["filepath"] = result["filepath"]
            entry["size"] = human_size(result["size"])
            entry["error"] = None
        except Exception as e:
            traceback.print_exc()
            entry["status"] = "failed"
            entry["error"] = str(e)
        finally:
            with self._lock:
                self._busy = False
            save_history(self.history)
            self._push(f"window.onDownloadFinished({json.dumps(entry)})")

    def _push(self, js_call):
        try:
            self.window.evaluate_js(js_call)
        except Exception:
            pass

    def _push_error(self, entry_id, msg):
        self._push(f"window.onDownloadError({json.dumps({'id': entry_id, 'message': msg})})")


def main():
    api = Api()
    index_path = os.path.join(_resource_dir(), "web", "index.html")
    icon_path = os.path.join(_resource_dir(), "ProDownloader.ico")

    kwargs = dict(
        title="Pro Downloader",
        url=index_path,
        js_api=api,
        width=1180,
        height=760,
        min_size=(900, 620),
        background_color="#191919",
        text_select=True,
    )
    try:
        window = webview.create_window(**kwargs)
    except TypeError:
        kwargs.pop("text_select", None)
        window = webview.create_window(**kwargs)

    api.window = window

    start_kwargs = {}
    if os.path.isfile(icon_path):
        start_kwargs["icon"] = icon_path

    try:
        webview.start(**start_kwargs)
    except TypeError:
        start_kwargs.pop("icon", None)
        webview.start(**start_kwargs)


if __name__ == "__main__":
    main()
