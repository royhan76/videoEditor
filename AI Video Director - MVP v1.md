# AI Video Director - MVP v1
Version : 1.0
Status  : Development Specification
Target  : Desktop Application
Language: Python 3.13+
UI      : PySide6 (Qt)
Renderer: FFmpeg
Subtitle: ASS Subtitle
AI       : LLM (Gemini/OpenAI/Compatible)

---

# 1. Tujuan Project

Membangun aplikasi desktop yang mampu melakukan editing video secara otomatis berdasarkan subtitle (.srt), tanpa timeline editing manual seperti CapCut.

Versi MVP hanya memiliki tiga fitur utama:

1. Auto Hook
2. Auto Crop (Long Video 16:9)
3. Modern Subtitle

Aplikasi ini bukan video editor.

Aplikasi ini adalah AI Video Director.

AI hanya bertugas mengambil keputusan editing.

Seluruh proses editing dilakukan oleh FFmpeg.

---

# 2. Arsitektur

                Video
                  │
                  │
               Subtitle
                  │
                  ▼
            Subtitle Extractor
                  │
                  ▼
              AI Director
                  │
                  ▼
             edit_plan.json
                  │
                  ▼
           Timeline Builder
                  │
                  ▼
              FFmpeg Render
                  │
                  ▼
             Final Output

---

# 3. Scope MVP

Yang dikerjakan

✔ Auto Hook

✔ Auto Crop

✔ Subtitle Modern

Yang BELUM dikerjakan

❌ Zoom In

❌ Zoom Out

❌ Auto Transition

❌ Face Tracking

❌ Object Tracking

❌ B-Roll

❌ Sound Effect

❌ Emoji

❌ AI Vision

---

# 4. Tech Stack

Python 3.13

PySide6

FFmpeg

pysubs2

ASS Subtitle

JSON

Google Gemini API (atau compatible)

---

# 5. Folder Structure

project/

    app.py

    ui/

    ai/

    renderer/

    subtitle/

    preset/

    assets/

    output/

    temp/

    config/

    edit_plan/

---

# 6. Workflow

STEP 1

User memilih Video

↓

STEP 2

User memilih Subtitle (.srt)

↓

STEP 3

User menentukan Subtitle Start Time

↓

STEP 4

Software menghitung Subtitle End Time berdasarkan durasi video

↓

STEP 5

Extract subtitle sesuai rentang waktu

↓

STEP 6

Kirim subtitle ke AI

↓

STEP 7

AI membuat edit_plan.json

↓

STEP 8

Timeline Builder

↓

STEP 9

FFmpeg Render

↓

Output

---

# 7. UI

Input Video

[ Browse ]

Input Subtitle

[ Browse ]

Subtitle Start Time

[ 00:12:30.000 ]

Subtitle End Time

[ AUTO ]

Aspect Ratio

Long Video (16:9)

Subtitle Style

Modern 01

Hook

☑ Auto Hook

Button

START

Progress

Searching Hook...

Rendering...

Done.

---

# 8. Subtitle Time

Video berasal dari hasil clip.

Subtitle berasal dari video asli.

Karena itu subtitle TIDAK dimulai dari

00:00:00

User wajib menentukan

Subtitle Start Time

Software otomatis menghitung

Subtitle End Time

Contoh

Video

00:00:45

Subtitle Start

00:35:20

Subtitle End

00:36:05

---

# 9. AI Director

AI hanya membaca subtitle.

AI TIDAK membaca video.

Input AI

Subtitle Text

Output

edit_plan.json

AI hanya menentukan

- Hook
- Subtitle Preset

Tidak menentukan

- Zoom
- Crop
- Transition

---

# 10. AI Prompt Goal

AI harus mencari

- bagian paling menarik

- konflik

- rasa penasaran

- kejutan

- fakta

- statement kuat

Output hanya SATU hook terbaik.

---

# 11. edit_plan.json

Contoh

{
    "hook":{

        "start":"00:12:30",

        "end":"00:13:05",

        "score":96,

        "reason":"Bagian ini memiliki konflik dan memancing rasa penasaran."

    },

    "subtitle":{

        "preset":"Modern01"

    }

}

---

# 12. Hook Processing

Timeline Builder melakukan

CUT

↓

MOVE

↓

PASTE TO BEGINNING

↓

DELETE ORIGINAL

↓

JOIN

Hook tidak boleh muncul dua kali.

---

# 13. Audio Processing

Saat hook dipindahkan ke depan

harus otomatis

Audio Fade In

Audio Fade Out

Crossfade

Supaya perpindahan terdengar natural.

Durasi fade dapat diatur melalui config.

---

# 14. Crop

Versi MVP

Tidak menggunakan AI.

Crop bersifat manual.

Mode

16:9

User menentukan

Left Margin

Right Margin

Top Margin

Bottom Margin

Disarankan menggunakan persen (%)

Contoh

Left

8%

Right

8%

Top

4%

Bottom

10%

---

# 15. Subtitle

Subtitle menggunakan ASS.

Tidak menggunakan subtitle filter bawaan FFmpeg.

Harus mendukung

Outline

Shadow

Modern Font

Margin

Safe Area

---

# 16. Subtitle Safe Area

Subtitle WAJIB berada di dalam area video.

Subtitle tidak boleh keluar area crop.

Subtitle selalu berada di bawah video.

Contoh

Video Area

↓

Subtitle Area

↓

Bottom Safe Margin

Margin subtitle mengikuti area crop.

Bukan mengikuti frame asli.

---

# 17. Subtitle Preset

Preset disimpan terpisah.

preset/

Modern01.ass

Modern02.ass

Podcast.ass

Bold.ass

AI hanya memilih nama preset.

Renderer yang memuat preset tersebut.

---

# 18. Timeline Builder

Timeline Builder membaca

edit_plan.json

Kemudian menerjemahkan menjadi

FFmpeg Command

AI tidak pernah membuat command FFmpeg.

---

# 19. Renderer

Renderer bertugas

Move Hook

Trim

Concat

Crop

Subtitle

Audio Fade

Encode

Semua proses dilakukan FFmpeg.

Render hanya SATU kali.

---

# 20. Configuration

config.json

Contoh

{

    "fade_in":300,

    "fade_out":300,

    "crossfade":400,

    "codec":"h264_nvenc",

    "subtitle_preset":"Modern01"

}

---

# 21. Output

output/

video_final.mp4

edit_plan.json

render_log.txt

---

# 22. Error Handling

Jika AI gagal

↓

Gunakan video tanpa hook

Jika subtitle kosong

↓

Batalkan render

Jika hook kurang dari 10 detik

↓

Cari kandidat berikutnya

Jika hook lebih dari 60 detik

↓

Potong menjadi maksimal 60 detik

---

# 23. Future Version

Auto Zoom

Auto Transition

AI Emotion Detection

Highlight Subtitle

Animated Subtitle

Face Tracking

Auto Crop

Object Tracking

Auto Sound Effect

Auto B-Roll

Auto CTA

---

# 24. Development Rules

- Semua logic AI dipisahkan dari renderer.
- Renderer tidak boleh mengetahui AI.
- AI tidak boleh mengetahui FFmpeg.
- Semua komunikasi menggunakan JSON.
- Semua preset berada pada folder terpisah.
- Semua proses render dilakukan satu kali (single encode).
- Seluruh kode harus modular agar mudah dikembangkan ke versi berikutnya.

---

# END