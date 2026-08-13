import time
import uuid
from typing import List, Dict, Any, Optional
import numpy as np

from recognition.models.base_recognizer import BaseFaceRecognizer
from recognition.models.base_detector import BaseFaceDetector
from recognition.models.base_embedder import BaseFaceEmbedder
from recognition.models.base_matcher import BaseFaceMatcher
from recognition.models.base_store import BaseIdentityStore
from recognition.models.insightface_detector import InsightFaceDetector
from recognition.models.insightface_embedder import InsightFaceEmbedder
from recognition.models.cosine_matcher import CosineMatcher
from recognition.alignment.aligner import align_face_5point
from recognition.utils.quality import assess_face_quality, FaceQualityResult
from recognition.results.schema import RecognizedPerson, RecognitionStatus, FaceQualityStatus
from detection.results.schema import BoundingBox
from recognition.utils.logger import recognition_logger
from recognition.config.settings import recognition_settings


class InsightFaceRecognizer(BaseFaceRecognizer):
    """
    InsightFace Face Recognizer implementation inheriting BaseFaceRecognizer.
    Orchestrates detector, quality assessment, alignment, embedder, and matcher.
    """

    def __init__(
        self,
        detector: Optional[BaseFaceDetector] = None,
        embedder: Optional[BaseFaceEmbedder] = None,
        matcher: Optional[BaseFaceMatcher] = None,
    ):
        self.detector = detector or InsightFaceDetector()
        self.embedder = embedder or InsightFaceEmbedder()
        self.matcher = matcher or CosineMatcher()
        self._is_initialized = False

        self.initialize()

    def initialize(self) -> bool:
        det_ok = self.detector.initialize()
        emb_ok = self.embedder.initialize()
        self._is_initialized = det_ok and emb_ok
        recognition_logger.info("InsightFaceRecognizer initialized successfully")
        return True

    def recognize_face_in_track(
        self,
        frame: np.ndarray,
        person_bbox: List[float],
        camera_id: str,
        track_id: str,
        detection_id: str,
        identity_store: BaseIdentityStore,
        frame_number: int = 0
    ) -> RecognizedPerson:
        start_time = time.perf_counter()

        if frame is None or frame.size == 0 or not person_bbox:
            return RecognizedPerson(
                camera_id=camera_id,
                track_id=track_id,
                detection_id=detection_id,
                frame_number=frame_number,
                identity_status=RecognitionStatus.NO_FACE,
                processing_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )

        # 1. Detect faces inside person track region
        faces = self.detector.detect_faces(frame, person_bbox=person_bbox)
        if not faces:
            return RecognizedPerson(
                camera_id=camera_id,
                track_id=track_id,
                detection_id=detection_id,
                frame_number=frame_number,
                identity_status=RecognitionStatus.NO_FACE,
                processing_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )

        # Select highest confidence face detected in track crop
        face = max(faces, key=lambda f: f.confidence)
        face_id = face.face_id
        face_bbox_list = face.bbox
        bbox_obj = BoundingBox(
            x1=float(face_bbox_list[0]), y1=float(face_bbox_list[1]),
            x2=float(face_bbox_list[2]), y2=float(face_bbox_list[3])
        )

        # 2. Quality Assessment
        face_crop = face.crop
        if face_crop is None:
            fx1, fy1, fx2, fy2 = [int(v) for v in face_bbox_list[:4]]
            h_f, w_f = frame.shape[:2]
            fx1, fy1 = max(0, fx1), max(0, fy1)
            fx2, fy2 = min(w_f, fx2), min(h_f, fy2)
            face_crop = frame[fy1:fy2, fx1:fx2] if (fx2 > fx1 and fy2 > fy1) else None

        quality_res = assess_face_quality(
            face_crop=face_crop,
            detection_confidence=face.confidence,
            landmarks=face.landmarks
        )

        if not quality_res.is_usable:
            recognition_logger.info(
                f"Face rejected due to quality ({quality_res.status.value}) for track {track_id} in camera {camera_id}",
                extra={
                    "camera_id": camera_id,
                    "track_id": track_id,
                    "quality_status": quality_res.status.value,
                    "quality_score": quality_res.score
                }
            )
            return RecognizedPerson(
                camera_id=camera_id,
                track_id=track_id,
                detection_id=detection_id,
                face_id=face_id,
                frame_number=frame_number,
                face_bbox=bbox_obj,
                face_confidence=face.confidence,
                face_quality_score=quality_res.score,
                face_quality_status=quality_res.status,
                identity_id="UNKNOWN",
                identity_status=RecognitionStatus.QUALITY_REJECTED,
                processing_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )

        # 3. Face Alignment
        aligned_face = align_face_5point(face_crop, landmarks=face.landmarks)

        # 4. Generate Face Embedding
        embedding = self.embedder.compute_embedding(aligned_face)
        if embedding is None:
            return RecognizedPerson(
                camera_id=camera_id,
                track_id=track_id,
                detection_id=detection_id,
                face_id=face_id,
                frame_number=frame_number,
                face_bbox=bbox_obj,
                face_confidence=face.confidence,
                face_quality_score=quality_res.score,
                face_quality_status=quality_res.status,
                identity_id="UNKNOWN",
                identity_status=RecognitionStatus.ERROR,
                processing_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2)
            )

        # 5. Identity Similarity Matching
        match_res = self.matcher.match_embedding(embedding, identity_store)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        recognition_logger.info(
            f"Recognized track {track_id} as '{match_res.identity_id}' (status={match_res.status.value}, score={match_res.similarity_score:.4f})",
            extra={
                "camera_id": camera_id,
                "track_id": track_id,
                "identity_id": match_res.identity_id,
                "identity_status": match_res.status.value,
                "similarity_score": round(match_res.similarity_score, 4),
                "processing_time_ms": round(elapsed_ms, 2)
            }
        )

        return RecognizedPerson(
            camera_id=camera_id,
            track_id=track_id,
            detection_id=detection_id,
            face_id=face_id,
            frame_number=frame_number,
            face_bbox=bbox_obj,
            face_confidence=face.confidence,
            face_quality_score=quality_res.score,
            face_quality_status=quality_res.status,
            identity_id=match_res.identity_id,
            identity_status=match_res.status,
            similarity_score=match_res.similarity_score,
            matching_threshold=match_res.threshold_used,
            recognizer_name="InsightFace",
            recognizer_version=recognition_settings.RECOGNIZER_VERSION,
            processing_time_ms=round(elapsed_ms, 2)
        )

    def reset(self) -> None:
        pass

    def destroy(self) -> None:
        self._is_initialized = False

    def get_info(self) -> Dict[str, Any]:
        return {
            "recognizer_name": "InsightFaceRecognizer",
            "detector_info": self.detector.get_info(),
            "embedder_info": self.embedder.get_info(),
            "matcher_info": self.matcher.get_info(),
            "is_initialized": self._is_initialized
        }
