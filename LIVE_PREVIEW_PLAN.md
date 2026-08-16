# Live Video Preview Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Menambahkan panel preview video di UI agar user bisa melihat hasil editing (crop, subtitle, hook) secara langsung tanpa render full.

**Architecture:** 
1. **Preview Engine**: Menggunakan `ffplay` yang dipanggil via subprocess untuk memutar stream hasil filter FFmpeg secara real-time.
2. **UI Integration**: Menambahkan `PreviewWidget` di samping form input atau di atas antrean.
3. **Real-time Sync**: Saat parameter crop atau subtitle berubah, preview di-refresh.

**Tech Stack:** PySide6, FFmpeg (ffplay), Python Subprocess.

---

### Task 1: Create Preview Player Widget
**Objective:** Membuat widget container untuk menampung window `ffplay` atau menggunakan `QVideoWidget` sebagai placeholder.

**Files:**
- Create: `ui/preview_widget.py`
- Modify: `ui/main_window.py`

**Step 1: Implement PreviewWidget**
Gunakan `QWidget` dengan background hitam. Untuk tahap awal, kita akan menggunakan *embedding* window `ffplay` ke dalam widget ini (via `WinId` di Windows).

**Step 2: Tambah ke Layout Utama**
Ubah `MainWindow` agar menggunakan `QHBoxLayout` sebagai root, dengan Form di kiri dan Preview di kanan.

**Step 3: Commit**
`git commit -m "ui: add preview widget placeholder to main window"`

---

### Task 2: Implement FFplay Stream Logic
**Objective:** Membuat fungsi untuk men-generate command FFmpeg yang output-nya di-pipe langsung ke `ffplay`.

**Files:**
- Modify: `renderer/command_builder.py`
- Modify: `ui/preview_widget.py`

**Step 1: Command Preview**
Tambahkan method `build_preview_command` di `CommandBuilder`. Perbedaan dengan render:
- Resolusi lebih rendah (misal 360p) untuk performa.
- Preset `ultrafast`.
- Output format `matroska` atau `mpegts` dialirkan ke stdout.

**Step 2: Jalankan Subprocess**
Di `PreviewWidget`, jalankan `ffmpeg | ffplay`.

**Step 3: Commit**
`git commit -m "feat: implement real-time ffmpeg-to-ffplay streaming"`

---

### Task 3: Trigger Updates on Settings Change
**Objective:** Mengupdate preview secara otomatis atau via button "Update Preview" saat user mengubah nilai Crop atau Subtitle.

**Files:**
- Modify: `ui/main_window.py`

**Step 1: Connect Signals**
Hubungkan `valueChanged` dari `QDoubleSpinBox` (crop) dan `currentTextChanged` dari `QComboBox` (subtitle style) ke fungsi `refresh_preview`.

**Step 2: Debounce Update**
Gunakan `QTimer` agar preview tidak re-start setiap kali angka diketik (tunggu 500ms diam).

**Step 3: Commit**
`git commit -m "ui: sync settings changes with live preview"`

---

### Task 4: Verification
**Objective:** Verifikasi visual preview.

**Verification:**
1. Jalankan `python app.py`.
2. Pilih video.
3. Ubah nilai Crop Left/Right.
4. Pastikan jendela preview muncul dan menunjukkan area yang terpotong sesuai angka.
