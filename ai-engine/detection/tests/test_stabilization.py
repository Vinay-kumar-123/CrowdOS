"""
Test: Sprint 3 Stabilization — frame validation, concurrency, reload, GPU unload,
result validation, and enterprise metadata fields.
"""
import threading
import time
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.engine.detection_engine import DetectionEngine, FrameValidationError
from detection.models.model_manager import ModelManager
from detection.processors.result_validator import ResultValidator, ValidationError
from detection.results.schema import FrameDetectionResult, DetectionItem, BoundingBox


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset ModelManager singleton state between tests."""
    mgr = ModelManager()
    mgr.is_loaded = False
    mgr.model = None
    yield
    mgr.unload_model()


@pytest.fixture
def engine():
    eng = DetectionEngine()
    eng.initialize()
    return eng


@pytest.fixture
def valid_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ─── Task 4: Frame Validation Tests ──────────────────────────────────────────

class TestFrameValidation:

    def test_none_frame_raises(self):
        """None frame must raise FrameValidationError, not AttributeError."""
        with pytest.raises(FrameValidationError, match="None"):
            DetectionEngine.validate_frame(None)

    def test_non_ndarray_raises(self):
        """Non-ndarray input must raise FrameValidationError."""
        with pytest.raises(FrameValidationError):
            DetectionEngine.validate_frame("not_a_frame")

    def test_empty_array_raises(self):
        """Zero-element array must raise FrameValidationError."""
        with pytest.raises(FrameValidationError, match="zero elements"):
            DetectionEngine.validate_frame(np.array([]))

    def test_wrong_dims_raises(self):
        """2D grayscale array must raise FrameValidationError."""
        with pytest.raises(FrameValidationError, match="3-dimensional"):
            DetectionEngine.validate_frame(np.zeros((480, 640), dtype=np.uint8))

    def test_zero_height_raises(self):
        """Frame with zero height dimension must raise FrameValidationError."""
        with pytest.raises(FrameValidationError):
            DetectionEngine.validate_frame(np.zeros((0, 640, 3), dtype=np.uint8))

    def test_wrong_channels_raises(self):
        """4-channel (RGBA) frame must raise FrameValidationError."""
        with pytest.raises(FrameValidationError, match="3 channels"):
            DetectionEngine.validate_frame(np.zeros((480, 640, 4), dtype=np.uint8))

    def test_unsupported_dtype_raises(self):
        """int16 dtype must raise FrameValidationError."""
        with pytest.raises(FrameValidationError, match="dtype"):
            DetectionEngine.validate_frame(np.zeros((480, 640, 3), dtype=np.int16))

    def test_valid_uint8_passes(self):
        """Valid uint8 frame must not raise."""
        DetectionEngine.validate_frame(np.zeros((480, 640, 3), dtype=np.uint8))

    def test_valid_float32_passes(self):
        """Valid float32 frame must not raise."""
        DetectionEngine.validate_frame(np.zeros((480, 640, 3), dtype=np.float32))

    def test_invalid_frame_returns_empty_result(self, engine):
        """Engine must return empty FrameDetectionResult (not crash) on invalid frame."""
        result = engine.detect_persons(frame=None, camera_id="test_cam", frame_number=1)
        assert isinstance(result, FrameDetectionResult)
        assert result.total_persons_detected == 0
        assert result.detections == []

    def test_wrong_channel_frame_returns_empty_result(self, engine):
        """4-channel frame must return empty result without crash."""
        bad_frame = np.zeros((480, 640, 4), dtype=np.uint8)
        result = engine.detect_persons(frame=bad_frame, camera_id="cam", frame_number=1)
        assert isinstance(result, FrameDetectionResult)
        assert result.total_persons_detected == 0


# ─── Task 7: Thread-Safe Concurrent Inference Tests ──────────────────────────

class TestConcurrentInference:

    def test_concurrent_metrics_are_accurate(self, engine, valid_frame):
        """
        Run N frames concurrently from M threads.
        total_frames_processed must equal N*M exactly — no race conditions.
        """
        n_threads = 5
        n_frames_per_thread = 4
        expected_total = n_threads * n_frames_per_thread
        errors = []

        def run_inference():
            try:
                for i in range(n_frames_per_thread):
                    engine.detect_persons(
                        frame=valid_frame.copy(),
                        camera_id=f"cam_{threading.current_thread().name}",
                        frame_number=i,
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=run_inference) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"
        assert engine.total_frames_processed == expected_total, (
            f"Expected {expected_total} frames, got {engine.total_frames_processed}"
        )

    def test_concurrent_results_are_valid(self, engine, valid_frame):
        """All concurrent results must be FrameDetectionResult instances."""
        results = []
        lock = threading.Lock()

        def run():
            r = engine.detect_persons(frame=valid_frame.copy(), camera_id="cc", frame_number=0)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 8
        for r in results:
            assert isinstance(r, FrameDetectionResult)


# ─── Task 2: Reload Model (Deadlock-Free) ────────────────────────────────────

class TestModelReload:

    def test_reload_does_not_deadlock(self):
        """reload_model() must complete within 10 seconds — no deadlock."""
        mgr = ModelManager()
        mgr.load_model()

        completed = threading.Event()

        def do_reload():
            mgr.reload_model()
            completed.set()

        t = threading.Thread(target=do_reload)
        t.start()
        finished = completed.wait(timeout=10.0)
        assert finished, "reload_model() deadlocked — did not complete within 10s"
        assert mgr.is_loaded is True

    def test_reload_model_is_loaded_after(self):
        """After reload, model must be loaded and health_check must pass."""
        mgr = ModelManager()
        mgr.load_model()
        result = mgr.reload_model()
        assert result is True
        assert mgr.health_check() is True

    def test_reload_multiple_times(self):
        """Multiple sequential reloads must all succeed without error."""
        mgr = ModelManager()
        for _ in range(3):
            assert mgr.reload_model() is True


# ─── Task 3: GPU Unload (VRAM cleanup) ───────────────────────────────────────

class TestModelUnload:

    def test_unload_clears_model(self):
        """After unload, model must be None and is_loaded must be False."""
        mgr = ModelManager()
        mgr.load_model()
        mgr.unload_model()
        assert mgr.model is None
        assert mgr.is_loaded is False

    def test_unload_twice_is_safe(self):
        """Calling unload twice must not raise any exception."""
        mgr = ModelManager()
        mgr.load_model()
        mgr.unload_model()
        mgr.unload_model()  # second call — must be safe


# ─── Task 8: Result Validator Tests ──────────────────────────────────────────

class TestResultValidator:

    @pytest.fixture
    def validator(self):
        return ResultValidator(person_class_id=0)

    def _make_detection(self, x1=10, y1=10, x2=200, y2=400, conf=0.9, cls=0, w=None, h=None):
        w = w if w is not None else (x2 - x1)
        h = h if h is not None else (y2 - y1)
        return DetectionItem(
            class_id=cls,
            class_name="person",
            confidence=conf,
            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
            center=((x1 + x2) / 2, (y1 + y2) / 2),
            width=w,
            height=h,
        )

    def test_valid_detection_passes(self, validator):
        """A geometrically valid detection must pass validation."""
        det = self._make_detection()
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 1

    def test_zero_width_rejected(self, validator):
        """Zero-width bbox must be rejected."""
        det = self._make_detection(x1=100, x2=100, y1=10, y2=200, w=0)
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_zero_height_rejected(self, validator):
        """Zero-height bbox must be rejected."""
        det = self._make_detection(y1=100, y2=100, h=0)
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_out_of_bounds_x2_rejected(self, validator):
        """BBox x2 exceeding frame width must be rejected."""
        det = self._make_detection(x2=700)  # frame width=640
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_negative_x1_rejected(self, validator):
        """BBox with negative x1 must be rejected."""
        det = self._make_detection(x1=-5)
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_wrong_class_rejected(self, validator):
        """Non-person class_id must be rejected."""
        det = self._make_detection(cls=2)  # car
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_invalid_confidence_rejected(self, validator):
        """Confidence > 1.0 must be rejected."""
        det = self._make_detection(conf=1.5)
        result = validator.validate([det], frame_resolution=(640, 480))
        assert len(result) == 0

    def test_mixed_detections_filters_correctly(self, validator):
        """Mix of valid and invalid — only valid ones returned."""
        good = self._make_detection(x1=10, y1=10, x2=200, y2=400)
        bad_cls = self._make_detection(cls=2)
        bad_bounds = self._make_detection(x2=700)
        result = validator.validate([good, bad_cls, bad_bounds], frame_resolution=(640, 480))
        assert len(result) == 1
        assert result[0].class_id == 0

    def test_empty_list_returns_empty(self, validator):
        """Empty input must return empty list."""
        result = validator.validate([], frame_resolution=(640, 480))
        assert result == []


# ─── Task 9: Enterprise Observability Metadata Tests ─────────────────────────

class TestObservabilityMetadata:

    def test_result_has_frame_uuid(self, engine, valid_frame):
        """FrameDetectionResult must include a non-empty frame_uuid."""
        result = engine.detect_persons(frame=valid_frame, camera_id="obs_cam", frame_number=1)
        assert hasattr(result, "frame_uuid")
        assert len(result.frame_uuid) > 0

    def test_frame_uuids_are_unique(self, engine, valid_frame):
        """Each frame result must have a unique frame_uuid."""
        r1 = engine.detect_persons(frame=valid_frame, camera_id="cam", frame_number=1)
        r2 = engine.detect_persons(frame=valid_frame, camera_id="cam", frame_number=2)
        assert r1.frame_uuid != r2.frame_uuid

    def test_result_has_model_name(self, engine, valid_frame):
        """FrameDetectionResult must include a model_name field."""
        result = engine.detect_persons(frame=valid_frame, camera_id="obs_cam", frame_number=1)
        assert hasattr(result, "model_name")
        assert result.model_name != ""

    def test_result_has_pipeline_version(self, engine, valid_frame):
        """FrameDetectionResult must include pipeline_version."""
        result = engine.detect_persons(frame=valid_frame, camera_id="obs_cam", frame_number=1)
        assert hasattr(result, "pipeline_version")
        assert result.pipeline_version == "3.1.0"

    def test_result_has_inference_engine_version(self, engine, valid_frame):
        """FrameDetectionResult must include inference_engine_version."""
        result = engine.detect_persons(frame=valid_frame, camera_id="obs_cam", frame_number=1)
        assert hasattr(result, "inference_engine_version")
        assert result.inference_engine_version == "3.1.0"

    def test_to_dict_includes_metadata(self, engine, valid_frame):
        """to_dict() must include all enterprise observability fields."""
        result = engine.detect_persons(frame=valid_frame, camera_id="obs_cam", frame_number=1)
        d = result.to_dict()
        assert "frame_uuid" in d
        assert "model_name" in d
        assert "pipeline_version" in d
        assert "inference_engine_version" in d

    def test_engine_metrics_include_version(self, engine, valid_frame):
        """get_engine_metrics() must report pipeline and engine versions."""
        engine.detect_persons(frame=valid_frame, camera_id="cam", frame_number=0)
        metrics = engine.get_engine_metrics()
        assert "pipeline_version" in metrics
        assert "inference_engine_version" in metrics
        assert "model_name" in metrics
