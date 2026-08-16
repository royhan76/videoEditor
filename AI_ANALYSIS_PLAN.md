# AI Analysis Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Mengintegrasikan AI Director secara langsung ke dalam UI antrean sehingga user tidak perlu memasukkan timestamp hook secara manual.

**Architecture:** 
1. UI memanggil `AIDirector` saat video ditambahkan ke antrean atau sebelum render dimulai.
2. `AIDirector` menggunakan Gemini API untuk menganalisis transkrip (subtitle) dan menentukan hook.
3. Hasil analisis (EditPlan) dikirim ke `TimelineBuilder` untuk diproses.

**Tech Stack:** PySide6 (Threading), Google Gemini API (via current `ai/` module).

---

### Task 1: Update UI Input Handling
**Objective:** Menambahkan checkbox "Auto AI Analysis" di `MainWindow` dan memastikan logic UI bisa menangani status "Analyzing".

**Files:**
- Modify: `ui/main_window.py`

**Step 1: Tambah widget di Settings Card**
Tambah checkbox `self._ai_analysis_check`.

**Step 2: Update RenderJob model**
Tambah field `ai_analysis: bool` ke `RenderJob`.

**Step 3: Commit**
`git commit -m "ui: add AI analysis toggle to settings"`

---

### Task 2: Implement AI Analysis in Worker Thread
**Objective:** Menjalankan `AIDirector.analyze()` di dalam `RenderWorker` sebelum proses render dimulai jika opsi diaktifkan.

**Files:**
- Modify: `ui/worker.py`
- Modify: `renderer/ffmpeg_renderer.py` (untuk menerima EditPlan)

**Step 1: Update Worker loop**
Jika `job.ai_analysis` True, panggil `AIDirector` menggunakan subtitle file.

**Step 2: Inject hasil ke TimelineBuilder**
Ganti manual timestamp dengan `edit_plan.hook` hasil AI.

**Step 3: Commit**
`git commit -m "feat: integrate AI analysis into render worker"`

---

### Task 3: Error Handling & Fallback
**Objective:** Memastikan jika AI gagal (limit API/error), sistem otomatis fallback ke mode "No Hook" tanpa membatalkan seluruh render.

**Files:**
- Modify: `renderer/timeline_builder.py`

**Step 1: Update build logic**
Gunakan `build_no_hook` jika `edit_plan` None atau invalid.

**Step 2: Commit**
`git commit -m "fix: add fallback for failed AI analysis"`

---

### Task 4: Verification
**Objective:** Test render 1 video dengan Auto AI Analysis aktif.

**Verification:**
1. Jalankan `python app.py`.
2. Masukkan video + subtitle.
3. Centang "Auto AI Analysis".
4. Klik "Mulai Antrian".
5. Cek output: apakah ada hook di awal video yang sesuai dengan konteks subtitle.
