import os
import sys
import re
import threading
import time
from queue import Queue

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from downloader.manager import DownloadManager
from downloader.config import VIDEO_QUALITIES, AUDIO_QUALITIES, AUDIO_CODECS
from downloader.utils import find_cookies_file

# Try import yt_dlp for metadata fetching
try:
    import yt_dlp
except ImportError:
    yt_dlp = None


# ──────────────────────────── Dark Theme (Raycast/Apple-inspired) ────────────────────────────
# Surface stack: each layer is 6-8 luminance points apart for subtle depth
# Never pure black — deep charcoal emits just enough light for surfaces to be distinguishable
THEME = {
    "bg":             "#121212",  # Base: deep charcoal, not #000
    "bg_surface":     "#1A1A1A",  # Cards, panels
    "bg_elevated":    "#242424",  # Elevated surfaces (inputs, dropdowns)
    "bg_overlay":     "#2C2C2C",  # Hover states, overlays
    "border":         "rgba(255,255,255,0.06)",  # Light border = elevation on dark
    "border_hover":   "rgba(255,255,255,0.12)",
    "text":           "#FFFFFF",  # Primary: off-white, not pure
    "text_secondary": "rgba(255,255,255,0.55)",  # Metadata, hints
    "text_muted":     "rgba(255,255,255,0.30)",  # Tertiary info
    "accent":         "#6C5CE7",  # Violet — used sparingly (~5% of UI)
    "accent_hover":   "#7E6EF0",
    "accent_pressed": "#5A4BD6",
    "success":        "#2ED573",
    "error":          "#FF6B6B",
    "warning":        "#FECA57",
    "pause":          "#FF9F43",
}


def build_stylesheet():
    t = THEME
    return f"""
    * {{
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        color: {t["text"]};
    }}
    QMainWindow, QWidget#central {{
        background: {t["bg"]};
    }}

    /* ── Cards ── */
    QFrame#card {{
        background: {t["bg_surface"]};
        border: 1px solid {t["border"]};
        border-radius: 10px;
        padding: 18px;
    }}

    /* ── Labels ── */
    QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel#title {{
        font-size: 18px;
        font-weight: 500;
        color: {t["text"]};
        letter-spacing: -0.3px;
    }}
    QLabel#subtitle {{
        font-size: 11px;
        color: {t["text_secondary"]};
        font-weight: 400;
    }}
    QLabel#sectionTitle {{
        font-size: 10px;
        font-weight: 500;
        color: {t["text_secondary"]};
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }}

    /* ── Inputs ── */
    QLineEdit, QTextEdit {{
        background: {t["bg_elevated"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 9px 12px;
        font-size: 13px;
        color: {t["text"]};
        selection-background-color: {t["accent"]};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {t["accent"]};
    }}
    QLineEdit::placeholder, QTextEdit::placeholder {{
        color: {t["text_muted"]};
    }}

    /* ── ComboBox ── */
    QComboBox {{
        background: {t["bg_elevated"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 7px 12px;
        font-size: 13px;
        min-width: 100px;
        color: {t["text"]};
    }}
    QComboBox:hover {{
        border-color: {t["border_hover"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {t["text_secondary"]};
        margin-right: 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {t["bg_surface"]};
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 4px;
        color: {t["text"]};
        selection-background-color: {t["accent"]};
        selection-color: #fff;
    }}

    /* ── Buttons ── */
    QPushButton {{
        border: none;
        border-radius: 6px;
        padding: 9px 18px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton#primary {{
        background: {t["accent"]};
        color: #ffffff;
    }}
    QPushButton#primary:hover {{
        background: {t["accent_hover"]};
    }}
    QPushButton#primary:pressed {{
        background: {t["accent_pressed"]};
    }}
    QPushButton#primary:disabled {{
        background: {t["bg_overlay"]};
        color: {t["text_muted"]};
    }}
    QPushButton#secondary {{
        background: {t["bg_elevated"]};
        color: {t["text"]};
        border: 1px solid {t["border"]};
    }}
    QPushButton#secondary:hover {{
        border-color: {t["border_hover"]};
        background: {t["bg_overlay"]};
    }}
    QPushButton#pause {{
        background: {t["warning"]};
        color: #000000;
    }}
    QPushButton#pause:hover {{
        background: {t["pause"]};
    }}
    QPushButton#danger {{
        background: transparent;
        color: {t["error"]};
        border: 1px solid {t["error"]};
    }}
    QPushButton#danger:hover {{
        background: {t["error"]};
        color: #000000;
    }}
    QPushButton#logToggle {{
        background: transparent;
        border: 1px solid {t["border"]};
        border-radius: 6px;
        padding: 5px 12px;
        font-size: 11px;
        color: {t["text_secondary"]};
    }}
    QPushButton#logToggle:hover {{
        border-color: {t["border_hover"]};
        color: {t["text"]};
    }}

    /* ── Table ── */
    QTableWidget {{
        background: {t["bg_surface"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        gridline-color: {t["border"]};
        font-size: 12px;
        color: {t["text"]};
    }}
    QTableWidget::item {{
        padding: 8px 10px;
        border-bottom: 1px solid {t["border"]};
    }}
    QTableWidget::item:selected {{
        background: {t["accent"]};
        color: #ffffff;
    }}
    QHeaderView::section {{
        background: {t["bg"]};
        color: {t["text_secondary"]};
        font-weight: 500;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 10px 10px;
        border: none;
        border-bottom: 1px solid {t["border"]};
    }}

    /* ── Progress Bar ── */
    QProgressBar {{
        background: {t["bg_elevated"]};
        border: none;
        border-radius: 4px;
        text-align: center;
        font-size: 10px;
        font-weight: 500;
        color: {t["text_secondary"]};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background: {t["accent"]};
        border-radius: 4px;
    }}

    /* ── Log Area ── */
    QTextEdit#log {{
        background: {t["bg"]};
        border: 1px solid {t["border"]};
        border-radius: 8px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 11px;
        color: {t["text_secondary"]};
        padding: 10px;
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: {t["border_hover"]};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t["text_muted"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """



