"""Offscreen UI smoke test: build MainWindow, toggle Nuclear, collect params, add job."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\PROJECT\desktop\videoEditor")

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from ui.main_window import MainWindow
m = MainWindow()

# Panel ada & default benar (resep terbukti)
assert m._nc_crop.value() == 42.4 and m._nc_rotate.value() == 2.0
assert m._nc_hue.value() == 40.0 and m._nc_speed.value() == 1.25
assert m._nc_noise.value() == 18 and m._nc_fps.value() == 30
assert not m._nuclear_check.isChecked()      # default off

# Toggle nuclear → knob enable, masking nyala otomatis, visual level mati
m._nuclear_check.setChecked(True)
assert m._nc_crop.isEnabled() and m._nuclear_reset_btn.isEnabled()
assert m._masking_check.isChecked(), "audio masking harus auto-on"
assert not m._visual_check.isChecked(), "visual level harus auto-off"

# Custom: ubah nilai → collected params ikut
m._nc_crop.setValue(50.0)
m._nc_pitch.setValue(6.0)
p = m._collect_nuclear_params()
assert p["mode"] == "nuclear" and p["crop_pct"] == 50.0 and "pitch_ratio" not in p, p

# Reset button balikin resep terbukti
m._reset_nuclear_defaults()
assert m._nc_crop.value() == 42.4

# Toggle off → params kosong, masking mati
m._nuclear_check.setChecked(False)
assert m._collect_nuclear_params() == {}
assert not m._masking_check.isChecked()

print("UI SMOKE PASS")
