# CrowdOS — Sprint 5: Face Recognition & Identity Association Engine

## Architectural Overview

The **Face Recognition & Identity Association Engine** (Sprint 5) provides enterprise-grade, model-agnostic face recognition for tracked persons output by the ByteTrack Tracking Engine (Sprint 4).

```
TrackingResult (Sprint 4) + Video Frame
                  │
                  ▼
         [ RecognitionEngine ]
                  │
  ┌───────────────┼───────────────┐
  │               │               │
  ▼               ▼               ▼
[ TrackCropper ] [ Detector ]   [ Associator ]
(Person crop)  (InsightFace /  (Geometrical
                Fallback)       containment)
                  │
                  ▼
      [ assess_face_quality ] (Blur, Brightness, Size, Confidence)
                  │
                  ▼
         [ align_face_5point ] (ArcFace 5-point similarity transform)
                  │
                  ▼
             [ Embedder ] (512-D L2-normalized vector)
                  │
                  ▼
              [ Matcher ] (Cosine similarity vs IdentityStore)
                  │
                  ▼
  [ TemporalRecognitionStabilizer ] (Camera/Track-isolated sliding window)
                  │
                  ▼
         [ RecognitionValidator ]
                  │
                  ▼
         RecognitionResult (Validated payload)
```

---

## Key Design Principles & Rules Enforced

1. **Model-Agnostic Abstractions**:
   - `BaseFaceDetector`, `BaseFaceEmbedder`, `BaseFaceMatcher`, `BaseFaceRecognizer`, `BaseIdentityStore`.
   - `RecognitionEngine` depends *only* on base interfaces, allowing seamless swapping of underlying implementations without touching orchestration logic.

2. **Isolated Camera State**:
   - Temporal recognition stabilization state is strictly scoped by `camera_id:track_id`.
   - Track ID 1 on `Camera_01` never shares recognition state with Track ID 1 on `Camera_02`.

3. **Traceability Preservation**:
   - Preserves complete lineage chain: `detection_id -> track_id -> face_id -> identity_id`.

4. **Privacy Safeguards**:
   - **Zero Biometric Logging**: Raw face embeddings, face crops, raw images, and biometric vectors are strictly prohibited from structured JSON logs (`RecognitionJSONFormatter` redacts vector outputs).
   - **No Vector Exposure**: `RecognizedPerson` schema does NOT include raw embedding attributes.
   - **Synthetic Testing**: All tests use synthetic reference embeddings; zero real biometric data is persisted.

5. **Temporal Policy**:
   - `MATCHED` status requires `TEMPORAL_CONFIRMATION_FRAMES` (default: 3) consistent frames.
   - Low quality, occlusion, or missing face frames (`NO_FACE`, `QUALITY_REJECTED`) preserve an established stable identity without overwriting.
   - `UNKNOWN` is always a valid outcome — matching is never forced.

---

## Verification & Test Suite

Run unit and integration tests:
```bash
python -m pytest recognition/tests/ -v
```

Full repository test suite execution:
```bash
python -m pytest
```
*Result: 191 passing tests across Sprints 1–5.*
