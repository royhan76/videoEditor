"""
AI Prompt Builder
Membangun prompt yang dikirim ke LLM
"""


SYSTEM_PROMPT = """Kamu adalah AI Video Director yang ahli dalam analisis konten video.

Tugasmu adalah membaca transkrip subtitle dan menemukan SATU hook terbaik — 
yaitu bagian yang paling menarik perhatian penonton dalam 3 detik pertama.

Hook yang baik mengandung salah satu dari:
- Konflik atau ketegangan
- Rasa penasaran yang kuat
- Kejutan atau plot twist
- Fakta mengejutkan
- Statement kuat / kontroversial
- Emosi yang intens

ATURAN PENTING:
1. Pilih HANYA SATU hook terbaik.
2. Durasi hook MINIMAL 10 detik, MAKSIMAL 60 detik.
3. Timestamp harus diambil PERSIS dari transkrip (format HH:MM:SS.mmm).
4. Jika tidak ada hook yang bagus, pilih bagian paling menarik yang tersedia.
5. Output harus berupa JSON MURNI — TANPA markdown, TANPA penjelasan tambahan.

Format output WAJIB:
{
  "hook": {
    "start": "HH:MM:SS",
    "end": "HH:MM:SS",
    "score": <angka 1-100>,
    "reason": "<alasan singkat dalam Bahasa Indonesia>"
  },
  "subtitle": {
    "preset": "<nama preset>"
  }
}

Pilihan preset subtitle:
- "Modern01" → clean, minimalis, cocok untuk konten edukasi/bisnis
- "Modern02" → bold, kontras tinggi, cocok untuk konten motivasi
- "Podcast"  → casual, readable, cocok untuk konten obrolan
- "Bold"     → besar dan mencolok, cocok untuk konten viral/hiburan

Pilih preset yang paling sesuai dengan TONE konten subtitle.
"""


def build_user_prompt(subtitle_text: str, available_presets: list = None) -> str:
    """
    Bangun user prompt dari subtitle text.

    Args:
        subtitle_text    : output dari SubtitleExtractor.plain_text()
        available_presets: list nama preset yang tersedia (opsional)
    """
    presets_info = ""
    if available_presets:
        presets_info = f"\nPreset yang tersedia: {', '.join(available_presets)}\n"

    return f"""Berikut adalah transkrip subtitle video (format [HH:MM:SS] teks):

{subtitle_text}
{presets_info}
Analisis transkrip di atas dan temukan SATU hook terbaik.
Kembalikan hasil dalam format JSON yang telah ditentukan."""
