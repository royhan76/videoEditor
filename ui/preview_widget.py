"""
Live preview: QMediaPlayer (decode native) + overlay crop + subtitle.
Bukan ffplay — laptop 930MX gak kuat re-encode realtime.
"""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QUrl, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from subtitle.extractor import SubtitleEntry


def contain_rect(
    box_w: int, box_h: int, src_w: int, src_h: int
) -> Tuple[int, int, int, int]:
    """Video letterbox di dalam box. Return (x, y, w, h)."""
    if src_w <= 0 or src_h <= 0 or box_w <= 0 or box_h <= 0:
        return (0, 0, max(box_w, 0), max(box_h, 0))
    box_ar = box_w / box_h
    src_ar = src_w / src_h
    if src_ar > box_ar:
        w = box_w
        h = int(round(box_w / src_ar))
        return (0, (box_h - h) // 2, w, h)
    h = box_h
    w = int(round(box_h * src_ar))
    return ((box_w - w) // 2, 0, w, h)


def crop_keep_rect(
    vx: int, vy: int, vw: int, vh: int,
    left_pct: float, right_pct: float, top_pct: float, bottom_pct: float,
) -> Tuple[int, int, int, int]:
    """Area yang tetap setelah crop % dari tepi video-display-rect."""
    x = vx + int(vw * left_pct / 100.0)
    y = vy + int(vh * top_pct / 100.0)
    w = vw - int(vw * left_pct / 100.0) - int(vw * right_pct / 100.0)
    h = vh - int(vh * top_pct / 100.0) - int(vh * bottom_pct / 100.0)
    return (x, y, max(w, 0), max(h, 0))


def _fmt_ms(ms: int) -> str:
    ms = max(0, int(ms))
    s, _ = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class _Overlay(QWidget):
    """Gelapin area ter-crop + teks subtitle di area keep."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.src_w = 1920
        self.src_h = 1080
        self.crop = {"left_pct": 8.0, "right_pct": 8.0, "top_pct": 4.0, "bottom_pct": 10.0}
        self.subtitle_text = ""
        self.placeholder = "Pilih video untuk preview"

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.src_w <= 0:
            p.fillRect(0, 0, w, h, QColor(10, 10, 14, 220))
            p.setPen(QColor("#5A5A7A"))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(self.rect(), Qt.AlignCenter, self.placeholder)
            return

        vx, vy, vw, vh = contain_rect(w, h, self.src_w, self.src_h)
        kx, ky, kw, kh = crop_keep_rect(
            vx, vy, vw, vh,
            self.crop.get("left_pct", 0),
            self.crop.get("right_pct", 0),
            self.crop.get("top_pct", 0),
            self.crop.get("bottom_pct", 0),
        )

        dim = QColor(8, 8, 12, 140)
        p.fillRect(0, 0, w, vy, dim)
        p.fillRect(0, vy + vh, w, h - (vy + vh), dim)
        p.fillRect(0, vy, vx, vh, dim)
        p.fillRect(vx + vw, vy, w - (vx + vw), vh, dim)
        p.fillRect(vx, vy, kx - vx, vh, dim)
        p.fillRect(kx + kw, vy, (vx + vw) - (kx + kw), vh, dim)
        p.fillRect(kx, vy, kw, ky - vy, dim)
        p.fillRect(kx, ky + kh, kw, (vy + vh) - (ky + kh), dim)

        # Highlight area crop aktual
        p.setPen(QPen(QColor("#7C6AFF"), 2))
        p.drawRect(kx, ky, kw, kh)

        if self.subtitle_text and kw > 8 and kh > 8:
            p.setPen(QColor("#FFFFFF"))
            font = QFont("Segoe UI", 11)
            font.setBold(True)
            p.setFont(font)
            pad = 8
            text_rect = self.rect().adjusted(0, 0, 0, 0)
            text_rect.setRect(kx + pad, ky + kh - 72, max(kw - pad * 2, 0), 64)
            p.setPen(QColor(0, 0, 0, 180))
            p.drawText(text_rect.adjusted(1, 1, 1, 1), Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, self.subtitle_text)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap, self.subtitle_text)


class PreviewWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._entries: List[SubtitleEntry] = []
        self._seeking = False
        self._has_source = False

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.85)
        self._player.setAudioOutput(self._audio)

        self._video = QVideoWidget(self)
        self._video.setMinimumSize(480, 270)   # 16:9 min
        self._video.setMaximumHeight(420)      # batasi tinggi (16:9 max-ish)
        self._video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._video.setAspectRatioMode(Qt.KeepAspectRatio)
        self._player.setVideoOutput(self._video)

        self._overlay = _Overlay(self._video)
        self._overlay.setGeometry(self._video.rect())

        self._time_lbl = QLabel("00:00 / 00:00")
        self._time_lbl.setObjectName("preview_time")
        self._time_lbl.setAlignment(Qt.AlignCenter)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.setEnabled(False)
        self._slider.sliderPressed.connect(self._on_slider_press)
        self._slider.sliderReleased.connect(self._on_slider_release)
        self._slider.sliderMoved.connect(self._on_slider_moved)

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

        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)

        self.setMinimumWidth(360)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._overlay.setGeometry(self._video.rect())

    def showEvent(self, event):
        super().showEvent(event)
        self._overlay.setGeometry(self._video.rect())
        self._overlay.raise_()

    # ─── Public ─────────────────────────────────────────────────────────────

    def load_video(self, path: str, src_w: int = 0, src_h: int = 0):
        self.stop()
        if not path:
            self._has_source = False
            self._overlay.src_w = 0
            self._overlay.placeholder = "Pilih video untuk preview"
            self._overlay.update()
            self._set_controls(False)
            return
        self._player.setSource(QUrl.fromLocalFile(path))
        self._has_source = True
        if src_w > 0 and src_h > 0:
            self.set_source_size(src_w, src_h)
        else:
            self._overlay.src_w = 16
            self._overlay.src_h = 9
        self._overlay.placeholder = ""
        self._overlay.update()
        self._set_controls(True)

    def set_source_size(self, w: int, h: int):
        self._overlay.src_w = w
        self._overlay.src_h = h
        self._overlay.update()

    def set_crop(self, crop: dict):
        self._overlay.crop = dict(crop)
        self._overlay.update()

    def set_subtitles(self, entries: List[SubtitleEntry]):
        self._entries = entries or []
        self._sync_subtitle(self._player.position())

    def start(self):
        if not self._has_source:
            return
        self._player.setPosition(0)
        self._player.play()

    def play(self):
        if self._has_source:
            self._player.play()

    def pause(self):
        self._player.pause()

    def stop(self):
        self._player.stop()
        self._player.setPosition(0)
        self._slider.setValue(0)
        self._sync_subtitle(0)
        self._update_time(0, self._player.duration())

    def shutdown(self):
        self._player.stop()
        self._player.setSource(QUrl())

    # ─── Internals ──────────────────────────────────────────────────────────

    def _set_controls(self, on: bool):
        for b in (self._btn_start, self._btn_play, self._btn_pause, self._btn_stop):
            b.setEnabled(on)
        self._slider.setEnabled(on)

    def _sync_subtitle(self, pos_ms: int):
        text = ""
        for e in self._entries:
            if e.start_ms <= pos_ms <= e.end_ms:
                text = e.text
                break
        if text != self._overlay.subtitle_text:
            self._overlay.subtitle_text = text
            self._overlay.update()

    def _update_time(self, pos: int, dur: int):
        self._time_lbl.setText(f"{_fmt_ms(pos)} / {_fmt_ms(dur)}")

    @Slot(int)
    def _on_position(self, pos: int):
        if not self._seeking:
            self._slider.blockSignals(True)
            self._slider.setValue(pos)
            self._slider.blockSignals(False)
        self._update_time(pos, self._player.duration())
        self._sync_subtitle(pos)

    @Slot(int)
    def _on_duration(self, dur: int):
        self._slider.setRange(0, max(dur, 0))
        self._update_time(self._player.position(), dur)

    @Slot()
    def _on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._btn_play.setEnabled(self._has_source and not playing)
        self._btn_pause.setEnabled(self._has_source and playing)

    @Slot()
    def _on_error(self, *_):
        err = self._player.errorString() or "Preview gagal memuat video"
        self._overlay.src_w = 0
        self._overlay.placeholder = err
        self._overlay.update()

    def _on_slider_press(self):
        self._seeking = True

    def _on_slider_release(self):
        self._seeking = False
        self._player.setPosition(self._slider.value())

    def _on_slider_moved(self, value: int):
        self._update_time(value, self._player.duration())
        self._sync_subtitle(value)


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