# ──────────────────────────── Metadata Worker ────────────────────────────
class MetadataWorker(QThread):
    """Fetches video/audio metadata without downloading."""

    result_signal = pyqtSignal(str, dict)  # unique_id, metadata dict
    error_signal = pyqtSignal(str, str)  # unique_id, error message

    def __init__(self, unique_id, url):
        super().__init__()
        self.unique_id = unique_id
        self.url = url

    def run(self):
        try:
            if yt_dlp is None:
                self.error_signal.emit(self.unique_id, "yt-dlp not available")
                return

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "ignoreerrors": True,
            }

            cookies_path = find_cookies_file()
            if cookies_path:
                ydl_opts["cookiefile"] = cookies_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if info is None:
                    self.error_signal.emit(self.unique_id, "Could not extract info")
                    return

                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        self.error_signal.emit(self.unique_id, "Could not extract info")
                        return
                    info = entries[0]

                meta = {
                    "title": info.get("title", "Unknown"),
                    "channel": info.get("uploader")
                    or info.get("channel")
                    or info.get("uploader_id", "Unknown"),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "upload_date": info.get("upload_date", ""),
                }
                self.result_signal.emit(self.unique_id, meta)

        except Exception as e:
            self.error_signal.emit(self.unique_id, str(e))


# ──────────────────────────── Cancel Exception ────────────────────────────
class DownloadCancelled(Exception):
    """Raised inside yt-dlp progress hook to abort download."""

    pass


