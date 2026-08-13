# Enterprise Multi-Object Person Tracking Engine (Sprint 4)

## Architecture Overview

The **CrowdOS Multi-Object Person Tracking Engine** is an enterprise-grade perception component designed to assign persistent `Track ID`s to detected persons across video frames. It consumes detection payloads from Sprint 3 (`FrameDetectionResult`) and delivers stable trajectory tracking while maintaining per-camera state isolation and model-agnostic tracker abstractions.

```
                    ┌──────────────────────────────┐
                    │ Sprint 3 FrameDetectionResult│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      TrackingPipeline        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │       TrackValidator         │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        TrackingEngine        │
                    │   (Per-Camera Lock Map)      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    BaseTracker Interface     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │      ByteTrackTracker        │
                    │  (2-Stage IoU Association)   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        TrackingResult        │
                    │ (TrackedPerson Payload List) │
                    └──────────────────────────────┘
```

---

## Technical Features

1. **Faithful 2-Stage ByteTrack Algorithm**:
   - **Stage 1**: High-confidence detections (`confidence >= TRACK_THRESH`) matched against Kalman-predicted active tracklets via IoU distance.
   - **Stage 2**: Low-confidence detections (`MIN_CONFIDENCE <= confidence < TRACK_THRESH`) matched against remaining unmatched active tracks, preventing track fragmentation during partial occlusions.
2. **Model-Agnostic Abstraction (`BaseTracker`)**: `TrackingEngine` depends purely on the `BaseTracker` abstract interface. Future trackers (`DeepSORT`, `BoTSORT`, `OC-SORT`, `StrongSORT`) can be plugged in without modifying `TrackingEngine`.
3. **Per-Camera State Isolation**: Track IDs are independent per camera stream (`camera_id -> BaseTracker`). Thread locks ensure thread safety across concurrent multi-camera streams.
4. **Strict Re-Identification Bounds**: `REIDENTIFIED` represents purely spatial Kalman recovery of a lost track within `MAX_LOST_FRAMES`. No appearance/face models are included.
5. **Observability & Validation**: Structured JSON logging (zero `print` statements), schema validation (`TrackValidator`), and operational metrics tracking.

---

## Track Lifecycle & State Machine

```
   [ NEW Detection ]
           │
           ▼
        ( NEW )
           │
           │ High-Confidence Confirmation
           ▼
       ( ACTIVE ) ◄────────────────────────┐
           │                               │
           │ No Detection (Frame t)        │ High-Confidence Re-Observation
           ▼                               │ (within MAX_LOST_FRAMES)
        ( LOST ) ────► ( REIDENTIFIED ) ───┘
           │
           │ Exceeds MAX_LOST_FRAMES
           ▼
       ( REMOVED )
           │
           ▼
       ( EXPIRED ) (Purged from Memory)
```

| Track State | Description |
|---|---|
| `NEW` | Initial tracklet state generated on first high-confidence detection. |
| `ACTIVE` | Confirmed active track with consecutive detection updates. |
| `LOST` | Temporarily unobserved track retained in tracking buffer. |
| `REIDENTIFIED` | Spatial recovery of a lost track upon re-observation within `MAX_LOST_FRAMES`. |
| `REMOVED` | Track flagged for removal after grace period expiration. |
| `EXPIRED` | Track state permanently purged from active memory. |

---

## Folder Structure

```
ai-engine/tracking/
├── __init__.py
├── TRACKING_ENGINE.md
├── config/
│   ├── __init__.py
│   └── settings.py
├── models/
│   ├── __init__.py
│   ├── base_tracker.py
│   ├── track_state.py
│   ├── kalman_filter.py
│   └── bytetrack.py
├── engine/
│   ├── __init__.py
│   ├── tracking_engine.py
│   └── metrics.py
├── pipeline/
│   ├── __init__.py
│   ├── validator.py
│   └── tracking_pipeline.py
├── results/
│   ├── __init__.py
│   └── schema.py
├── benchmark/
│   ├── __init__.py
│   └── benchmark.py
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── bounding_box.py
│   └── matching.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_base_tracker.py
    ├── test_bytetrack.py
    ├── test_tracking_engine.py
    ├── test_tracking_pipeline.py
    ├── test_multi_camera.py
    ├── test_concurrency.py
    ├── test_validator.py
    └── test_benchmark.py
```

---

## Configuration Settings

Configured via environment variables or `.env` file using Pydantic Settings (`TrackingSettings`):

| Environment Variable | Default | Description |
|---|---|---|
| `TRACKER_TYPE` | `ByteTrack` | Active default tracking algorithm implementation. |
| `TRACK_THRESH` | `0.5` | High-confidence detection threshold for Stage 1 association. |
| `MIN_CONFIDENCE` | `0.1` | Low-confidence detection threshold for Stage 2 association. |
| `MATCH_THRESHOLD` | `0.8` | Maximum IoU distance threshold for Stage 1 matching. |
| `LOW_MATCH_THRESHOLD` | `0.5` | Maximum IoU distance threshold for Stage 2 matching. |
| `MAX_LOST_FRAMES` | `30` | Maximum consecutive frames to retain lost tracks before expiration. |
| `FRAME_RATE` | `30` | Video frame rate (FPS). |

---

## Running Verification & Tests

Run the full pytest suite for the tracking engine:
```bash
pytest ai-engine/tracking/tests/ -v
```

Run Sprint 1-3 regression tests:
```bash
pytest ai-engine/detection/tests/ -v
pytest ai-engine/tests/ -v
```

Run performance benchmarking suite:
```bash
python -m tracking.benchmark.benchmark
```

---

## Downstream Integration (Sprint 5 Ready)

Sprint 5 (Face Recognition Integration) can subscribe to `TrackingPipeline` output callbacks without altering the tracking engine:

```python
from tracking.pipeline.tracking_pipeline import TrackingPipeline

def sprint5_face_recognition_callback(tracking_result: TrackingResult):
    for person in tracking_result.tracks:
        if person.track_state in [TrackState.ACTIVE, TrackState.REIDENTIFIED]:
            # Perform facial crop & embedding extraction using person.bbox
            pass

pipeline = TrackingPipeline(result_callback=sprint5_face_recognition_callback)
```
