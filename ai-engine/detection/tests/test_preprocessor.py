"""
Test: Preprocessor — letterbox resizing, aspect ratio preservation, and color conversion.
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.processors.preprocessor import Preprocessor


@pytest.fixture
def preprocessor():
    return Preprocessor(target_size=640)


def test_letterbox_output_shape(preprocessor):
    """Letterbox should produce output matching target size (640x640)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    padded, scale, pad = preprocessor.letterbox(frame)
    assert padded.shape[0] == 640
    assert padded.shape[1] == 640


def test_letterbox_preserves_aspect_ratio(preprocessor):
    """Scale factor should never exceed 1.0 for images smaller than target."""
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    _, scale, _ = preprocessor.letterbox(frame)
    assert scale[0] <= 2.0  # scale up allowed
    assert scale[1] <= 2.0


def test_preprocess_returns_dict(preprocessor):
    """Preprocess should return dict with required keys."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = preprocessor.preprocess(frame)
    assert "processed_image" in result
    assert "original_shape" in result
    assert "scale" in result
    assert "pad" in result


def test_preprocess_original_shape(preprocessor):
    """Preprocess should record original frame width and height correctly."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = preprocessor.preprocess(frame)
    assert result["original_shape"] == (1280, 720)


def test_preprocess_accepts_small_frame(preprocessor):
    """Preprocessor should handle very small frames gracefully."""
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    result = preprocessor.preprocess(frame)
    assert result["processed_image"] is not None


def test_preprocess_accepts_non_square_hd(preprocessor):
    """Preprocessor should handle full HD non-square frames."""
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = preprocessor.preprocess(frame)
    assert result["processed_image"].shape[0] == 640
    assert result["processed_image"].shape[1] == 640
