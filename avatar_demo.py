from pathlib import Path
from manim import *
import librosa
import numpy as np

# Paths (adjust if needed)
AVATAR_DIR = Path(r"E:/PROJECT/desktop/videoEditor/assets/avatars/host")
AUDIO_PATH = Path(r"C:/Users/royha/Desktop/Takdir Allah Lebih Baik II Pengajian Gus Iqdam - Gus Iqdam Official (128k).mp3")

class AvatarScene(Scene):
    def construct(self):
        # Load audio (first 10 seconds for demo)
        y, sr = librosa.load(str(AUDIO_PATH), duration=10)
        hop = 512
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        # Normalise 0-1
        rms_norm = (rms - rms.min()) / (rms.max() - rms.min() + 1e-6)
        # thresholds for mouth states
        def get_state(val):
            if val < 0.3:
                return 0  # closed
            elif val < 0.6:
                return 1  # small
            else:
                return 2  # wide
        # Prepare avatar images
        imgs = [ImageMobject(str(AVATAR_DIR / f"state{i}.png")).scale(2) for i in range(3)]
        # Use first image as base
        avatar = imgs[0]
        self.add(avatar)
        # Updater to switch image based on audio RMS
        def updater(mob, dt):
            # current time in scene (seconds)
            t = self.time
            # compute which rms index corresponds to this time
            idx = int(t * sr / hop)
            if idx < len(rms_norm):
                state = get_state(rms_norm[idx])
                # replace mob with correct image
                mob.become(imgs[state])
        avatar.add_updater(updater)
        self.wait(10)
        avatar.remove_updater(updater)

if __name__ == "__main__":
    pass
