"""
AI Director
- Menerima subtitle plain text
- Mengirim ke Gemini API
- Memvalidasi dan mengembalikan EditPlan
"""

import json
import re
import time
import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from ai.prompt import SYSTEM_PROMPT, build_user_prompt
from ai.edit_plan import EditPlan, HookPlan, SubtitlePlan
from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp

logger = logging.getLogger(__name__)

# Konstanta batas durasi hook
HOOK_MIN_SEC = 10
HOOK_MAX_SEC = 60
HOOK_MIN_MS  = HOOK_MIN_SEC * 1000
HOOK_MAX_MS  = HOOK_MAX_SEC * 1000


class AIDirector:
    """
    Bertanggung jawab untuk:
    - Menerima subtitle text
    - Mengirim ke Gemini API
    - Memvalidasi hasil
    - Mengembalikan EditPlan
    """

    def __init__(self, config: dict):
        self.config    = config
        self.api_key   = config.get("api", {}).get("api_key", "")
        self.model_name = config.get("api", {}).get("model", "gemini-1.5-flash")
        self.min_hook_sec = config.get("hook", {}).get("min_duration_sec", HOOK_MIN_SEC)
        self.max_hook_sec = config.get("hook", {}).get("max_duration_sec", HOOK_MAX_SEC)

        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            raise ValueError("API key Gemini belum dikonfigurasi di config.json")

        self.client = genai.Client(api_key=self.api_key)

        # Model fallback chain — dicoba urut dari atas ke bawah
        primary = config.get("api", {}).get("model", "gemini-2.0-flash")
        self.model_chain = self._build_model_chain(primary)
        self.model_name  = self.model_chain[0]   # model aktif saat ini

        # Retry config
        self.max_retries    = config.get("api", {}).get("max_retries",    3)
        self.retry_delay_s  = config.get("api", {}).get("retry_delay_s",  5)

    # ─── Public API ───────────────────────────────────────────────────────────────

    def analyze(
        self,
        subtitle_text: str,
        available_presets: Optional[list] = None,
        save_path: Optional[str] = None
    ) -> Optional[EditPlan]:
        """
        Analisis subtitle dan kembalikan EditPlan.

        Args:
            subtitle_text    : output SubtitleExtractor.plain_text()
            available_presets: list preset yang tersedia
            save_path        : path untuk simpan edit_plan.json (opsional)

        Returns:
            EditPlan jika berhasil, None jika gagal (gunakan video tanpa hook)
        """
        if not subtitle_text.strip():
            logger.error("Subtitle kosong — tidak bisa analisis")
            return None

        prompt = build_user_prompt(subtitle_text, available_presets)

        logger.info(f"Mengirim subtitle ke AI ({self.model_name})...")
        raw_response = self._call_api(prompt)

        if raw_response is None:
            logger.warning("AI tidak merespons — fallback tanpa hook")
            return None

        plan = self._parse_response(raw_response)
        if plan is None:
            logger.warning("Gagal parse respons AI — fallback tanpa hook")
            return None

        plan = self._validate_and_fix(plan)

        if save_path:
            plan.save(save_path)
            logger.info(f"edit_plan.json disimpan: {save_path}")

        return plan

    # ─── Internal ─────────────────────────────────────────────────────────────────

    def _call_api(self, prompt: str) -> Optional[str]:
        """
        Kirim prompt ke Gemini dengan retry + exponential backoff.
        Jika satu model gagal 429, coba model berikutnya dalam chain.
        """
        for model in self.model_chain:
            result = self._try_model(model, prompt)
            if result is not None:
                self.model_name = model   # catat model yang berhasil
                return result
            logger.warning(f"Model {model} gagal, mencoba model berikutnya...")

        logger.error("Semua model dalam fallback chain gagal.")
        return None

    def _try_model(self, model: str, prompt: str) -> Optional[str]:
        """Coba satu model dengan retry + exponential backoff."""
        delay = self.retry_delay_s
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.3,
                        max_output_tokens=2048,   # dinaikkan agar JSON tidak terpotong
                    )
                )
                logger.info(f"Berhasil dengan model: {model} (attempt {attempt})")
                return response.text

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    # Cek apakah daily quota habis (limit: 0) — tidak perlu retry
                    if "limit: 0" in err_str and attempt == 1:
                        logger.warning(
                            f"[{model}] Daily quota habis (limit: 0) — "
                            f"skip ke model berikutnya."
                        )
                        return None

                    if attempt < self.max_retries:
                        logger.warning(
                            f"[{model}] Rate limit (attempt {attempt}/{self.max_retries}) "
                            f"— retry dalam {delay}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, 60)   # exponential backoff, max 60s
                    else:
                        logger.warning(
                            f"[{model}] Gagal setelah {self.max_retries} attempts."
                        )
                        return None
                else:
                    # Error lain (bukan rate limit) — langsung keluar
                    logger.error(f"[{model}] Error: {e}")
                    return None

        return None

    @staticmethod
    def _build_model_chain(primary: str) -> list:
        """
        Buat model fallback chain.
        Primary model didahulukan, lalu fallback ke model lain yang tersedia.
        """
        # Daftar fallback urutan dari tercepat ke paling powerful
        all_options = [
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]
        # Taruh primary di depan, hapus duplikat
        chain = [primary]
        for m in all_options:
            if m != primary:
                chain.append(m)
        return chain

    def _parse_response(self, raw: str) -> Optional[EditPlan]:
        """
        Parse raw text dari AI menjadi EditPlan.
        Handles:
        - JSON murni
        - JSON dalam ```json ... ``` block
        - JSON terpotong (truncated) → gunakan regex field extraction
        """
        if not raw or not raw.strip():
            logger.error("Respons AI kosong")
            return None

        # ── Coba 1: Ekstrak dari markdown code block ─────────────────────────
        code_block = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        if code_block:
            candidate = code_block.group(1).strip()
        else:
            candidate = raw

        # ── Coba 2: Cari JSON object lengkap ─────────────────────────────────
        json_match = re.search(r"\{[\s\S]+\}", candidate)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return EditPlan.from_dict(data)
            except (json.JSONDecodeError, KeyError, ValueError):
                pass   # lanjut ke recovery

        # ── Coba 3: JSON truncated — regex field extraction ───────────────────
        logger.warning("JSON tidak lengkap — mencoba field extraction...")
        plan = self._extract_fields_fallback(raw)
        if plan:
            logger.info("Berhasil parse via field extraction fallback")
            return plan

        logger.error(f"Tidak ada JSON valid di respons AI:\n{raw[:300]}")
        return None

    def _extract_fields_fallback(self, raw: str) -> Optional[EditPlan]:
        """
        Fallback parser: ekstrak field satu per satu dengan regex.
        Berguna saat JSON terpotong di tengah.
        """
        try:
            start   = re.search(r'"start"\s*:\s*"([^"]+)"', raw)
            end     = re.search(r'"end"\s*:\s*"([^"]+)"', raw)
            score   = re.search(r'"score"\s*:\s*(\d+)', raw)
            reason  = re.search(r'"reason"\s*:\s*"([^"]+)"', raw)
            preset  = re.search(r'"preset"\s*:\s*"([^"]+)"', raw)

            if not start or not end:
                return None

            return EditPlan.from_dict({
                "hook": {
                    "start":  start.group(1),
                    "end":    end.group(1),
                    "score":  int(score.group(1)) if score else 75,
                    "reason": reason.group(1) if reason else "Extracted from truncated response",
                },
                "subtitle": {
                    "preset": preset.group(1) if preset else "Modern01"
                }
            })
        except Exception as e:
            logger.error(f"Field extraction fallback gagal: {e}")
            return None

    def _validate_and_fix(self, plan: EditPlan) -> EditPlan:
        """
        Validasi durasi hook dan perbaiki jika perlu.

        Rules:
        - Hook start harus >= 0
        - Hook end harus > start
        - Hook < 10 detik → log warning (tetap dipakai)
        - Hook > 60 detik → potong menjadi maksimal 60 detik
        - Score 0 diperbolehkan (tetap dipakai)
        """
        hook = plan.hook

        logger.info(
            f"[HOOK VALIDATE] start={hook.start}, end={hook.end}, "
            f"score={hook.score}, duration={hook.duration_ms/1000:.1f}s"
        )

        # Validasi: start harus positif
        if hook.start_ms < 0:
            logger.warning(f"Hook start negatif ({hook.start_ms}ms) — reset ke 00:00:00")
            plan.hook.start = "00:00:00"

        # Validasi: durasi tidak boleh negatif atau nol
        duration_ms = hook.duration_ms
        if duration_ms <= 0:
            logger.warning(
                f"Hook duration tidak valid ({duration_ms}ms): "
                f"start={hook.start}, end={hook.end} — fallback ke hook 30s dari awal"
            )
            plan.hook.end = ms_to_timestamp(hook.start_ms + 30_000)
            duration_ms = 30_000

        min_ms = self.min_hook_sec * 1000
        max_ms = self.max_hook_sec * 1000

        if duration_ms < min_ms:
            logger.warning(
                f"Hook terlalu pendek: {duration_ms/1000:.1f}s "
                f"(minimum {self.min_hook_sec}s). "
                f"Tetap dipakai karena tidak ada kandidat lain."
            )

        if duration_ms > max_ms:
            logger.info(
                f"Hook terlalu panjang: {duration_ms/1000:.1f}s — "
                f"dipotong menjadi {self.max_hook_sec}s"
            )
            new_end_ms = hook.start_ms + max_ms
            plan.hook.end = ms_to_timestamp(new_end_ms)

        # Jika score = 0 dari AI, naikkan ke minimum agar tidak dibuang
        if plan.hook.score == 0:
            logger.info("Hook score = 0, dinaikkan ke 50 agar tetap dipakai")
            plan.hook.score = 50

        return plan
