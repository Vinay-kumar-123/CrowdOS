"""
Sprint 5 - Recognition Engine Test Fixtures and Helpers
"""
import uuid
import numpy as np
import pytest
import cv2

from detection.results.schema import BoundingBox, DetectionItem, FrameDetectionResult
from tracking.results.schema import TrackingResult, TrackedPerson, TrackState
from recognition.models.in_memory_store import InMemoryIdentityStore
from recognition.models.insightface_recognizer import InsightFaceRecognizer
from recognition.engine.recognition_engine import RecognitionEngine
from recognition.config.settings import recognition_settings


def make_synthetic_embedding(seed: int = 42, dim: int = 512) -> np.ndarray:
    """Generate a deterministic L2-normalized synthetic embedding."""
    rng = np.random.RandomState(seed)
    raw = rng.randn(dim).astype(np.float32)
    norm = np.linalg.norm(raw)
    return raw / norm if norm > 1e-6 else raw


def make_synthetic_store(num_identities: int = 3, dim: int = 512) -> InMemoryIdentityStore:
    """Populate an InMemoryIdentityStore with synthetic reference embeddings."""
    store = InMemoryIdentityStore()
    for i in range(num_identities):
        store.add_identity(
            identity_id=f"synthetic_person_{i+1:03d}",
            embedding=make_synthetic_embedding(seed=100 + i, dim=dim)
        )
    return store


def make_blank_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Generate a blank BGR frame for unit testing."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def make_face_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Generate a frame with a simple high-contrast rectangle simulating a face region."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[50:200, 200:350] = [200, 160, 130]   # Face-tone rectangle
    return frame


def make_tracking_result(
    camera_id: str = "cam_test",
    frame_number: int = 1,
    num_tracks: int = 1,
    track_state: TrackState = TrackState.ACTIVE
) -> TrackingResult:
    """Build a synthetic TrackingResult for testing."""
    tracks = []
    for i in range(num_tracks):
        x1 = float(50 + i * 100)
        tracks.append(TrackedPerson(
            track_id=str(i + 1),
            detection_id=str(uuid.uuid4()),
            camera_id=camera_id,
            frame_number=frame_number,
            bbox=BoundingBox(x1=x1, y1=50.0, x2=x1 + 120.0, y2=350.0),
            confidence=0.88,
            center=(x1 + 60.0, 200.0),
            track_state=track_state
        ))

    return TrackingResult(
        frame_number=frame_number,
        camera_id=camera_id,
        tracking_time_ms=2.5,
        total_active_tracks=num_tracks,
        total_lost_tracks=0,
        tracks=tracks
    )


@pytest.fixture
def identity_store():
    return make_synthetic_store(num_identities=3)


@pytest.fixture
def blank_frame():
    return make_blank_frame()


@pytest.fixture
def face_frame():
    return make_face_frame()


@pytest.fixture
def recognizer():
    from recognition.models.insightface_embedder import InsightFaceEmbedder
    return InsightFaceRecognizer(embedder=InsightFaceEmbedder(allow_synthetic_fallback=True))


@pytest.fixture
def recognition_engine(recognizer, identity_store):
    return RecognitionEngine(recognizer, identity_store)
