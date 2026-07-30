"""
Time Utilities
Konversi format waktu yang dipakai di seluruh aplikasi
"""


def timestamp_to_ms(timestamp: str) -> int:
    """
    Konversi timestamp string ke milliseconds.

    Format yang didukung:
        HH:MM:SS.mmm  → "00:35:20.000"
        HH:MM:SS,mmm  → "00:35:20,000"  (format SRT)
        HH:MM:SS      → "00:35:20"
        MM:SS         → "35:20"
    """
    timestamp = timestamp.strip().replace(",", ".")

    parts = timestamp.split(":")
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split(".")
        s = int(s_parts[0])
        ms = int(s_parts[1].ljust(3, "0")[:3]) if len(s_parts) > 1 else 0
    elif len(parts) == 2:
        h = 0
        m = int(parts[0])
        s_parts = parts[1].split(".")
        s = int(s_parts[0])
        ms = int(s_parts[1].ljust(3, "0")[:3]) if len(s_parts) > 1 else 0
    else:
        raise ValueError(f"Format timestamp tidak valid: '{timestamp}'")

    return (h * 3600 + m * 60 + s) * 1000 + ms


def ms_to_timestamp(ms: int) -> str:
    """
    Konversi milliseconds ke format HH:MM:SS.mmm
    """
    ms = max(0, ms)
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def ms_to_ass_timestamp(ms: int) -> str:
    """
    Konversi milliseconds ke format ASS timestamp: H:MM:SS.cc
    (centiseconds, bukan milliseconds)
    """
    ms = max(0, ms)
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1000
    cs = (ms % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def format_duration(ms: int) -> str:
    """
    Format durasi ms ke string yang mudah dibaca.
    Contoh: 65000 → "1m 5s"
    """
    total_sec = ms // 1000
    m = total_sec // 60
    s = total_sec % 60
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"
