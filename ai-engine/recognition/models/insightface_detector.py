import uuid
from typing import List, Dict, Any, Optional
import numpy as np
import cv2
from recognition.models.base_detector import BaseFaceDetector, FaceDetectionItem
from recognition.config.settings import recognition_settings
from recognition.utils.logger import recognition_logger

try:
    import insightface
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False


class InsightFaceDetector(BaseFaceDetector):
    """
    InsightFace Face Detector implementation inheriting BaseFaceDetector.
    Detects face bounding boxes and 5-point facial landmarks within person crop region.
    """

    def __init__(
        self,
        min_confidence: float = recognition_settings.MIN_FACE_CONFIDENCE,
        device: str = recognition_settings.DEVICE,
        use_gpu: bool = recognition_settings.USE_GPU
    ):
        self.min_confidence = min_confidence
        self.device = device
        self.use_gpu = use_gpu

        self.app = None
        self._is_initialized = False
        self._backend_used = "OpenCV_Haar_Fallback"

        self.initialize()

    def initialize(self) -> bool:
        if HAS_INSIGHTFACE:
            try:
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.use_gpu else ['CPUExecutionProvider']
                self.app = insightface.app.FaceAnalysis(name='buffalo_l', providers=providers)
                self.app.prepare(ctx_id=0 if self.use_gpu else -1, det_size=(640, 640))
                self._backend_used = "InsightFace_RetinaFace"
                tracking_msg = "InsightFace RetinaFace detector initialized successfully"
            except Exception as e:
                recognition_logger.warning(
                    f"InsightFace app loading failed: {e}. Falling back to OpenCV Cascade detector."
                )
                self._backend_used = "OpenCV_Cascade_Fallback"
        else:
            self._backend_used = "OpenCV_Cascade_Fallback"

        self._is_initialized = True
        recognition_logger.info(
            f"InsightFaceDetector initialized using backend '{self._backend_used}'",
            extra={"device_used": self.device, "detector_backend": self._backend_used}
        )
        return True

    def detect_faces(
        self,
        image: np.ndarray,
        person_bbox: Optional[List[float]] = None
    ) -> List[FaceDetectionItem]:
        if image is None or image.size == 0:
            return []

        h_img, w_img = image.shape[:2]

        # Crop region if person_bbox provided
        if person_bbox:
            px1, py1, px2, py2 = [int(v) for v in person_bbox[:4]]
            px1, py1 = max(0, px1), max(0, py1)
            px2, py2 = min(w_img, px2), min(h_img, py2)
            if px2 <= px1 or py2 <= py1:
                return []
            crop_img = image[py1:py2, px1:px2]
            offset_x, offset_y = px1, py1
        else:
            crop_img = image
            offset_x, offset_y = 0, 0

        crop_h, crop_w = crop_img.shape[:2]
        if crop_h < 10 or crop_w < 10:
            return []

        results: List[FaceDetectionItem] = []

        if self._backend_used == "InsightFace_RetinaFace" and self.app is not None:
            try:
                faces = self.app.get(crop_img)
                for face in faces:
                    score = float(face.det_score)
                    if score < self.min_confidence:
                        continue
                    box = face.bbox.astype(float)
                    # Convert to frame coordinates
                    frame_box = [
                        box[0] + offset_x, box[1] + offset_y,
                        box[2] + offset_x, box[3] + offset_y
                    ]
                    landmarks = face.kps.copy() if hasattr(face, "kps") and face.kps is not None else None
                    if landmarks is not None:
                        landmarks[:, 0] += offset_x
                        landmarks[:, 1] += offset_y

                    fx1, fy1, fx2, fy2 = [int(v) for v in box[:4]]
                    fx1, fy1 = max(0, fx1), max(0, fy1)
                    fx2, fy2 = min(crop_w, fx2), min(crop_h, fy2)
                    face_crop = crop_img[fy1:fy2, fx1:fx2] if (fx2 > fx1 and fy2 > fy1) else None

                    item = FaceDetectionItem(
                        face_id=str(uuid.uuid4()),
                        bbox=frame_box,
                        confidence=score,
                        landmarks=landmarks,
                        crop=face_crop
                    )
                    results.append(item)
                return results
            except Exception as e:
                recognition_logger.warning(f"InsightFace detection error: {e}")

        # Fallback OpenCV Cascade Face Detector for testing / CPU environment
        try:
            gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY) if len(crop_img.shape) == 3 else crop_img
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            rects = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))

            for (x, y, w, h) in rects:
                frame_box = [
                    float(x + offset_x), float(y + offset_y),
                    float(x + w + offset_x), float(y + h + offset_y)
                ]
                face_crop = crop_img[y:y+h, x:x+w]
                # Synthesize 5-point facial landmarks for alignment
                kps = np.array([
                    [x + w * 0.3 + offset_x, y + h * 0.35 + offset_y], # Left eye
                    [x + w * 0.7 + offset_x, y + h * 0.35 + offset_y], # Right eye
                    [x + w * 0.5 + offset_x, y + h * 0.55 + offset_y], # Nose
                    [x + w * 0.35 + offset_x, y + h * 0.75 + offset_y],# Mouth left
                    [x + w * 0.65 + offset_x, y + h * 0.75 + offset_y] # Mouth right
                ], dtype=np.float32)

                item = FaceDetectionItem(
                    face_id=str(uuid.uuid4()),
                    bbox=frame_box,
                    confidence=0.85,
                    landmarks=kps,
                    crop=face_crop
                )
                results.append(item)
        except Exception as e:
            recognition_logger.error(f"Fallback face detection failed: {e}")

        return results

    def get_info(self) -> Dict[str, Any]:
        return {
            "detector_name": "InsightFaceDetector",
            "backend_used": self._backend_used,
            "min_confidence": self.min_confidence,
            "device": self.device,
            "is_initialized": self._is_initialized
        }
