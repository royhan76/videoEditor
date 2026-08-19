# Avatar Podcast Implementation Plan

**Goal**: Produce Islamic podcast episodes where two AI‑cloned voices converse, each represented by a 2‑D avatar that animates its mouth (and optional eye blink) in sync with the audio. Full video must be original content, suitable for YouTube monetisation.

**Current context / assumptions**
- Audio files already exist (raw recordings of you and co‑host). We'll clone them to desired voices using RVC (or a free Colab service).
- Manim & librosa are installed (see previous dependency install).
- Existing videoEditor pipeline can overlay subtitles (.ass) and background music.
- We have a GPU‑poor laptop (i5‑8th gen, NVIDIA 930MX 2 GB). Rendering must stay CPU‑friendly.

**Proposed approach**
1. **Create avatar assets**
   - Generate a front‑facing head PNG (transparent background) for each speaker via FLUX/StableDiffusion.
   - Render four mouth states: `closed`, `small_open`, `wide_open`, `silence` (optional eye‑blink frame).
   - Export each state as `speakerA_00.png … speakerA_03.png` and same for speaker B.
   - Store under `assets/avatars/<speaker>/`.
2. **Map audio to mouth state**
   - Load the final (cloned) wav with `librosa.load(..., sr=22050)`.
   - Compute short‑term RMS envelope (`hop_length=512`).
   - Normalise to 0‑1 and define thresholds, e.g.:
     * 0‑0.2 → `closed`
     * 0.2‑0.5 → `small_open`
     * >0.5 → `wide_open`.
   - Produce a list of timestamps + chosen state index.
3. **Render avatar animation** (two options, pick one).
   - **Manim up‑dater** (preferred – already in repo):
     * Load the avatar PNG with `ImageMobject`.
     * Add an updater that reads the RMS envelope at `self.time` and swaps the image via `self.become(ImageMobject(state_path))`.
     * Place host on left, co‑host on right.
   - **ffmpeg overlay filter** (fallback):
     * Export the timestamp‑state list to a CSV.
     * Use `ffmpeg -i background.mp4 -filter_complex "[0:v]scale=…"` with a series of `overlay` filters using `enable='between(t,start,end)'` to swap each PNG.
4. **Compose final video**
   - Background: static image or slow‑pan video (Ken Burns) prepared in existing pipeline.
   - Add avatar layer (Manim output) as a video clip.
   - Overlay subtitles (`.ass`) generated from the script.
   - Add background music (Lyria) and optional sound‑effects.
   - Export MP4 (`-c:v libx264 -crf 23 -preset veryslow`).
5. **Automation script**
   - `scripts/create_episode.py` – arguments: `--title`, `--audio_a`, `--audio_b`, `--bg_image`, `--music`.
   - Steps: clone voices → generate mouth‑state CSV → run Manim scene → ffmpeg compose → embed subtitles.
   - Output placed in `output/<slug>.mp4`.
6. **Testing / validation**
   - Render a 30‑second sample using the two short audio clips.
   - Verify mouth sync visually; adjust RMS thresholds if lips lag/lead.
   - Run `ffprobe` to ensure audio‑video sync and no extra delay.
   - Check final file size (< 200 MB) for YouTube upload.

**Files likely to change / add**
- `assets/avatars/host/` and `assets/avatars/cohost/` (PNG assets).
- `scripts/create_episode.py` (new automation entry point).
- `audio_demo.py` (may be repurposed or removed).
- `renderer/ffmpeg_renderer.py` (optional: add a helper to feed avatar overlay).
- `subtitle/preset_loader.py` (no change, reuse existing subtitle pipeline).

**Risks, trade‑offs, open questions**
- **Render time** – Manim with updaters is CPU‑intensive; keep resolution 720p for drafts.
- **Lip‑sync granularity** – RMS‑based approach gives coarse mouth movement. For higher fidelity, consider phoneme‑level alignment (e.g., `aeneas`), but that adds complexity.
- **Avatar style** – Simple PNG heads may look static. Adding eye‑blink frames (extra PNG) improves realism at minimal cost.
- **Audio cloning quality** – Free RVC Colab may introduce artifacts; test with a short clip before full episode.
- **YouTube policy** – Ensure no copyrighted music or footage is used; all assets must be original/royalty‑free.

**Next steps**
1. Generate avatar PNG set (quick test with FLUX image‑to‑image).
2. Write the RMS‑to‑state utility (`scripts/audio_to_mouth.py`).
3. Prototype Manim scene swapping avatars based on audio.
4. Run a 30‑second end‑to‑end test and iterate thresholds.

---
*Plan saved for reference.*