# ──────────────────────────── Download Worker ────────────────────────────
class DownloadWorker(QThread):
    status_signal = pyqtSignal(str, str)  # unique_id, status_text
    percent_signal = pyqtSignal(str, int)  # unique_id, percent (0-100)
    log_signal = pyqtSignal(str)  # log message
    finished_signal = pyqtSignal(str, bool, str)  # unique_id, success, message

    def __init__(self, unique_id, url, format_type, quality, codec, output_path):
        super().__init__()
        self.unique_id = unique_id
        self.url = url
        self.format_type = format_type
        self.quality = quality
        self.codec = codec
        self.output_path = output_path
        self._paused = False
        self._cancelled = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def cancel(self):
        self._cancelled = True
        self._paused = False

    @property
    def is_paused(self):
        return self._paused

    def _progress_hook(self, d):
        """Called by yt-dlp during download with progress info."""
        # Check cancel
        if self._cancelled:
            raise DownloadCancelled("Cancelled by user")

        # Check pause — block here until resumed or cancelled
        # Use short sleep intervals to avoid yt-dlp timeout issues
        pause_start = None
        while self._paused and not self._cancelled:
            self.status_signal.emit(self.unique_id, "Paused")
            if pause_start is None:
                pause_start = time.monotonic()
            # Timeout after 30 minutes of paused state to prevent infinite blocking
            if time.monotonic() - pause_start > 1800:
                self._cancelled = True
                raise DownloadCancelled("Pause timeout (30 min limit)")
            time.sleep(0.15)
        if self._cancelled:
            raise DownloadCancelled("Cancelled by user")

        status = d.get("status", "")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = int((downloaded / total) * 100)
                self.percent_signal.emit(self.unique_id, pct)
        elif status == "finished":
            self.percent_signal.emit(self.unique_id, 100)

    def run(self):
        try:
            self.status_signal.emit(self.unique_id, "Downloading...")
            self.percent_signal.emit(self.unique_id, 0)
            self.log_signal.emit(f"Starting: {self.url}")

            manager = DownloadManager(self.output_path)
            downloader, file_uuid = manager.download(
                self.url,
                self.format_type,
                quality=self.quality,
                codec=self.codec,
                progress_hook=self._progress_hook,
            )

            self.status_signal.emit(self.unique_id, "Processing...")
            downloader.cleanup_thumbnails(file_uuid)
            downloader.finalize_filename(file_uuid)

            self.status_signal.emit(self.unique_id, "Completed")
            self.percent_signal.emit(self.unique_id, 100)
            self.log_signal.emit(f"Completed: {self.url}")
            self.finished_signal.emit(self.unique_id, True, "")

        except DownloadCancelled:
            self.status_signal.emit(self.unique_id, "Cancelled")
            self.finished_signal.emit(self.unique_id, False, "Cancelled by user")

        except Exception as e:
            self.status_signal.emit(self.unique_id, "Failed")
            self.log_signal.emit(f"Failed: {self.url} — {e}")
            self.finished_signal.emit(self.unique_id, False, str(e))


# ──────────────────────────── Helpers ────────────────────────────
def format_duration(seconds):
    """Convert seconds to HH:MM:SS or MM:SS."""
    if not seconds or seconds <= 0:
        return "--:--"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_views(count):
    """Format view count nicely."""
    if not count or count <= 0:
        return ""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M views"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K views"
    return f"{count} views"


def format_date(date_str):
    """Format YYYYMMDD to DD.MM.YYYY."""
    if not date_str or len(date_str) != 8:
        return ""
    return f"{date_str[6:]}.{date_str[4:6]}.{date_str[:4]}"


# ──────────────────────────── Download Item Data ────────────────────────────
class DownloadItem:
    _counter = 0

    def __init__(self, url, format_type, quality, codec='aac'):
        DownloadItem._counter += 1
        self.id = f"dl_{DownloadItem._counter}"
        self.url = url
        self.format_type = format_type
        self.quality = quality
        self.codec = codec
        self.title = ""
        self.channel = ""
        self.duration = 0
        self.duration_str = "--:--"
        self.view_count = 0
        self.upload_date = ""
        self.status = "Fetching info…"
        self.meta_loaded = False
        self.finished = False
        self.success = False


