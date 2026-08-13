# CrowdOS — Camera Infrastructure Layer (Sprint 2)

The **Camera Infrastructure Layer** provides high-throughput, non-blocking, multi-source video capture, buffering, queuing, and health monitoring for **CrowdOS**.

It isolates video frame ingestion from downstream AI perception workers, ensuring zero frame dropping on low-latency IP camera streams.

---

## Module Overview

```
ai-engine/camera/
├── capture/     # Physical & network stream capture abstractions (USB, RTSP, MP4, Drone)
├── buffer/      # Thread-safe FIFO Ring Buffer for latest frame retention
├── queue/       # Async asyncio.Queue with configurable backpressure policies
├── health/      # Camera connection, active FPS, latency, and heartbeat monitors
├── workers/     # Asynchronous task workers (Producer, Consumer, Health, CameraWorker)
├── stream/      # Per-camera StreamManager lifecycle controller (Start/Stop/Pause/Resume)
├── manager/     # Central CameraManager multi-stream registry and auto-reconnect coordinator
├── events/      # Internal event definitions (CameraConnected, QueueOverflow, etc.)
├── config/      # Environment-driven CameraSettings (timeouts, max cameras, queue limits)
└── utils/       # Structured JSON logger for camera events
```

---

## Module Responsibilities

1. **`capture/`**: Heterogeneous video source abstractions (`USBCameraCapture`, `RTSPCameraCapture`, `FileCameraCapture`). Implements `CameraFactory` for dynamic instantiation.
2. **`buffer/`**: `FrameBuffer` stores frames in a thread-safe `deque` (default capacity: 30 frames). Fast peek and pop for UI or analytical sampling.
3. **`queue/`**: `FrameQueue` wraps `asyncio.Queue` (default max size: 60) with automatic backpressure frame dropping (`DROP_OLDEST` or `DROP_NEWEST`).
4. **`health/`**: `CameraHealthService` continuously monitors connection state, active FPS, frame latency, dropped frame statistics, and heartbeat timestamps.
5. **`workers/`**:
   - `FrameProducer`: Async loop acquiring frames from `BaseCameraCapture` and pushing to buffer & queue.
   - `FrameConsumer`: Async loop pulling frames from `FrameQueue` and executing registered callbacks.
   - `HealthWorker`: Background auditor triggering automatic reconnection upon stream failure.
   - `CameraWorker`: Task wrapper managing Producer, Consumer, and Health workers per camera stream.
6. **`stream/`**: `StreamManager` orchestrates start, stop, pause, resume, and health querying for a single camera.
7. **`manager/`**: `CameraManager` manages global camera registrations, multi-camera start/stop/restart, and fault isolation (one failing camera will never affect others).

---

## Future AI Integration (Sprint 3 Roadmap)

In Sprint 3, downstream AI perception pipelines will hook directly into `FrameConsumer` callbacks:

```
[Camera Hardware] ──> [FrameProducer] ──> [FrameQueue] ──> [FrameConsumer] ──> [YOLOv8 / ByteTrack Worker]
```
- Zero architectural refactoring is needed to add AI models.
- Downstream AI workers simply register frame processing callbacks with `CameraManager.register_camera(..., frame_callback=yolo_pipeline)`.
