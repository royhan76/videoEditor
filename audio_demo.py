import numpy as np
import librosa
from manim import *

# Path audio
AUDIO_PATH = r"C:\Users\royha\Desktop\Takdir Allah Lebih Baik II Pengajian Gus Iqdam - Gus Iqdam Official (128k).mp3"

class AudioPulse(Scene):
    def construct(self):
        # Load audio and sample rate
        # Kita ambil 5 detik pertama
        y, sr = librosa.load(AUDIO_PATH, duration=5)
        
        # Hitung RMSE (Root Mean Square Energy) per frame
        # Ini indikator "volume" atau "loudness"
        hop_length = 512
        rmse = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        
        # Normalisasi data volume agar enak dilihat (skala 1-3)
        rmse = (rmse - np.min(rmse)) / (np.max(rmse) - np.min(rmse) + 1e-6)
        # Skala circle: min 1.0, max 3.5
        scales = 1.0 + rmse * 2.5
        
        # Buat lingkaran
        circle = Circle(radius=1.0, color=BLUE, stroke_width=8)
        circle.set_fill(BLUE, opacity=0.3)
        
        # Tambah glow effect tipis
        glow = circle.copy().set_stroke(BLUE, opacity=0.1, width=20)
        
        self.add(circle, glow)
        
        # Durasi per frame Manim default 1/fps
        fps = self.camera.frame_rate
        total_frames = len(scales)
        
        # Map timestamp audio ke frame manim
        # sr/hop_length = jumlah data per detik
        data_per_sec = sr / hop_length
        
        def update_circle(obj, dt):
            # Hitung index data berdasarkan waktu sekarang
            idx = int(self.time * data_per_sec)
            if idx < len(scales):
                s = scales[idx]
                obj.scale(s / obj.get_width() * 2) # sync ke radius dasar
        
        circle.add_updater(update_circle)
        glow.add_updater(lambda m, dt: m.become(circle.copy().set_stroke(BLUE, opacity=0.1, width=20)))
        
        self.wait(5)
        
        circle.remove_updater(update_circle)

if __name__ == "__main__":
    # Command untuk render: manim -pql audio_demo.py AudioPulse
    pass
