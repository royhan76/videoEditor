"""Self-check geometry preview. Run: python tests/test_preview_geometry.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.preview_widget import contain_rect, crop_keep_rect


def test_contain_wide_in_square():
    # 16:9 di kotak 400x400 → tinggi 225, y = 87
    assert contain_rect(400, 400, 1920, 1080) == (0, 87, 400, 225)


def test_contain_tall_in_wide():
    x, y, w, h = contain_rect(400, 200, 1080, 1920)
    assert y == 0
    assert h == 200
    assert w < 400
    assert x > 0


def test_crop_keep():
    # video 200x100 di (0,0), crop 10% tiap sisi
    assert crop_keep_rect(0, 0, 200, 100, 10, 10, 10, 10) == (20, 10, 160, 80)


if __name__ == "__main__":
    test_contain_wide_in_square()
    test_contain_tall_in_wide()
    test_crop_keep()
    print("ok")
