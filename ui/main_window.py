"""
Main Window - AI Video Director MVP v1
Premium dark UI with PySide6 + Queue System
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QDoubleSpinBox, QFrame, QTextEdit,
    QProgressBar, QFileDialog, QSizePolicy, QGridLayout,
    QScrollArea, QSpacerItem, QSplitter,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QColor

from ui.styles import MAIN_STYLE
from ui.preview_widget import PREVIEW_STYLE, PreviewWidget
from ui.worker import RenderWorker
from subtitle.extractor import SubtitleExtractor
from subtitle.preset_loader import PresetLoader
from config import load_config, get_preset_dir
from renderer.ffmpeg_renderer import FFmpegRenderer
from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp

logger = logging.getLogger(__name__)


# ─── Job Data Model ───────────────────────────────────────────────────────────

@dataclass
class RenderJob:
    """Satu item dalam antrian render."""
    video_path: str
    intro_path: Optional[str]
    subtitle_path: str
    subtitle_start: str
    subtitle_preset: str
    auto_hook: bool
    crop_settings: dict
    # Status: "pending" | "running" | "done" | "failed"
    status: str = "pending"
    output_path: str = ""
    error_msg: str = ""

    @property
    def name(self) -> str:
        return Path(self.video_path).name

    @property
    def status_icon(self) -> str:
        return {
            "pending": "⏳",
            "running": "⚙",
            "done":    "✓",
            "failed":  "✗",
        }.get(self.status, "?")


# ─── Queue Item Widget ────────────────────────────────────────────────────────

class QueueItemWidget(QFrame):
    """Widget satu baris di antrian render."""

    def __init__(self, job: RenderJob, index: int, on_remove):
        super().__init__()
        self.job = job
        self.setObjectName("queue_item")
        self.setFixedHeight(52)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(8)

        # Index
        self._idx_lbl = QLabel(f"{index + 1:02d}")
        self._idx_lbl.setObjectName("queue_idx")
        self._idx_lbl.setFixedWidth(24)
        self._idx_lbl.setAlignment(Qt.AlignCenter)

        # Icon status
        self._icon_lbl = QLabel("⏳")
        self._icon_lbl.setFixedWidth(20)
        self._icon_lbl.setAlignment(Qt.AlignCenter)
        self._icon_lbl.setObjectName("queue_icon_pending")

        # Info
        info_col = QVBoxLayout()
        info_col.setSpacing(1)

        self._name_lbl = QLabel(job.name)
        self._name_lbl.setObjectName("queue_name")
        # Elide panjang
        self._name_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        sub_text = f"Subtitle: {Path(job.subtitle_path).name}  ·  Start: {job.subtitle_start}"
        if job.intro_path:
            sub_text += f"  ·  Intro: {Path(job.intro_path).name}"
        self._sub_lbl = QLabel(sub_text)
        self._sub_lbl.setObjectName("queue_sub")
        self._sub_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        info_col.addWidget(self._name_lbl)
        info_col.addWidget(self._sub_lbl)

        # Remove button (hidden saat running)
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setObjectName("queue_remove_btn")
        self._remove_btn.setFixedSize(24, 24)
        self._remove_btn.setCursor(Qt.PointingHandCursor)
        self._remove_btn.clicked.connect(lambda: on_remove(self))

        lay.addWidget(self._idx_lbl)
        lay.addWidget(self._icon_lbl)
        lay.addLayout(info_col)
        lay.addWidget(self._remove_btn)

    def set_status(self, status: str):
        self.job.status = status
        icons = {
            "pending": ("⏳", "queue_icon_pending"),
            "running": ("⚙",  "queue_icon_running"),
            "done":    ("✓",  "queue_icon_done"),
            "failed":  ("✗",  "queue_icon_failed"),
        }
        icon_char, obj_name = icons.get(status, ("?", "queue_icon_pending"))
        self._icon_lbl.setText(icon_char)
        self._icon_lbl.setObjectName(obj_name)
        self._icon_lbl.style().unpolish(self._icon_lbl)
        self._icon_lbl.style().polish(self._icon_lbl)

        # Sembunyikan remove saat running
        self._remove_btn.setVisible(status not in ("running", "done"))

    def update_index(self, index: int):
        self._idx_lbl.setText(f"{index + 1:02d}")


# ─── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker: RenderWorker = None
        self._config = load_config()

        # Queue state
        self._queue: List[RenderJob] = []
        self._queue_widgets: List[QueueItemWidget] = []
        self._queue_running = False
        self._current_job_idx = -1

        self._setup_window()
        self._setup_ui()
        self._apply_style()
        self._check_environment()
        self._wire_preview()

    # ─── Window Setup ────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("AI Video Director")
        self.setMinimumSize(980, 680)
        self.resize(1280, 720)

    # ─── UI Setup ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Root horizontal layout: form kiri, video kanan (splitter)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)

        # Left panel (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        scroll.setWidget(content)

        inner = QVBoxLayout(content)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(14)

        inner.addWidget(self._build_header())
        inner.addWidget(self._build_separator())
        inner.addWidget(self._build_input_card())
        inner.addWidget(self._build_settings_card())
        inner.addWidget(self._build_add_button())
        inner.addWidget(self._build_queue_card())
        inner.addWidget(self._build_progress_card())
        inner.addStretch()

        # Video preview di kanan
        self._preview = PreviewWidget()
        self._preview.setMinimumWidth(480)

        splitter.addWidget(scroll)
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([480, 800])

        root.addWidget(splitter)

        self._preview_debounce = QTimer(self)
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.setInterval(250)
        self._preview_debounce.timeout.connect(self._refresh_preview_overlays)

    # ─── Header ──────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("AI VIDEO DIRECTOR")
        title.setObjectName("app_title")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        sub = QLabel("MVP v1.0  ·  Gemini + FFmpeg  ·  Queue Mode")
        sub.setObjectName("app_subtitle")
        sub.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left.addWidget(title)
        left.addWidget(sub)

        lay.addLayout(left)
        lay.addStretch()

        self._env_badge = QLabel("● Checking...")
        self._env_badge.setObjectName("status_running")
        self._env_badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._env_badge.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self._env_badge)

        return w

    # ─── Separator ───────────────────────────────────────────────────────────

    def _build_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    # ─── Input Card ──────────────────────────────────────────────────────────

    def _build_input_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # Section title dengan badge counter
        hdr = QHBoxLayout()
        lbl = QLabel("INPUT  —  Isi form lalu klik ＋ Tambah")
        lbl.setObjectName("section_label")
        hdr.addWidget(lbl)
        hdr.addStretch()
        lay.addLayout(hdr)

        # Video file
        lay.addLayout(self._build_file_row(
            label="Video File",
            attr="_video_edit",
            placeholder="Pilih file video...",
            file_filter="Video Files (*.mp4 *.mov *.avi *.mkv *.webm)",
            on_selected=self._on_video_selected,
        ))

        # Intro video (opsional)
        lay.addLayout(self._build_file_row(
            label="Intro Video",
            attr="_intro_edit",
            placeholder="(Opsional) Pilih video intro...",
            file_filter="Video Files (*.mp4 *.mov *.avi *.mkv *.webm)",
        ))

        # Subtitle file
        lay.addLayout(self._build_file_row(
            label="Subtitle (.srt)",
            attr="_subtitle_edit",
            placeholder="Pilih file subtitle .srt...",
            file_filter="Subtitle Files (*.srt)",
        ))

        # Time row
        lay.addLayout(self._build_time_row())

        return card

    def _build_file_row(
        self, label, attr, placeholder, file_filter, on_selected=None
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setObjectName("field_label")
        lbl.setMinimumWidth(90)
        lbl.setMaximumWidth(120)
        lbl.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        setattr(self, attr, edit)

        btn = QPushButton("Browse")
        btn.setObjectName("browse_btn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        def _browse():
            path, _ = QFileDialog.getOpenFileName(self, f"Pilih {label}", "", file_filter)
            if path:
                edit.setText(path)
                if on_selected:
                    on_selected(path)

        btn.clicked.connect(_browse)

        row.addWidget(lbl)
        row.addWidget(edit)
        row.addWidget(btn)
        return row

    def _build_time_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl_s = QLabel("Start Time")
        lbl_s.setObjectName("field_label")
        lbl_s.setMinimumWidth(70)
        lbl_s.setMaximumWidth(90)
        lbl_s.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self._start_edit = QLineEdit()
        self._start_edit.setObjectName("time_input")
        self._start_edit.setPlaceholderText("00:00:00.000")
        self._start_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._start_edit.setToolTip(
            "Waktu subtitle di video ASLI yang sesuai dengan awal video clip ini.\n"
            "Contoh: jika clip berasal dari menit 35:20 video asli, isi 00:35:20"
        )
        self._start_edit.textChanged.connect(self._update_end_time)

        lbl_e = QLabel("End Time")
        lbl_e.setObjectName("field_label")
        lbl_e.setMinimumWidth(60)
        lbl_e.setMaximumWidth(80)
        lbl_e.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self._end_edit = QLineEdit()
        self._end_edit.setObjectName("time_input")
        self._end_edit.setPlaceholderText("AUTO")
        self._end_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._end_edit.setReadOnly(True)
        self._end_edit.setToolTip("Dihitung otomatis: Subtitle Start + Durasi Video")

        row.addWidget(lbl_s)
        row.addWidget(self._start_edit)
        row.addSpacing(8)
        row.addWidget(lbl_e)
        row.addWidget(self._end_edit)
        return row

    # ─── Settings Card ───────────────────────────────────────────────────────

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        lbl = QLabel("SETTINGS")
        lbl.setObjectName("section_label")
        lay.addWidget(lbl)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_style = QLabel("Subtitle Style")
        lbl_style.setObjectName("field_label")
        lbl_style.setMinimumWidth(90)
        lbl_style.setMaximumWidth(120)
        lbl_style.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self._style_combo = QComboBox()
        self._style_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._populate_presets()
        self._style_combo.setToolTip("Pilih preset tampilan subtitle")

        self._hook_check = QCheckBox("Auto Hook")
        self._hook_check.setChecked(True)
        self._hook_check.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._hook_check.setToolTip(
            "AI akan mencari bagian paling menarik dan memindahkannya ke awal video"
        )

        row1.addWidget(lbl_style)
        row1.addWidget(self._style_combo)
        row1.addSpacing(8)
        row1.addWidget(self._hook_check)

        lay.addLayout(row1)
        lay.addWidget(self._build_separator())

        crop_lbl = QLabel("CROP MARGINS (16:9)")
        crop_lbl.setObjectName("section_label")
        lay.addWidget(crop_lbl)
        lay.addLayout(self._build_crop_row())

        return card

    def _populate_presets(self):
        try:
            loader = PresetLoader(str(get_preset_dir()))
            presets = loader.available_presets()
        except Exception:
            presets = ["Modern01", "Modern02", "Podcast", "Bold"]
        self._style_combo.clear()
        for p in presets:
            self._style_combo.addItem(p)
        default = self._config.get("subtitle", {}).get("default_preset", "Modern01")
        idx = self._style_combo.findText(default)
        if idx >= 0:
            self._style_combo.setCurrentIndex(idx)

    def _build_crop_row(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setHorizontalSpacing(12)

        cfg = self._config.get("crop", {})
        labels   = ["Left %", "Right %", "Top %", "Bottom %"]
        keys     = ["left_pct", "right_pct", "top_pct", "bottom_pct"]
        defaults = [8, 8, 4, 10]
        self._crop_spins = {}

        for col, (lbl_text, key, default) in enumerate(zip(labels, keys, defaults)):
            lbl = QLabel(lbl_text)
            lbl.setObjectName("field_label")
            lbl.setAlignment(Qt.AlignCenter)

            spin = QDoubleSpinBox()
            spin.setRange(0, 49)
            spin.setSingleStep(0.5)
            spin.setDecimals(1)
            spin.setValue(cfg.get(key, default))
            spin.setToolTip(f"Margin {lbl_text} dari tepi video (%)")
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            spin.setMinimumWidth(60)

            self._crop_spins[key] = spin
            spin.valueChanged.connect(self._schedule_preview_refresh)
            grid.addWidget(lbl,  0, col, Qt.AlignCenter)
            grid.addWidget(spin, 1, col, Qt.AlignCenter)
            grid.setColumnStretch(col, 1)

        return grid

    # ─── Add to Queue Button ──────────────────────────────────────────────────

    def _build_add_button(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)

        self._add_btn = QPushButton("＋   TAMBAH KE ANTRIAN")
        self._add_btn.setObjectName("add_btn")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.clicked.connect(self._on_add_to_queue)
        self._add_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._clear_form_btn = QPushButton("↺  Reset Form")
        self._clear_form_btn.setObjectName("browse_btn")
        self._clear_form_btn.setCursor(Qt.PointingHandCursor)
        self._clear_form_btn.clicked.connect(self._reset_form)
        self._clear_form_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        lay.addWidget(self._add_btn)
        lay.addWidget(self._clear_form_btn)
        return w

    # ─── Queue Card ──────────────────────────────────────────────────────────

    def _build_queue_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # Header antrian
        hdr = QHBoxLayout()
        self._queue_lbl = QLabel("ANTRIAN  (0 video)")
        self._queue_lbl.setObjectName("section_label")

        self._start_queue_btn = QPushButton("▶   MULAI ANTRIAN")
        self._start_queue_btn.setObjectName("start_btn")
        self._start_queue_btn.setCursor(Qt.PointingHandCursor)
        self._start_queue_btn.clicked.connect(self._on_start_queue)
        self._start_queue_btn.setEnabled(False)
        self._start_queue_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self._clear_queue_btn = QPushButton("🗑  Hapus Semua")
        self._clear_queue_btn.setObjectName("browse_btn")
        self._clear_queue_btn.setCursor(Qt.PointingHandCursor)
        self._clear_queue_btn.clicked.connect(self._on_clear_queue)
        self._clear_queue_btn.setEnabled(False)
        self._clear_queue_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        hdr.addWidget(self._queue_lbl)
        hdr.addStretch()
        hdr.addWidget(self._clear_queue_btn)
        hdr.addWidget(self._start_queue_btn)
        lay.addLayout(hdr)

        # Separator
        lay.addWidget(self._build_separator())

        # Scroll area untuk list item antrian
        self._queue_scroll = QScrollArea()
        self._queue_scroll.setWidgetResizable(True)
        self._queue_scroll.setFrameShape(QFrame.NoFrame)
        self._queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._queue_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._queue_scroll.setFixedHeight(200)

        self._queue_content = QWidget()
        self._queue_list_layout = QVBoxLayout(self._queue_content)
        self._queue_list_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_list_layout.setSpacing(4)
        self._queue_list_layout.addStretch()
        self._queue_scroll.setWidget(self._queue_content)

        # Placeholder saat antrian kosong
        self._queue_placeholder = QLabel("Antrian kosong — isi form di atas lalu klik ＋ Tambah")
        self._queue_placeholder.setObjectName("queue_placeholder")
        self._queue_placeholder.setAlignment(Qt.AlignCenter)
        self._queue_placeholder.setFixedHeight(200)
        lay.addWidget(self._queue_placeholder)
        lay.addWidget(self._queue_scroll)
        self._queue_scroll.hide()

        # Queue progress info
        self._queue_progress_lbl = QLabel("")
        self._queue_progress_lbl.setObjectName("queue_progress_lbl")
        self._queue_progress_lbl.setAlignment(Qt.AlignRight)
        lay.addWidget(self._queue_progress_lbl)

        return card

    # ─── Progress Card ────────────────────────────────────────────────────────

    def _build_progress_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        lbl = QLabel("PROGRESS")
        lbl.setObjectName("section_label")
        lay.addWidget(lbl)

        self._status_lbl = QLabel("Menunggu antrian...")
        self._status_lbl.setObjectName("status_idle")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        lay.addWidget(self._progress_bar)

        self._log_box = QTextEdit()
        self._log_box.setObjectName("log_box")
        self._log_box.setReadOnly(True)
        self._log_box.setMinimumHeight(100)
        self._log_box.setMaximumHeight(220)
        self._log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._log_box.setPlaceholderText("Log akan muncul di sini...")
        lay.addWidget(self._log_box)

        self._open_btn = QPushButton("📂  Buka Folder Output")
        self._open_btn.setObjectName("browse_btn")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.hide()
        self._open_btn.clicked.connect(self._open_output_folder)
        lay.addWidget(self._open_btn, alignment=Qt.AlignRight)

        return card

    # ─── Apply Style ─────────────────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet(MAIN_STYLE + QUEUE_EXTRA_STYLE + PREVIEW_STYLE)

    # ─── Event: Video selected ────────────────────────────────────────────────

    def _on_video_selected(self, path: str):
        QTimer.singleShot(100, lambda: self._probe_and_update(path))

    def _probe_and_update(self, path: str):
        info = FFmpegRenderer.probe_video(path)
        if info:
            self._video_duration_ms = info["duration_ms"]
            self._video_src_w = info["width"]
            self._video_src_h = info["height"]
            self._log(
                f"Video terdeteksi: {info['width']}x{info['height']}, "
                f"durasi: {info['duration_ms']/1000:.1f}s"
            )
            self._update_end_time()
            self._preview.load_video(path, info["width"], info["height"])
            self._refresh_preview_overlays()
        else:
            self._video_duration_ms = 0

    def _update_end_time(self):
        start_text = self._start_edit.text().strip()
        duration   = getattr(self, "_video_duration_ms", 0)
        if start_text and duration > 0:
            try:
                start_ms = timestamp_to_ms(start_text)
                end_ms   = start_ms + duration
                self._end_edit.setText(ms_to_timestamp(end_ms))
            except Exception:
                self._end_edit.clear()
        else:
            self._end_edit.clear()

    # ─── Event: Add to Queue ──────────────────────────────────────────────────

    def _on_add_to_queue(self):
        video_path    = self._video_edit.text().strip()
        intro_path    = self._intro_edit.text().strip()
        subtitle_path = self._subtitle_edit.text().strip()
        sub_start     = self._start_edit.text().strip()

        # Validasi
        if not video_path or not Path(video_path).exists():
            self._set_status("⚠ Pilih file video terlebih dahulu.", "error")
            return
        if intro_path and not Path(intro_path).exists():
            self._set_status("⚠ File intro tidak ditemukan.", "error")
            return
        if not subtitle_path or not Path(subtitle_path).exists():
            self._set_status("⚠ Pilih file subtitle (.srt) terlebih dahulu.", "error")
            return
        if not sub_start:
            self._set_status("⚠ Isi Subtitle Start Time.", "error")
            return
        try:
            timestamp_to_ms(sub_start)
        except Exception:
            self._set_status("⚠ Format Subtitle Start Time tidak valid. Gunakan HH:MM:SS", "error")
            return

        # Buat job
        job = RenderJob(
            video_path       = video_path,
            intro_path       = intro_path or None,
            subtitle_path    = subtitle_path,
            subtitle_start   = sub_start,
            subtitle_preset  = self._style_combo.currentText(),
            auto_hook        = self._hook_check.isChecked(),
            crop_settings    = {k: v.value() for k, v in self._crop_spins.items()},
        )

        self._queue.append(job)
        self._add_queue_widget(job)
        self._update_queue_ui()
        self._set_status(f"✓ '{job.name}' ditambahkan ke antrian ({len(self._queue)} video).", "done")
        self._log(f"[QUEUE] Ditambahkan: {job.name}")

    def _add_queue_widget(self, job: RenderJob):
        idx = len(self._queue) - 1
        widget = QueueItemWidget(job, idx, on_remove=self._on_remove_item)
        self._queue_widgets.append(widget)
        # Insert sebelum stretch
        count = self._queue_list_layout.count()
        self._queue_list_layout.insertWidget(count - 1, widget)

    def _on_remove_item(self, widget: QueueItemWidget):
        if self._queue_running:
            return
        if widget in self._queue_widgets:
            idx = self._queue_widgets.index(widget)
            self._queue_widgets.pop(idx)
            self._queue.pop(idx)
            self._queue_list_layout.removeWidget(widget)
            widget.deleteLater()
            # Re-index
            for i, w in enumerate(self._queue_widgets):
                w.update_index(i)
            self._update_queue_ui()
            self._log(f"[QUEUE] Dihapus dari antrian.")

    def _on_clear_queue(self):
        if self._queue_running:
            return
        for w in self._queue_widgets:
            self._queue_list_layout.removeWidget(w)
            w.deleteLater()
        self._queue_widgets.clear()
        self._queue.clear()
        self._update_queue_ui()
        self._set_status("Antrian dikosongkan.", "idle")
        self._log("[QUEUE] Semua item dihapus.")

    def _update_queue_ui(self):
        n = len(self._queue)
        self._queue_lbl.setText(f"ANTRIAN  ({n} video)")
        self._start_queue_btn.setEnabled(n > 0 and not self._queue_running)
        self._clear_queue_btn.setEnabled(n > 0 and not self._queue_running)

        if n == 0:
            self._queue_placeholder.show()
            self._queue_scroll.hide()
        else:
            self._queue_placeholder.hide()
            self._queue_scroll.show()

    def _reset_form(self):
        self._video_edit.clear()
        self._intro_edit.clear()
        self._subtitle_edit.clear()
        self._start_edit.clear()
        self._end_edit.clear()
        self._video_duration_ms = 0
        self._preview.load_video("")
        self._preview.set_subtitles([])

    # ─── Event: Start Queue ───────────────────────────────────────────────────

    def _on_start_queue(self):
        if self._queue_running:
            # Cancel current job
            if self._worker and self._worker.isRunning():
                self._worker.cancel()
            self._queue_running = False
            self._start_queue_btn.setText("▶   MULAI ANTRIAN")
            self._add_btn.setEnabled(True)
            self._log("[QUEUE] Antrian dihentikan oleh user.")
            self._set_status("Antrian dihentikan.", "error")
            return

        # Mulai dari job pertama yang masih "pending"
        pending = [i for i, j in enumerate(self._queue) if j.status == "pending"]
        if not pending:
            self._set_status("Semua video sudah diproses.", "done")
            return

        self._queue_running = True
        self._start_queue_btn.setText("⏹   STOP ANTRIAN")
        self._add_btn.setEnabled(False)
        self._clear_queue_btn.setEnabled(False)
        self._open_btn.hide()

        self._log(f"[QUEUE] Memulai antrian: {len(pending)} video pending.")
        self._run_next_job()

    def _run_next_job(self):
        """Jalankan job pending berikutnya dalam antrian."""
        if not self._queue_running:
            return

        # Cari job pending berikutnya
        next_idx = next(
            (i for i, j in enumerate(self._queue) if j.status == "pending"),
            None
        )

        if next_idx is None:
            # Semua selesai
            self._queue_running = False
            self._start_queue_btn.setText("▶   MULAI ANTRIAN")
            self._add_btn.setEnabled(True)
            self._update_queue_ui()

            done  = sum(1 for j in self._queue if j.status == "done")
            failed = sum(1 for j in self._queue if j.status == "failed")
            self._log(f"\n[QUEUE] ===== ANTRIAN SELESAI =====")
            self._log(f"[QUEUE] Berhasil: {done}  |  Gagal: {failed}")
            self._set_status(
                f"✓ Antrian selesai! {done} berhasil, {failed} gagal.",
                "done" if failed == 0 else "error"
            )
            self._open_btn.show()
            self._update_queue_progress()
            return

        self._current_job_idx = next_idx
        job = self._queue[next_idx]
        widget = self._queue_widgets[next_idx]
        widget.set_status("running")

        total   = len(self._queue)
        done_so_far = sum(1 for j in self._queue if j.status in ("done", "failed"))
        self._log(f"\n[QUEUE] ─── Job {done_so_far + 1}/{total}: {job.name} ───")
        self._progress_bar.setValue(0)
        self._set_status(f"⚙ [{done_so_far + 1}/{total}] {job.name}", "running")
        self._update_queue_progress()

        # Jalankan worker
        self._worker = RenderWorker(
            video_path      = job.video_path,
            intro_path      = job.intro_path,
            subtitle_path   = job.subtitle_path,
            subtitle_start  = job.subtitle_start,
            subtitle_preset = job.subtitle_preset,
            auto_hook       = job.auto_hook,
            crop_settings   = job.crop_settings,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished.connect(self._on_job_finished)
        self._worker.start()

    def _on_progress(self, pct: float, msg: str):
        self._progress_bar.setValue(int(pct * 100))
        total = len(self._queue)
        done  = sum(1 for j in self._queue if j.status in ("done", "failed"))
        self._set_status(f"⚙ [{done + 1}/{total}] {msg}", "running")

    def _on_job_finished(self, success: bool, result: str):
        idx  = self._current_job_idx
        job  = self._queue[idx]
        widget = self._queue_widgets[idx]

        if success:
            job.status      = "done"
            job.output_path = result
            widget.set_status("done")
            self._progress_bar.setValue(100)
            self._log(f"[QUEUE] ✓ Selesai: {result}")
            self._output_path = result
        else:
            job.status    = "failed"
            job.error_msg = result
            widget.set_status("failed")
            self._log(f"[QUEUE] ✗ Gagal: {result}")

        self._update_queue_progress()

        # Jeda 500ms lalu lanjut ke job berikutnya
        QTimer.singleShot(500, self._run_next_job)

    def _update_queue_progress(self):
        done   = sum(1 for j in self._queue if j.status == "done")
        failed = sum(1 for j in self._queue if j.status == "failed")
        total  = len(self._queue)
        if total > 0:
            self._queue_progress_lbl.setText(
                f"✓ {done}  ✗ {failed}  ⏳ {total - done - failed}  /  {total} total"
            )

    def _open_output_folder(self):
        path = getattr(self, "_output_path", None)
        if path and Path(path).exists():
            os.startfile(str(Path(path).parent))

    # ─── Status & Log Helpers ────────────────────────────────────────────────

    def _set_status(self, msg: str, state: str = "idle"):
        self._status_lbl.setText(msg)
        name_map = {
            "idle":    "status_idle",
            "running": "status_running",
            "done":    "status_done",
            "error":   "status_error",
        }
        self._status_lbl.setObjectName(name_map.get(state, "status_idle"))
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_box.append(f"[{ts}] {msg}")
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ─── Environment Check ────────────────────────────────────────────────────

    def _check_environment(self):
        self._video_duration_ms = 0
        self._video_src_w = 1920
        self._video_src_h = 1080
        self._output_path = None

        ok = FFmpegRenderer.check_ffmpeg()
        if ok:
            nvenc = FFmpegRenderer.check_codec("h264_nvenc")
            codec = "h264_nvenc" if nvenc else "libx264"
            self._env_badge.setText(f"● FFmpeg OK [{codec}]")
            self._env_badge.setObjectName("status_done")
            self._log(f"FFmpeg terdeteksi. Codec: {codec}")
        else:
            self._env_badge.setText("● FFmpeg tidak ditemukan!")
            self._env_badge.setObjectName("status_error")
            self._log("[ERROR] FFmpeg tidak ditemukan di PATH!")
            self._add_btn.setEnabled(False)
            self._start_queue_btn.setEnabled(False)

        self._env_badge.style().unpolish(self._env_badge)
        self._env_badge.style().polish(self._env_badge)

    def _wire_preview(self):
        self._subtitle_edit.textChanged.connect(self._schedule_preview_refresh)
        self._start_edit.textChanged.connect(self._schedule_preview_refresh)

    def _schedule_preview_refresh(self, *_):
        self._preview_debounce.start()

    def _refresh_preview_overlays(self):
        crop = {k: v.value() for k, v in self._crop_spins.items()}
        self._preview.set_crop(crop)
        self._preview.set_subtitles(self._preview_entries())

    def _preview_entries(self):
        sub_path = self._subtitle_edit.text().strip()
        start = self._start_edit.text().strip()
        duration = getattr(self, "_video_duration_ms", 0)
        if not sub_path or not Path(sub_path).exists() or not start or duration <= 0:
            return []
        try:
            extractor = SubtitleExtractor(sub_path)
            start_ms = timestamp_to_ms(start)
            end_time = ms_to_timestamp(start_ms + duration)
            return extractor.shifted_entries(start, end_time)
        except Exception as e:
            self._log(f"[PREVIEW] Subtitle skip: {e}")
            return []

    def closeEvent(self, event):
        self._preview.shutdown()
        super().closeEvent(event)


# ─── Extra Style untuk Queue ──────────────────────────────────────────────────

QUEUE_EXTRA_STYLE = """
/* Tombol tambah ke antrian */
QPushButton#add_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #7c3aed, stop:1 #6d28d9);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QPushButton#add_btn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #8b5cf6, stop:1 #7c3aed);
}
QPushButton#add_btn:disabled {
    background: #2d2d3d;
    color: #555;
}

/* Item antrian */
QFrame#queue_item {
    background: #1a1a2e;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
}
QFrame#queue_item:hover {
    border-color: #4a4a6e;
}

QLabel#queue_idx {
    color: #555;
    font-size: 11px;
    font-weight: 600;
}

QLabel#queue_icon_pending  { color: #f59e0b; font-size: 14px; }
QLabel#queue_icon_running  { color: #3b82f6; font-size: 14px; }
QLabel#queue_icon_done     { color: #10b981; font-size: 14px; }
QLabel#queue_icon_failed   { color: #ef4444; font-size: 14px; }

QLabel#queue_name {
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 600;
}
QLabel#queue_sub {
    color: #64748b;
    font-size: 10px;
}

QPushButton#queue_remove_btn {
    background: transparent;
    color: #4a4a6e;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    padding: 0;
}
QPushButton#queue_remove_btn:hover {
    background: #3f1818;
    color: #ef4444;
}

QLabel#queue_placeholder {
    color: #3a3a5c;
    font-size: 13px;
    font-style: italic;
}
QLabel#queue_progress_lbl {
    color: #64748b;
    font-size: 11px;
}
"""
