# Sprint 3 — Person Detection Engine

## Overview
Sprint 3 implements the **AI Person Detection Engine** for CrowdOS, built on Ultralytics YOLO11.
It receives frames from Sprint 2's Camera Infrastructure, performs GPU-accelerated inference,
filters exclusively for the `person` class (COCO Class ID 0), and outputs structured
`FrameDetectionResult` payloads for downstream AI modules (Tracking, Counting, Behavior Analysis).

---

## Detection Pipeline

```
[Sprint 2 Camera Frame]
         │
         ▼
[DetectionPipeline.process_frame()]
         │
         ▼
[Preprocessor.preprocess()]
  - Letterbox Resize (640×640)
  - Aspect Ratio Preserved
  - Padding with Neutral Gray (114,114,114)
         │
         ▼
[DetectionEngine.detect_persons()]
  - YOLO11 Model.predict()
  - Confidence: CONFIDENCE_THRESHOLD (default 0.45)
  - IoU NMS: IOU_THRESHOLD (default 0.45)
         │
         ▼
[Postprocessor.process_results()]
  - Filter Class ID == 0 (Person ONLY)
  - Drop all non-person classes
  - Clip bbox to original frame bounds
  - Construct DetectionItem objects
         │
         ▼
[FrameDetectionResult]
  - frame_number, camera_id, timestamp
  - inference_time_ms, device_used, resolution
  - List[DetectionItem]
         │
         ▼
[Downstream Module Callback]
  (Sprint 4 ByteTrack, Sprint 5 Counting, etc.)
```

---

## Module Reference

### `detection/config/settings.py` — `DetectionSettings`
Environment variable driven configuration.

| Variable | Default | Description |
|---|---|---|
| `MODEL_PATH` | `models/yolo11n.pt` | Path to YOLO weights |
| `MODEL_NAME` | `yolo11n` | Human-readable model name |
| `CONFIDENCE_THRESHOLD` | `0.45` | Minimum detection confidence |
| `IOU_THRESHOLD` | `0.45` | NMS IoU threshold |
| `IMG_SIZE` | `640` | YOLO input resolution |
| `DEVICE` | `auto` | `auto` / `cuda` / `cpu` / `mps` |
| `MAX_DETECTIONS` | `300` | Maximum persons per frame |
| `HALF_PRECISION` | `False` | Enable FP16 inference (GPU only) |
| `WARMUP_ITERATIONS` | `3` | GPU warmup forward passes |

---

### `detection/models/model_manager.py` — `ModelManager`
Singleton model lifecycle controller.

**Methods:**
- `load_model(model_path, device)` — Loads YOLO model with GPU/CPU auto-detect and CPU fallback
- `unload_model()` — Frees model from GPU/CPU memory
- `reload_model(model_path)` — Hot-reload without restarting the process
- `warmup_model(iterations)` — GPU warmup with dummy inference passes
- `health_check()` — Returns `True` if model is loaded and ready
- `get_model_info()` — Returns dict with model name, device, load time, VRAM

---

### `detection/processors/preprocessor.py` — `Preprocessor`
Frame preparation before YOLO inference.

- **Letterbox resize**: Scales frame to target size while preserving aspect ratio.
- **Gray padding**: Fills edges with neutral gray (114, 114, 114) to avoid distortion.
- **Metadata output**: Returns scale and padding for reverse coordinate transformation.

---

### `detection/processors/postprocessor.py` — `Postprocessor`
YOLO output filtering and DetectionItem construction.

- Filters **Class 0 (Person) ONLY** — zero tolerance for non-person classes.
- Clips bounding boxes to original frame bounds.
- Constructs fully populated `DetectionItem` objects.
- Respects `max_detections` limit per frame.

---

### `detection/engine/detection_engine.py` — `DetectionEngine`
Core inference executor.

- Calls `model.predict()` with Ultralytics YOLO API.
- Measures wall-clock inference time in milliseconds.
- Maintains cumulative stats: total frames, average FPS, average inference time.
- Auto-initializes model if not already loaded.

---

### `detection/pipeline/detection_pipeline.py` — `DetectionPipeline`
End-to-end orchestration layer connecting Sprint 2 and Sprint 3.

- Wraps `DetectionEngine` with Sprint 2-compatible frame consumer interface.
- Supports result callback injection for downstream Sprint modules.
- `get_camera_callback()` returns a callable compatible with `CameraManager`.

---

## Detection Result Schema

### `DetectionItem`
```json
{
  "detection_id": "3f2d1a4b-...",
  "class_id": 0,
  "class_name": "person",
  "confidence": 0.9124,
  "bbox": [100.0, 150.0, 300.0, 500.0],
  "center": [200.0, 325.0],
  "width": 200.0,
  "height": 350.0
}
```

### `FrameDetectionResult`
```json
{
  "frame_number": 1204,
  "timestamp": "2026-08-07T00:30:00.000Z",
  "camera_id": "gate_entry_01",
  "inference_time_ms": 12.45,
  "total_persons_detected": 3,
  "device_used": "cuda",
  "resolution": [1280, 720],
  "detections": [ ... ]
}
```

---

## Integration with Sprint 2

```python
from camera.manager.camera_manager import CameraManager
from detection.pipeline.detection_pipeline import DetectionPipeline

pipeline = DetectionPipeline()
pipeline.initialize()

manager = CameraManager()
manager.register_camera(
    camera_id="gate_01",
    source="rtsp://192.168.1.10/stream1",
    camera_type="rtsp",
)

# Connect Sprint 2 frame output → Sprint 3 detection input
callback = pipeline.get_camera_callback()
# Attach callback to FrameConsumer in Sprint 2 StreamManager
```

---

## Commands

### Download YOLO11 Weights
```bash
# Nano — fastest inference (recommended for CPU)
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

# Small — balanced accuracy/speed
python -c "from ultralytics import YOLO; YOLO('yolo11s.pt')"

# Medium — best accuracy/speed tradeoff
python -c "from ultralytics import YOLO; YOLO('yolo11m.pt')"
```

### Run Detection Engine
```bash
cd ai-engine
python -c "
import numpy as np
from detection.pipeline.detection_pipeline import DetectionPipeline

pipeline = DetectionPipeline()
pipeline.initialize()

frame = np.zeros((720, 1280, 3), dtype='uint8')
result = pipeline.process_frame(frame, camera_id='gate_01', frame_number=1)
print(result.to_dict())
"
```

### Run Benchmark
```bash
cd ai-engine
python -m detection.benchmark.benchmark
```

### Run Tests
```bash
cd ai-engine
python -m pytest detection/tests/ -v
```

---

## Performance Targets

| Model | Device | Target FPS | P99 Latency |
|---|---|---|---|
| yolo11n | CPU | ~30 FPS | < 50ms |
| yolo11n | CUDA GPU | ~180 FPS | < 8ms |
| yolo11s | CUDA GPU | ~120 FPS | < 12ms |
| yolo11m | CUDA GPU | ~80 FPS | < 18ms |

---

## Future Integration (Sprint 4+)

| Sprint | Module | Input |
|---|---|---|
| Sprint 4 | ByteTrack Tracker | `List[DetectionItem]` |
| Sprint 5 | Entry/Exit Counter | `FrameDetectionResult` |
| Sprint 6 | Face Recognition | `DetectionItem.bbox` |
| Sprint 7 | Crowd Density | `FrameDetectionResult` |
| Sprint 8 | Behavior Analysis | `List[FrameDetectionResult]` |
| Sprint 9 | Alert Engine | `FrameDetectionResult` |

> All future modules consume `FrameDetectionResult` directly.  
> **No changes to the Detection Engine will be required.**
