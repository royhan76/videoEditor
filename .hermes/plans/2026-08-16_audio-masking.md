# Anti-Copyright Audio Masking Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Menambahkan fitur manipulasi audio (masking) untuk menghindari Content ID YouTube tanpa merusak kualitas suara secara signifikan. Terintegrasi ke UI PySide6 dan FFmpeg renderer yang sudah ada.

**Architecture:** 
1.  **Data Model**: Tambahkan `masking_enabled` dan `masking_intensity` ke `Timeline` dan `AudioInfo`.
2.  **Renderer**: Modifikasi `FFmpegCommandBuilder` untuk menyisipkan filter `aecho`, `vibrato`, dan `asetrate` ke dalam `audio_chain`.
3.  **UI**: Tambah section "Audio Masking" di `MainWindow` (Settings Card) dengan toggle dan slider intensitas.
4.  **Preview**: Update `PreviewWidget` agar mendukung audio filtering saat playback.

**Tech Stack:** Python 3.12, PySide6, FFmpeg (aecho, vibrato, rubberband filters).

---

## Phase 1: Core Logic & Renderer
**Objective:** Menambahkan kemampuan FFmpeg command builder untuk memproses audio masking.

### Task 1: Update Timeline Data Model
**Files:** 
- Modify: `renderer/timeline_builder.py:64-69`

**Step 1: Update AudioInfo dataclass**
```python
@dataclass
class AudioInfo:
    fade_in_ms: int
    fade_out_ms: int
    crossfade_ms: int
    masking_enabled: bool = False
    masking_intensity: float = 0.5  # 0.0 to 1.0
```

### Task 2: Implement Masking Filters in Command Builder
**Files:**
- Modify: `renderer/command_builder.py` (tambah method `_build_audio_masking_filter`)

**Step 1: Tambah logic masking filter**
Di dalam `FFmpegCommandBuilder`, buat filter string berdasarkan intensitas:
- `aecho`: delay sekitar 20-40ms (intensitas rendah).
- `vibrato`: frequency 0.5-2.0Hz.
- `asetrate`: geser sample rate sedikit (0.99x atau 1.01x).

**Step 2: Inject ke audio_chain**
Modifikasi loop di `_build_with_hook` (line 120+) untuk menyertakan masking jika enabled.

---

## Phase 2: UI Integration
**Objective:** Menampilkan kontrol masking di aplikasi.

### Task 3: Add Masking Controls to MainWindow
**Files:**
- Modify: `ui/main_window.py`

**Step 1: Modify `_build_settings_card`**
Tambah `QCheckBox` (Anti-Copyright) dan `QSlider` (Intensity) di bawah pengaturan subtitle.

**Step 2: Connect signals**
Pastikan nilai masking masuk ke `RenderJob` saat tombol "Tambah" (Add to Queue) diklik.

---

## Phase 3: Preview & Validation
**Objective:** Memastikan user bisa mendengar hasil masking sebelum render.

### Task 4: Update Preview Widget (Optional but Recommended)
**Files:**
- Modify: `ui/preview_widget.py`

**Note:** Preview saat ini menggunakan `QMediaPlayer` untuk audio. Karena `QMediaPlayer` membaca file langsung, masking filter FFmpeg tidak akan terdengar di preview kecuali kita pipe audio-nya juga (kompleks). 
**Simplified Approach:** Tambahkan tombol "Test Audio" yang me-render 5 detik audio dengan masking untuk divalidasi manual.

### Task 5: Final Testing
**Step 1: Test Command Generation**
Run: `pytest tests/test_renderer.py` (jika ada) atau print command string.
Expected: FFmpeg command mengandung `aecho` atau `vibrato` di filter_complex.

**Step 2: Manual Render**
Render video pendek, cek apakah suara berubah sesuai intensitas.

---

## Risks & Tradeoffs
- **Audio Quality**: Intensitas terlalu tinggi bikin suara "robot" atau fals.
- **Content ID**: Tidak ada jaminan 100% lolos, tapi meningkatkan peluang signifikan.
- **CPU Load**: Filter audio FFmpeg sangat ringan, tidak membebani i5 Gen 8.
