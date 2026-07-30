"""
Edit Plan - Model dan validator untuk edit_plan.json
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from subtitle.time_utils import timestamp_to_ms, ms_to_timestamp


@dataclass
class HookPlan:
    start: str      # "HH:MM:SS"
    end: str        # "HH:MM:SS"
    score: int      # 1-100
    reason: str

    @property
    def start_ms(self) -> int:
        return timestamp_to_ms(self.start)

    @property
    def end_ms(self) -> int:
        return timestamp_to_ms(self.end)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def duration_sec(self) -> float:
        return self.duration_ms / 1000


@dataclass
class SubtitlePlan:
    preset: str     # "Modern01", "Podcast", dll


@dataclass
class EditPlan:
    hook: HookPlan
    subtitle: SubtitlePlan

    def to_dict(self) -> dict:
        return {
            "hook": asdict(self.hook),
            "subtitle": asdict(self.subtitle)
        }

    def save(self, path: str):
        """Simpan edit_plan ke file JSON."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "EditPlan":
        """Buat EditPlan dari dict (hasil parse JSON AI)."""
        hook_data = data["hook"]
        sub_data  = data["subtitle"]

        return cls(
            hook=HookPlan(
                start=hook_data["start"],
                end=hook_data["end"],
                score=int(hook_data.get("score", 80)),
                reason=hook_data.get("reason", "")
            ),
            subtitle=SubtitlePlan(
                preset=sub_data.get("preset", "Modern01")
            )
        )

    @classmethod
    def load(cls, path: str) -> "EditPlan":
        """Load EditPlan dari file JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
