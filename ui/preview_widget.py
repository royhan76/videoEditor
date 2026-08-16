"""
Live preview: FFmpeg image2pipe + crop filter real-time di QLabel.
Overlay crop diganti crop nyata via ffmpeg -vf crop.
Subtitle tetap via QPainter overlay di QLabel.
Render final pakai renderer/command_builder.py (HD720+).
"""

import subprocess
import threading
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl, Slot, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QImage, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSlider, QVBoxLayout, QWidget,
)

from subtitle.extractor import SubtitleEntry


def _fmt_ms(ms: int) -> str:
    ms = max(0, int(ms))
    s, _ = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class PreviewWidget(QFrame):
    PREVIEW_W = 480
    PREVIEW_H = 270

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._entries: List[SubtitleEntry] = []
        self._src_w = 1920
        self._src_h = 1080
        self._video_path: Optional[str] = None
        self._crop = {"left_pct": 8.0, "right_pct": 8.0, "top_pct": 4.0, "bottom_pct": 10.0}
        self._proc: Optional[subprocess.Popen] = None
        self._pipe_buf = bytearray()
        self._frame_size = self.PREVIEW_W * self.PREVIEW_H * 3
        self._playing = False
        self._position_ms = 0
        self._duration_ms = 0
        self._user_seek = False

        # Audio playback via QtMultimedia — sinkron dengan FFmpeg video pipe
        self._audio = QAudioOutput()
        self._audio.setVolume(1.0)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio)

        # QLabel video
        self._video = QLabel()
        self._video.setMinimumSize(self.PREVIEW_W, self.PREVIEW_H)
        self._video.setMaximumHeight(420)
        self._video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._video.setAlignment(Qt.AlignCenter)
        self._video.setStyleSheet("background:#000;")
        self._video.setPixmap(QPixmap(self.PREVIEW_W, self.PREVIEW_H))

        # Controls
        self._time_lbl = QLabel("00:00 / 00:00")
        self._time_lbl.setObjectName("preview_time")
        self._time_lbl.setAlignment(Qt.AlignCenter)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setEnabled(False)
        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)

        self._btn_start = QPushButton("⏮  Start")
        self._btn_play = QPushButton("▶  Play")
        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_stop = QPushButton("⏹  Stop")
        for b in (self._btn_start, self._btn_play, self._btn_pause, self._btn_stop):
            b.setObjectName("preview_ctrl_btn")
            b.setCursor(Qt.PointingHandCursor)
            b.setEnabled(False)
        self._btn_play.setObjectName("preview_play_btn")

        self._btn_start.clicked.connect(self.start)
        self._btn_play.clicked.connect(self.play)
        self._btn_pause.clicked.connect(self.pause)
        self._btn_stop.clicked.connect(self.stop)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        controls.addWidget(self._btn_start)
        controls.addWidget(self._btn_play)
        controls.addWidget(self._btn_pause)
        controls.addWidget(self._btn_stop)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        title = QLabel("PREVIEW")
        title.setObjectName("section_label")
        lay.addWidget(title)
        lay.addWidget(self._video, 1)
        lay.addWidget(self._slider)
        lay.addWidget(self._time_lbl)
        lay.addLayout(controls)

        # Timer untuk baca frame dari pipe
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._read_frame)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._do_restart)

    # ─── Public ─────────────────────────────────────────────────────────────

    def load_video(self, path: str, src_w: int = 0, src_h: int = 0):
        self.stop()
        if not path:
            self._video_path = None
            self._has_source = False
            self._set_controls(False)
            self._show_placeholder("Pilih video untuk preview")
            return
        self._video_path = path
        self._has_source = True
        self._src_w = src_w if src_w > 0 else 1920
        self._src_h = src_h if src_h > 0 else 1080
        self._show_placeholder("")
        # Set audio source (same video file — QtMultimedia handles audio demux)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._restart_pipe()
        self._set_controls(True)

    def set_source_size(self, w: int, h: int):
        self._src_w = w
        self._src_h = h
        self._restart_pipe()

    def set_crop(self, crop: dict):
        self._crop = dict(crop)
        self._restart_pipe()

    def set_subtitles(self, entries: List[SubtitleEntry]):
        self._entries = entries or []
        self._sync_subtitle(self._position_ms)

    def start(self):
        if not self._video_path:
            return
        self.stop()
        self._position_ms = 0
        self._slider.blockSignals(True)
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._playing = True
        self._btn_play.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._position_ms = 0
        self._restart_pipe(seek_ms=0)
        self._player.setPlaybackRate(1.0)
        self._player.play()

    def play(self):
        if not self._video_path or self._playing:
            return
        self._playing = True
        self._btn_play.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._restart_pipe(seek_ms=self._position_ms)
        self._player.play()

    def pause(self):
        self._playing = False
        self._btn_play.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._player.pause()
        if self._proc:
            self._proc.terminate()
            self._proc = None
        self._timer.stop()
        self._render_subtitle_overlay()

    def stop(self):
        self._playing = False
        self._btn_play.setEnabled(True)
        self._btn_pause.setEnabled(False)
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1)
            except Exception:
                self._proc.kill()
            self._proc = None
        self._timer.stop()
        self._pipe_buf.clear()
        self._position_ms = 0
        self._player.stop()
        self._slider.blockSignals(True)
        self._slider.setValue(0)
        self._slider.blockSignals(False)
        self._update_time(0, self._duration_ms)
        self._sync_subtitle(0)
        self._render_subtitle_overlay()

    def shutdown(self):
        self.stop()

    # ─── Internals ──────────────────────────────────────────────────────────

    def _set_controls(self, on: bool):
        for b in (self._btn_start, self._btn_play, self._btn_pause, self._btn_stop):
            b.setEnabled(on)
        self._slider.setEnabled(on)

    def _show_placeholder(self, text: str):
        img = QImage(self.PREVIEW_W, self.PREVIEW_H, QImage.Format_RGB32)
        img.fill(QColor(10, 10, 14, 220))
        p = QPainter()
        if p.begin(img):
            p.setPen(QColor("#5A5A7A"))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(img.rect(), Qt.AlignCenter, text or "")
            p.end()
        self._video.setPixmap(QPixmap.fromImage(img))

    def _crop_rect(self):
        """Pixel crop rect at source resolution."""
        left = self._src_w * self._crop["left_pct"] / 100.0
        right = self._src_w * self._crop["right_pct"] / 100.0
        top = self._src_h * self._crop["top_pct"] / 100.0
        bottom = self._src_h * self._crop["bottom_pct"] / 100.0
        cw = max(self._src_w - left - right, 1)
        ch = max(self._src_h - top - bottom, 1)
        return int(cw), int(ch), int(left), int(top)

    def _restart_pipe(self, seek_ms: Optional[int] = None):
        if seek_ms is not None:
            self._position_ms = seek_ms
        self._do_restart(seek_ms=self._position_ms)

    def _do_restart(self, seek_ms: Optional[int] = None):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1)
            except Exception:
                self._proc.kill()
            self._proc = None
        self._timer.stop()
        self._pipe_buf.clear()

        if not self._video_path or not self._has_source:
            return

        cw, ch, cx, cy = self._crop_rect()
        if cw <= 0 or ch <= 0:
            self._show_placeholder("Crop tidak valid")
            return

        cmd = [
            "ffmpeg", "-y",
            "-i", self._video_path,
        ]
        if seek_ms is not None and seek_ms > 0:
            cmd += ["-ss", f"{seek_ms / 1000.0:.3f}"]
        cmd += [
            "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale={self.PREVIEW_W}:{self.PREVIEW_H}",
            "-r", "30",
            "-f", "image2pipe",
            "-vcodec", "rawvideo",
            "-pix_fmt", "rgb24",
            "-",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self._show_placeholder(f"FFmpeg error: {e}")
            return
        self._timer.start(33)

    def _read_frame(self):
        if not self._proc or not self._proc.stdout:
            self._timer.stop()
            return
        chunk = self._proc.stdout.read(self._frame_size)
        if not chunk or len(chunk) < self._frame_size:
            if self._proc and self._proc.poll() is not None:
                # EOF / finished
                if self._playing:
                    self.stop()
                else:
                    self._timer.stop()
            return
        img = QImage(chunk, self.PREVIEW_W, self.PREVIEW_H, QImage.Format_RGB888)
        img = img.copy()  # detach
        self._pipe_buf = bytearray()
        self._video.setPixmap(QPixmap.fromImage(img))
        self._render_subtitle_overlay()
        if self._playing and not self._user_seek:
            self._position_ms += int(1000 / 30)
            self._slider.blockSignals(True)
            self._slider.setValue(self._position_ms)
            self._slider.blockSignals(False)
            self._update_time(self._position_ms, self._duration_ms)
            self._sync_subtitle(self._position_ms)

    def _render_subtitle_overlay(self):
        """Draw subtitle text onto a copy of current pixmap."""
        px = self._video.pixmap()
        if px is None or px.isNull():
            return
        img = px.toImage().convertToFormat(QImage.Format_RGB32)
        p = QPainter()
        try:
            if not p.begin(img):
                return
            text = self._current_subtitle()
            if text:
                pad = 8
                rect = img.rect().adjusted(0, 0, 0, -pad)
                p.setPen(QPen(QColor(0, 0, 0, 180)))
                font = QFont("Segoe UI", 11)
                font.setBold(True)
                p.setFont(font)
                p.drawText(rect.adjusted(1, 1, 1, 1), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, text)
                p.setPen(QPen(QColor("#FFFFFF")))
                p.drawText(rect, Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, text)
            p.end()
        except Exception:
            return
        self._video.setPixmap(QPixmap.fromImage(img))

    def _current_subtitle(self) -> str:
        for e in self._entries:
            if e.start_ms <= self._position_ms <= e.end_ms:
                return e.text
        return ""

    def _sync_subtitle(self, pos_ms: int):
        pass  # handled in _render_subtitle_overlay via _current_subtitle

    def _update_time(self, pos: int, dur: int):
        self._time_lbl.setText(f"{_fmt_ms(pos)} / {_fmt_ms(dur)}")

    def _on_slider_press(self):
        self._user_seek = True

    def _on_slider_release(self):
        self._user_seek = False
        self._position_ms = self._slider.value()
        # Seek audio player to match slider position
        self._player.setPosition(self._position_ms)
        if self._playing:
            self._do_restart(seek_ms=self._position_ms)
        else:
            self._do_restart(seek_ms=self._position_ms)  # single frame seek

    def set_duration(self, ms: int):
        self._duration_ms = ms
        self._slider.setRange(0, max(ms, 0))
        self._update_time(self._position_ms, ms)


PREVIEW_STYLE = """
QLabel#preview_time {
    color: #A8A8FF;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    letter-spacing: 1px;
}
QPushButton#preview_ctrl_btn, QPushButton#preview_play_btn {
    background-color: #1E1E28;
    border: 1px solid #3A3A50;
    border-radius: 8px;
    padding: 6px 10px;
    color: #C0C0E0;
    font-size: 12px;
    font-weight: 600;
    min-height: 32px;
}
QPushButton#preview_ctrl_btn:hover, QPushButton#preview_play_btn:hover {
    border-color: #7C6AFF;
    color: #FFFFFF;
}
QPushButton#preview_play_btn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5B4FFF, stop:1 #8B5CF6);
    border: none;
    color: #FFFFFF;
}
QPushButton#preview_play_btn:disabled, QPushButton#preview_ctrl_btn:disabled {
    background: #1A1A22;
    color: #444460;
    border-color: #2A2A3A;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2A2A3A;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -4px 0;
    background: #7C6AFF;
    border-radius: 6px;
}
QSlider::sub-page:horizontal {
    background: #7C6AFF;
    border-radius: 2px;
}
"""
