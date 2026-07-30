"""
UI Stylesheet - Dark Premium Theme
"""

MAIN_STYLE = """
/* ─── Global ─────────────────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0C0C0F;
    color: #E8E8F0;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

/* ─── Card / Panel ───────────────────────────────────────────────────────── */
QFrame#card {
    background-color: #14141A;
    border: 1px solid #2A2A38;
    border-radius: 12px;
    padding: 4px;
}

/* ─── Section Label ──────────────────────────────────────────────────────── */
QLabel#section_label {
    color: #7C6AFF;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
}

QLabel#field_label {
    color: #8888AA;
    font-size: 12px;
    font-weight: 500;
}

QLabel#value_label {
    color: #E8E8F0;
    font-size: 12px;
}

QLabel#app_title {
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLabel#app_subtitle {
    color: #5A5A7A;
    font-size: 10px;
}

QLabel#status_idle {
    color: #5A5A7A;
    font-size: 12px;
    font-style: italic;
}

QLabel#status_running {
    color: #7C6AFF;
    font-size: 12px;
}

QLabel#status_done {
    color: #00D68F;
    font-size: 12px;
    font-weight: 600;
}

QLabel#status_error {
    color: #FF5555;
    font-size: 12px;
    font-weight: 600;
}

/* ─── Line Edit ──────────────────────────────────────────────────────────── */
QLineEdit {
    background-color: #1E1E28;
    border: 1px solid #2A2A3A;
    border-radius: 8px;
    padding: 6px 10px;
    color: #E8E8F0;
    font-size: 12px;
    selection-background-color: #7C6AFF;
    min-height: 28px;
}

QLineEdit:focus {
    border: 1px solid #7C6AFF;
    background-color: #1E1E30;
}

QLineEdit:read-only {
    background-color: #181820;
    color: #5A5A7A;
    border: 1px solid #222230;
}

QLineEdit#time_input {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    letter-spacing: 1px;
    color: #A8A8FF;
}

/* ─── ComboBox ───────────────────────────────────────────────────────────── */
QComboBox {
    background-color: #1E1E28;
    border: 1px solid #2A2A3A;
    border-radius: 8px;
    padding: 6px 10px;
    color: #E8E8F0;
    font-size: 12px;
    min-height: 28px;
}

QComboBox:focus {
    border: 1px solid #7C6AFF;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #7C6AFF;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1E1E28;
    border: 1px solid #7C6AFF;
    border-radius: 8px;
    color: #E8E8F0;
    selection-background-color: #7C6AFF;
    selection-color: #FFFFFF;
    padding: 4px;
}

/* ─── Spin Box ───────────────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox {
    background-color: #1E1E28;
    border: 1px solid #2A2A3A;
    border-radius: 8px;
    padding: 6px 8px;
    color: #E8E8F0;
    font-size: 12px;
    min-height: 28px;
}

QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #7C6AFF;
}

QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #2A2A3A;
    border: none;
    width: 16px;
    border-radius: 4px;
}

QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #7C6AFF;
}

/* ─── Push Button ────────────────────────────────────────────────────────── */
QPushButton#browse_btn {
    background-color: #1E1E28;
    border: 1px solid #3A3A50;
    border-radius: 8px;
    padding: 6px 12px;
    color: #A0A0CC;
    font-size: 12px;
    font-weight: 500;
    min-width: 70px;
    min-height: 28px;
}

QPushButton#browse_btn:hover {
    background-color: #2A2A3A;
    border-color: #7C6AFF;
    color: #FFFFFF;
}

QPushButton#browse_btn:pressed {
    background-color: #7C6AFF;
    color: #FFFFFF;
}

QPushButton#start_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5B4FFF, stop:1 #8B5CF6);
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 1px;
    min-height: 42px;
}

QPushButton#start_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6B5FFF, stop:1 #9B6CF6);
}

QPushButton#start_btn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4B3FEF, stop:1 #7B4CE6);
    padding-top: 11px;
    padding-bottom: 9px;
}

QPushButton#start_btn:disabled {
    background: #2A2A3A;
    color: #444460;
}

/* ─── CheckBox ───────────────────────────────────────────────────────────── */
QCheckBox {
    color: #C0C0E0;
    font-size: 12px;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3A3A50;
    background-color: #1E1E28;
}

QCheckBox::indicator:checked {
    background-color: #7C6AFF;
    border-color: #7C6AFF;
    image: none;
}

QCheckBox::indicator:checked:hover {
    background-color: #8B79FF;
}

QCheckBox::indicator:hover {
    border-color: #7C6AFF;
}

/* ─── Progress Bar ───────────────────────────────────────────────────────── */
QProgressBar {
    background-color: #1E1E28;
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5B4FFF, stop:0.5 #8B5CF6, stop:1 #00D4FF);
    border-radius: 6px;
}

/* ─── Text Edit (Log) ────────────────────────────────────────────────────── */
QTextEdit#log_box {
    background-color: #0A0A0F;
    border: 1px solid #1A1A28;
    border-radius: 8px;
    color: #7070A0;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 8px;
}

/* ─── Separator ──────────────────────────────────────────────────────────── */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #2A2A3A;
    border: none;
    background-color: #2A2A3A;
    max-height: 1px;
}

/* ─── ScrollBar ──────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #0C0C0F;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #2A2A3A;
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #7C6AFF;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #0C0C0F;
    height: 6px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #2A2A3A;
    border-radius: 3px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #7C6AFF;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ─── ToolTip ────────────────────────────────────────────────────────────── */
QToolTip {
    background-color: #1E1E30;
    border: 1px solid #7C6AFF;
    border-radius: 6px;
    color: #E8E8F0;
    padding: 6px 10px;
    font-size: 12px;
}
"""
