# Project Status: videoEditor
**Last Sync:** 2026-08-13
**Version:** MVP v1.0

## Deskripsi
Aplikasi desktop (PySide6) untuk otomatisasi editing video pendek (Shorts/TikTok/Reels) dengan fitur "Smart Hook" dan subtitle dinamis.

## Fitur Utama
1.  **Queue System**: Mendukung antrean render banyak video sekaligus.
2.  **Smart Hook Logic**: 
    - Potong bagian menarik berdasarkan timestamp AI.
    - Pindah ke awal video (Hook -> Body).
    - Mapping ulang timing subtitle otomatis agar tetap sinkron.
3.  **FFmpeg Engine**:
    - **Multi-input seeking**: Efisiensi RAM tinggi, hanya membaca segmen yang diperlukan.
    - **Hardware Acceleration**: Prioritas `h264_nvenc` (NVIDIA), fallback ke `libx264`.
    - **Audio Fading**: Auto fade-in/out pada sambungan segmen.
4.  **Subtitle System**: Render subtitle `.ass` hardcoded dengan berbagai preset style.
5.  **Crop & Formatting**: Auto-crop ke rasio 16:9 (Portrait) dengan margin yang bisa diatur.

## Struktur Folder
- `ui/`: Interface PySide6, style, dan worker thread.
- `renderer/`: Logika inti editing (TimelineBuilder, CommandBuilder, FFmpegRenderer).
- `subtitle/`: Management `.srt` ke `.ass` dan preset style.
- `config/`: Konfigurasi global dan preset.
- `output/`: Lokasi hasil render dan log.

## Status Pengembangan
- [x] UI Dasar & Antrean.
- [x] FFmpeg Command Generator (Multi-input).
- [x] Subtitle Remapping.
- [x] GPU Acceleration Support.
- [ ] Integrasi AI Assistant Direct (saat ini masih manual input timestamp).
- [ ] Auto-Caption Generation (Speech-to-Text).

---
*File ini dibuat otomatis untuk tracker status project.*
