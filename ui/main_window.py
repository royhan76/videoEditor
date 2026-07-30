"""
Main Window - AI Video Director MVP v1
Premium dark UI with PySide6
"""

import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QDoubleSpinBox, QFrame, QTextEdit,
    QProgressBar, QFileDialog, QSizePolicy, QGridLayout,
    QScrollArea, QSpacerItem,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QColor

from ui.styles import MAIN_STYLE
from ui.worker import RenderWorker
from subtitle.preset_loader import PresetLoader
from config import load_config, get_preset_dir
from renderer.ffmpeg_renderer import FFmpegRenderer
from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._worker: RenderWorker = None
        self._config = load_config()

        self._setup_window()
        self._setup_ui()
        self._apply_style()
        self._check_environment()

    # ─── Window Setup ─────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("AI Video Director")
        # Ukuran minimum yang lebih kecil agar bisa diperkecil
        self.setMinimumSize(480, 580)
        self.resize(760, 860)

    # ─── UI Setup ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Tambah scroll area agar bisa scroll jika jendela terlalu kecil
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(scroll)

        inner = QVBoxLayout(content)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(14)

        inner.addWidget(self._build_header())
        inner.addWidget(self._build_separator())
        inner.addWidget(self._build_input_card())
        inner.addWidget(self._build_settings_card())
        inner.addWidget(self._build_start_button())
        inner.addWidget(self._build_progress_card())
        inner.addStretch()

    # ─── Header ──────────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel("AI VIDEO DIRECTOR")
        title.setObjectName("app_title")
        # Biarkan title shrink jika perlu
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        sub = QLabel("MVP v1.0  ·  Gemini + FFmpeg")
        sub.setObjectName("app_subtitle")
        sub.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        left.addWidget(title)
        left.addWidget(sub)

        lay.addLayout(left)
        lay.addStretch()

        # Status badge — biarkan elide jika terlalu kecil
        self._env_badge = QLabel("● Checking...")
        self._env_badge.setObjectName("status_running")
        self._env_badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._env_badge.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self._env_badge)

        return w

    # ─── Separator ───────────────────────────────────────────────────────────────

    def _build_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    # ─── Input Card ──────────────────────────────────────────────────────────────

    def _build_input_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        # Section title
        lbl = QLabel("INPUT")
        lbl.setObjectName("section_label")
        lay.addWidget(lbl)

        # Video file
        lay.addLayout(self._build_file_row(
            label="Video File",
            attr="_video_edit",
            placeholder="Pilih file video...",
            file_filter="Video Files (*.mp4 *.mov *.avi *.mkv *.webm)",
            on_selected=self._on_video_selected,
        ))

        # Intro video (opsional — disisipkan antara hook dan video inti)
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
        # Gunakan minimum width bukan fixed, agar bisa shrink
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

        # Start
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

        # End (auto)
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
        self._end_edit.setToolTip(
            "Dihitung otomatis: Subtitle Start + Durasi Video"
        )

        row.addWidget(lbl_s)
        row.addWidget(self._start_edit)
        row.addSpacing(8)
        row.addWidget(lbl_e)
        row.addWidget(self._end_edit)
        return row

    # ─── Settings Card ────────────────────────────────────────────────────────────

    def _build_settings_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        lbl = QLabel("SETTINGS")
        lbl.setObjectName("section_label")
        lay.addWidget(lbl)

        # Row 1: Subtitle style + Auto Hook
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

        # Separator
        lay.addWidget(self._build_separator())

        # Crop section
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
        labels = ["Left %", "Right %", "Top %", "Bottom %"]
        keys   = ["left_pct", "right_pct", "top_pct", "bottom_pct"]
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

            grid.addWidget(lbl,  0, col, Qt.AlignCenter)
            grid.addWidget(spin, 1, col, Qt.AlignCenter)
            grid.setColumnStretch(col, 1)

        return grid

    # ─── Start Button ─────────────────────────────────────────────────────────────

    def _build_start_button(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(0)

        self._start_btn = QPushButton("▶   START PROCESSING")
        self._start_btn.setObjectName("start_btn")
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start)
        # Biarkan button expand mengisi lebar tersedia
        self._start_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay.addWidget(self._start_btn)
        return w

    # ─── Progress Card ────────────────────────────────────────────────────────────

    def _build_progress_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        lbl = QLabel("PROGRESS")
        lbl.setObjectName("section_label")
        lay.addWidget(lbl)

        # Status label — bisa wrap teks
        self._status_lbl = QLabel("Menunggu input...")
        self._status_lbl.setObjectName("status_idle")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(8)
        lay.addWidget(self._progress_bar)

        # Log box — tinggi minimum, bisa expand
        self._log_box = QTextEdit()
        self._log_box.setObjectName("log_box")
        self._log_box.setReadOnly(True)
        self._log_box.setMinimumHeight(100)
        self._log_box.setMaximumHeight(200)
        self._log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._log_box.setPlaceholderText("Log akan muncul di sini...")
        lay.addWidget(self._log_box)

        # Open output button (hidden initially)
        self._open_btn = QPushButton("📂  Buka Folder Output")
        self._open_btn.setObjectName("browse_btn")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.hide()
        self._open_btn.clicked.connect(self._open_output_folder)
        lay.addWidget(self._open_btn, alignment=Qt.AlignRight)

        return card

    # ─── Apply Style ─────────────────────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet(MAIN_STYLE)

    # ─── Event Handlers ───────────────────────────────────────────────────────────

    def _on_video_selected(self, path: str):
        """Auto-probe video dan update end time jika start sudah diisi."""
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
        else:
            self._video_duration_ms = 0

    def _update_end_time(self):
        """Hitung subtitle end time otomatis."""
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

    def _on_start(self):
        if self._worker and self._worker.isRunning():
            # Cancel
            self._worker.cancel()
            self._start_btn.setText("▶   START PROCESSING")
            self._log("Dibatalkan oleh user.")
            return

        # Validasi input
        video_path    = self._video_edit.text().strip()
        intro_path    = self._intro_edit.text().strip()   # opsional
        subtitle_path = self._subtitle_edit.text().strip()
        sub_start     = self._start_edit.text().strip()

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

        # Kumpulkan crop settings
        crop_settings = {k: v.value() for k, v in self._crop_spins.items()}

        # Reset UI
        self._log_box.clear()
        self._progress_bar.setValue(0)
        self._open_btn.hide()
        self._set_status("Memulai proses...", "running")
        self._start_btn.setText("⏹   CANCEL")

        # Buat dan jalankan worker
        self._worker = RenderWorker(
            video_path       = video_path,
            intro_path       = intro_path or None,
            subtitle_path    = subtitle_path,
            subtitle_start   = sub_start,
            subtitle_preset  = self._style_combo.currentText(),
            auto_hook        = self._hook_check.isChecked(),
            crop_settings    = crop_settings,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: float, msg: str):
        self._progress_bar.setValue(int(pct * 100))
        self._set_status(msg, "running")

    def _on_finished(self, success: bool, result: str):
        self._start_btn.setText("▶   START PROCESSING")
        self._progress_bar.setValue(100 if success else self._progress_bar.value())

        if success:
            self._set_status(f"✓ Done! Output: {Path(result).name}", "done")
            self._output_path = result
            self._open_btn.show()
            self._log(f"\n=== SELESAI ===\nOutput: {result}")
        else:
            self._set_status(f"✗ Gagal: {result}", "error")
            self._log(f"\n=== ERROR ===\n{result}")

    def _open_output_folder(self):
        path = getattr(self, "_output_path", None)
        if path and Path(path).exists():
            folder = str(Path(path).parent)
            os.startfile(folder)

    # ─── Status & Log Helpers ─────────────────────────────────────────────────────

    def _set_status(self, msg: str, state: str = "idle"):
        self._status_lbl.setText(msg)
        name_map = {
            "idle":    "status_idle",
            "running": "status_running",
            "done":    "status_done",
            "error":   "status_error",
        }
        self._status_lbl.setObjectName(name_map.get(state, "status_idle"))
        # Force stylesheet refresh
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_box.append(f"[{ts}] {msg}")
        # Auto scroll
        sb = self._log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ─── Environment Check ────────────────────────────────────────────────────────

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
            self._start_btn.setEnabled(False)

        self._env_badge.style().unpolish(self._env_badge)
        self._env_badge.style().polish(self._env_badge)