# ──────────────────────────── Main Window ────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_visible = False
        self.items = {}  # id -> DownloadItem
        self.workers = {}  # id -> DownloadWorker
        self.meta_workers = {}  # id -> MetadataWorker
        self.pending_ids = []  # ids waiting to download
        self.active_count = 0
        self.MAX_CONCURRENT = 1
        self.total_finished = 0
        self.row_progress_bars = {}  # unique_id -> QProgressBar widget

        self.setWindowTitle("Media Downloader")
        self.setMinimumSize(960, 720)
        self.resize(1020, 780)

        self._build_ui()
        self.setStyleSheet(build_stylesheet())

    # ─────────────────── UI Construction ───────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # ── Header ──
        header = QHBoxLayout()
        header.setContentsMargins(0, 4, 0, 4)
        lbl_title = QLabel("Media Downloader")
        lbl_title.setObjectName("title")
        header.addWidget(lbl_title)
        header.addStretch()
        root.addLayout(header)

        # ── Settings Card ──
        settings_card = QFrame()
        settings_card.setObjectName("card")
        sc = QVBoxLayout(settings_card)
        sc.setSpacing(12)

        # Folder row
        lbl_folder = QLabel("DOWNLOAD FOLDER")
        lbl_folder.setObjectName("sectionTitle")
        sc.addWidget(lbl_folder)

        folder_row = QHBoxLayout()
        self.input_folder = QLineEdit()
        self.input_folder.setPlaceholderText("Select download folder…")
        self.input_folder.setText(os.path.join(os.getcwd(), "downloads"))
        folder_row.addWidget(self.input_folder, 1)

        btn_browse = QPushButton("Browse")
        btn_browse.setObjectName("secondary")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(btn_browse)
        sc.addLayout(folder_row)

        # Format + Codec + Quality row
        opts_row = QHBoxLayout()

        fmt_col = QVBoxLayout()
        lbl_fmt = QLabel("FORMAT")
        lbl_fmt.setObjectName("sectionTitle")
        fmt_col.addWidget(lbl_fmt)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["Video (MP4)", "Audio"])
        self.combo_format.currentIndexChanged.connect(self._on_format_changed)
        fmt_col.addWidget(self.combo_format)
        opts_row.addLayout(fmt_col)

        codec_col = QVBoxLayout()
        lbl_codec = QLabel("CODEC")
        lbl_codec.setObjectName("sectionTitle")
        codec_col.addWidget(lbl_codec)
        self.combo_codec = QComboBox()
        self.combo_codec.addItems(["AAC (m4a)", "MP3", "OPUS", "FLAC (lossless)", "Vorbis (ogg)"])
        codec_col.addWidget(self.combo_codec)
        opts_row.addLayout(codec_col)

        qual_col = QVBoxLayout()
        lbl_qual = QLabel("QUALITY")
        lbl_qual.setObjectName("sectionTitle")
        qual_col.addWidget(lbl_qual)
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["Best", "1080p", "720p", "480p"])
        qual_col.addWidget(self.combo_quality)
        opts_row.addLayout(qual_col)

        opts_row.addStretch()
        sc.addLayout(opts_row)

        # Cookies status row
        cookie_row = QHBoxLayout()
        lbl_cookie = QLabel("COOKIES")
        lbl_cookie.setObjectName("sectionTitle")
        cookie_row.addWidget(lbl_cookie, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_cookie_status = QLabel()
        self.lbl_cookie_status.setObjectName("subtitle")
        cookie_row.addWidget(self.lbl_cookie_status, 1)

        self.btn_cookies = QPushButton("Set cookies.txt")
        self.btn_cookies.setObjectName("secondary")
        self.btn_cookies.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cookies.setFixedWidth(130)
        self.btn_cookies.clicked.connect(self._set_cookies_file)
        cookie_row.addWidget(self.btn_cookies)

        cookie_row.addStretch()
        sc.addLayout(cookie_row)

        self._refresh_cookies_status()

        # URL input
        lbl_urls = QLabel("URLS  (one per line or space-separated)")
        lbl_urls.setObjectName("sectionTitle")
        sc.addWidget(lbl_urls)

        self.input_urls = QTextEdit()
        self.input_urls.setPlaceholderText("Paste URLs here…")
        self.input_urls.setFixedHeight(80)
        sc.addWidget(self.input_urls)

        # Action buttons
        actions_row = QHBoxLayout()

        self.btn_add = QPushButton("Add to Queue")
        self.btn_add.setObjectName("primary")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_urls)
        actions_row.addWidget(self.btn_add)

        self.btn_start = QPushButton("Start All")
        self.btn_start.setObjectName("primary")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._start_downloads)
        actions_row.addWidget(self.btn_start)

        self.btn_pause = QPushButton("Pause All")
        self.btn_pause.setObjectName("pause")
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.clicked.connect(self._pause_resume_all)
        self.btn_pause.setEnabled(False)
        actions_row.addWidget(self.btn_pause)

        self.btn_clear = QPushButton("Clear List")
        self.btn_clear.setObjectName("danger")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_list)
        actions_row.addWidget(self.btn_clear)

        actions_row.addStretch()
        sc.addLayout(actions_row)

        root.addWidget(settings_card)

        # ── Download Table ──
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["#", "Title / Info", "Duration", "Format", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 180)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        root.addWidget(self.table, 1)

        # ── Progress + Log Toggle ──
        prog_row = QHBoxLayout()
        self.lbl_progress = QLabel("Ready")
        self.lbl_progress.setObjectName("subtitle")
        prog_row.addWidget(self.lbl_progress)

        prog_row.addStretch()

        self.btn_log_toggle = QPushButton("Show Logs")
        self.btn_log_toggle.setObjectName("logToggle")
        self.btn_log_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_log_toggle.clicked.connect(self._toggle_log)
        prog_row.addWidget(self.btn_log_toggle)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setValue(0)
        prog_row.addWidget(self.progress_bar)
        root.addLayout(prog_row)

        # ── Log Area (hidden by default) ──
        self.log_area = QTextEdit()
        self.log_area.setObjectName("log")
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(130)
        self.log_area.setPlaceholderText("Logs will appear here…")
        self.log_area.setVisible(False)
        root.addWidget(self.log_area)

    # ─────────────────── Log Toggle ───────────────────
    def _toggle_log(self):
        self.log_visible = not self.log_visible
        self.log_area.setVisible(self.log_visible)
        self.btn_log_toggle.setText("Hide Logs" if self.log_visible else "Show Logs")

    # ─────────────────── Folder ───────────────────
    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if path:
            self.input_folder.setText(path)

    # ─────────────────── Cookies ───────────────────
    def _set_cookies_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select cookies.txt", "", "Cookie File (*.txt);;All Files (*)"
        )
        if path:
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            target = os.path.join(script_dir, "cookies.txt")
            try:
                import shutil
                shutil.copy2(path, target)
                self._log(f"Cookies copied to: cookies.txt")
                self._refresh_cookies_status()
            except Exception as e:
                self._log(f"Failed to copy cookies: {e}")

    def _refresh_cookies_status(self):
        cookies_path = find_cookies_file()
        t = THEME
        if cookies_path:
            self.lbl_cookie_status.setText("cookies.txt found")
            self.lbl_cookie_status.setStyleSheet(f"color: {t['success']};")
        else:
            self.lbl_cookie_status.setText("No cookies.txt — YouTube may require login")
            self.lbl_cookie_status.setStyleSheet(f"color: {t['text_muted']};")

    # ─────────────────── Format Change ───────────────────
    def _on_format_changed(self, idx):
        is_video = idx == 0
        self.combo_quality.setEnabled(is_video)
        self.combo_codec.setEnabled(not is_video)

        if is_video:
            self.combo_quality.clear()
            self.combo_quality.addItems(["Best", "1080p", "720p", "480p"])
        else:
            self.combo_quality.clear()
            self.combo_quality.addItems(["Best (320kbps)", "256kbps", "192kbps", "128kbps", "96kbps", "64kbps"])

    # ─────────────────── Find Table Row by ID ───────────────────
    def _find_row_by_id(self, unique_id):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == unique_id:
                return r
        return -1

    # ─────────────────── Refresh table row numbers & colors ───────────────────
    def _refresh_table_colors(self):
        t = THEME
        for r in range(self.table.rowCount()):
            uid_item = self.table.item(r, 0)
            if not uid_item:
                continue
            uid = uid_item.data(Qt.ItemDataRole.UserRole)
            item = self.items.get(uid)
            if item and item.finished and not item.success:
                color = QColor(t["error"])
                color.setAlpha(30)
                for c in range(self.table.columnCount()):
                    cell = self.table.item(r, c)
                    if cell:
                        cell.setBackground(color)

    # ─────────────────── Update Table Row ───────────────────
    def _update_table_row(self, unique_id):
        item = self.items.get(unique_id)
        if not item:
            return
        row = self._find_row_by_id(unique_id)
        if row < 0:
            return

        # Column 0: # (display row number, store id)
        idx_item = self.table.item(row, 0)
        if idx_item:
            idx_item.setText(str(row + 1))

        # Column 1: Title / Info
        if item.meta_loaded:
            info_parts = [item.title]
            sub_parts = []
            if item.channel:
                sub_parts.append(item.channel)
            if item.view_count:
                sub_parts.append(format_views(item.view_count))
            if item.upload_date:
                sub_parts.append(format_date(item.upload_date))
            if sub_parts:
                info_parts.append("  ·  ".join(sub_parts))
            display = "\n".join(info_parts)
        else:
            display = item.url
        info_item = self.table.item(row, 1)
        if info_item:
            info_item.setText(display)
            if item.meta_loaded:
                info_item.setToolTip(item.url)

        # Column 2: Duration
        dur_item = self.table.item(row, 2)
        if dur_item:
            dur_item.setText(item.duration_str if item.meta_loaded else "…")

        # Column 3: Format
        fmt_item = self.table.item(row, 3)
        if fmt_item:
            if item.format_type == "video":
                q = item.quality if item.quality != "best" else "Best"
                fmt_item.setText(f"MP4 · {q}")
            else:
                codec_ext = {
                    "aac": "AAC (m4a)",
                    "mp3": "MP3",
                    "opus": "OPUS",
                    "flac": "FLAC",
                    "vorbis": "Vorbis (ogg)",
                }
                codec_label = codec_ext.get(item.codec, item.codec.upper())
                fmt_item.setText(f"{codec_label}")

        # Column 4: Status — update progress bar format text
        pb = self.row_progress_bars.get(unique_id)
        if pb:
            pb.setFormat(item.status)

        # Row height for multi-line info
        if item.meta_loaded:
            self.table.setRowHeight(row, 52)

    def _renumber_rows(self):
        for r in range(self.table.rowCount()):
            idx_item = self.table.item(r, 0)
            if idx_item:
                idx_item.setText(str(r + 1))

    # ─────────────────── Add URLs ───────────────────
    def _add_urls(self):
        raw = self.input_urls.toPlainText().strip()
        if not raw:
            return
        urls = [u.strip() for u in raw.replace(" ", "\n").split("\n") if u.strip()]

        fmt_text = self.combo_format.currentText()
        format_type = "video" if "Video" in fmt_text else "audio"

        codec = AUDIO_CODECS.get(self.combo_codec.currentText(), "aac")

        if format_type == "video":
            quality = VIDEO_QUALITIES.get(self.combo_quality.currentText(), "best")
        else:
            quality = AUDIO_QUALITIES.get(self.combo_quality.currentText(), "best")

        for url in urls:
            dl = DownloadItem(url, format_type, quality, codec)
            self.items[dl.id] = dl

            row = self.table.rowCount()
            self.table.insertRow(row)

            # # col — stores unique id in UserRole
            idx_item = QTableWidgetItem(str(row + 1))
            idx_item.setData(Qt.ItemDataRole.UserRole, dl.id)
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, idx_item)

            # Info col
            self.table.setItem(row, 1, QTableWidgetItem(url))

            # Duration col
            dur = QTableWidgetItem("…")
            dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, dur)

            # Format col
            fmt = QTableWidgetItem("")
            fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, fmt)

            # Status col — use QProgressBar as cell widget
            pb = QProgressBar()
            pb.setMinimum(0)
            pb.setMaximum(100)
            pb.setValue(0)
            pb.setFormat(dl.status)
            pb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 4, pb)
            self.row_progress_bars[dl.id] = pb
            # Need a placeholder item for background color
            self.table.setItem(row, 4, QTableWidgetItem(""))

            self._update_table_row(dl.id)

            # Add to pending
            self.pending_ids.append(dl.id)

            # Start metadata fetch
            mw = MetadataWorker(dl.id, url)
            mw.result_signal.connect(self._on_metadata_ready)
            mw.error_signal.connect(self._on_metadata_error)
            self.meta_workers[dl.id] = mw
            mw.start()

        self.input_urls.clear()
        self._log(f"Added {len(urls)} URL(s) to queue.")
        self._update_progress()

    def _on_metadata_ready(self, unique_id, meta):
        item = self.items.get(unique_id)
        if not item:
            return
        item.title = meta.get("title", "")
        item.channel = meta.get("channel", "")
        item.duration = meta.get("duration", 0)
        item.duration_str = format_duration(item.duration)
        item.view_count = meta.get("view_count", 0)
        item.upload_date = meta.get("upload_date", "")
        item.meta_loaded = True
        item.status = "Ready"
        self._update_table_row(unique_id)
        self._log(f"Metadata loaded: {item.title}")
        # Cleanup worker ref
        self.meta_workers.pop(unique_id, None)

    def _on_metadata_error(self, unique_id, error):
        item = self.items.get(unique_id)
        if not item:
            return
        item.meta_loaded = False
        item.status = "Ready (no meta)"
        self._update_table_row(unique_id)
        self._log(f"Metadata fetch failed for {item.url}: {error}")
        self.meta_workers.pop(unique_id, None)

    # ─────────────────── Start Downloads ───────────────────
    def _start_downloads(self):
        if not self.pending_ids:
            self._log("Nothing to download. Add URLs first.")
            return
        self.btn_pause.setEnabled(True)
        self._process_queue()

    def _process_queue(self):
        while self.active_count < self.MAX_CONCURRENT and self.pending_ids:
            dl_id = self.pending_ids.pop(0)
            item = self.items.get(dl_id)
            if not item or item.finished:
                continue
            self._start_worker(dl_id)

    def _start_worker(self, dl_id):
        item = self.items.get(dl_id)
        if not item:
            return

        output_path = self.input_folder.text().strip() or os.path.join(
            os.getcwd(), "downloads"
        )
        os.makedirs(output_path, exist_ok=True)

        worker = DownloadWorker(
            unique_id=dl_id,
            url=item.url,
            format_type=item.format_type,
            quality=item.quality,
            codec=item.codec,
            output_path=os.path.abspath(output_path),
        )
        worker.status_signal.connect(self._on_worker_status)
        worker.percent_signal.connect(self._on_worker_percent)
        worker.log_signal.connect(self._log)
        worker.finished_signal.connect(self._on_worker_finished)
        self.workers[dl_id] = worker
        self.active_count += 1
        worker.start()

    def _on_worker_status(self, unique_id, text):
        item = self.items.get(unique_id)
        if item:
            item.status = text
        pb = self.row_progress_bars.get(unique_id)
        if pb:
            pb.setFormat(text)

    def _on_worker_percent(self, unique_id, pct):
        pb = self.row_progress_bars.get(unique_id)
        if pb:
            pb.setValue(pct)
            if pct < 100:
                pb.setFormat(f"%p%")

    def _on_worker_finished(self, unique_id, success, message):
        self.active_count -= 1
        self.total_finished += 1

        item = self.items.get(unique_id)
        if item:
            item.finished = True
            item.success = success

        # Remove worker
        self.workers.pop(unique_id, None)

        if success:
            # Remove successful download from list after a short delay for visibility
            QTimer.singleShot(1200, lambda uid=unique_id: self._remove_item(uid))
        else:
            # Mark failed row with error color
            row = self._find_row_by_id(unique_id)
            if row >= 0:
                color = QColor(THEME["error"])
                color.setAlpha(30)
                for c in range(self.table.columnCount()):
                    cell = self.table.item(row, c)
                    if cell:
                        cell.setBackground(color)
                if item:
                    item.status = f"Failed: {message[:60]}" if message else "Failed"
                    self._update_table_row(unique_id)

        self._update_progress()

        # Start next download after delay
        if self.pending_ids:
            QTimer.singleShot(1500, self._process_queue)
        elif self.active_count == 0:
            self.btn_pause.setEnabled(False)
            self._log("All downloads completed!")

    def _remove_item(self, unique_id):
        """Remove a successfully downloaded item from the table."""
        row = self._find_row_by_id(unique_id)
        if row >= 0:
            self.table.removeRow(row)
            self._renumber_rows()
        self.row_progress_bars.pop(unique_id, None)
        self._update_progress()

    # ─────────────────── Progress ───────────────────
    def _update_progress(self):
        total = len(self.items)
        finished = sum(1 for i in self.items.values() if i.finished)

        if total > 0:
            pct = int((finished / total) * 100)
            self.progress_bar.setValue(pct)
            success_count = sum(
                1 for i in self.items.values() if i.finished and i.success
            )
            fail_count = sum(
                1 for i in self.items.values() if i.finished and not i.success
            )
            self.lbl_progress.setText(
                f"{finished}/{total} done  —  {success_count} success  {fail_count} failed"
            )
        else:
            self.progress_bar.setValue(0)
            self.lbl_progress.setText("Ready")

    # ─────────────────── Pause / Resume ───────────────────
    def _pause_resume_all(self):
        any_paused = any(w.is_paused for w in self.workers.values() if w.isRunning())
        if any_paused:
            for w in self.workers.values():
                if w.isRunning():
                    w.resume()
            self.btn_pause.setText("Pause All")
            self.btn_pause.setObjectName("pause")
            self._log("Resumed all downloads.")
        else:
            for w in self.workers.values():
                if w.isRunning():
                    w.pause()
            self.btn_pause.setText("Resume All")
            self.btn_pause.setObjectName("primary")
            self._log("Paused all downloads.")

    # ─────────────────── Clear ───────────────────
    def _clear_list(self):
        for w in self.workers.values():
            if w.isRunning():
                w.cancel()
        for w in self.meta_workers.values():
            if w.isRunning():
                w.quit()
        self.workers.clear()
        self.meta_workers.clear()
        self.pending_ids.clear()
        self.items.clear()
        self.row_progress_bars.clear()
        self.active_count = 0
        self.total_finished = 0
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("Ready")
        self.btn_pause.setEnabled(False)
        self._log("Cleared download list.")

    # ─────────────────── Logging ───────────────────
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

    def _log(self, msg):
        clean = self._ANSI_RE.sub("", msg)
        self.log_area.append(clean)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())


# ──────────────────────────── Entry Point ────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
