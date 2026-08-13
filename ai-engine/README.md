# CrowdOS AI Engine Service

The **CrowdOS AI Engine** is an independent, high-performance vision service responsible for camera stream ingestion, object detection (YOLO), multi-object tracking (ByteTrack), and facial recognition (InsightFace).

## Service Architecture

```
ai-engine/
├── camera/       # RTSP / IP Camera stream capture abstraction
├── detection/    # YOLO / ONNX Runtime object detection wrappers
├── tracking/     # ByteTrack multi-object tracking engine
├── recognition/  # InsightFace feature embedding & matching
├── pipelines/    # High-throughput crowd analytics processing pipelines
├── services/     # Inference runner and API service abstractions
├── models/       # Local model weight management and caching
├── utils/        # Logger, helpers, and image preprocessing tools
└── config/       # Environment & runtime configurations
```

## Independence & Communication
- Runs as a standalone HTTP / gRPC service.
- Completely decoupled from Backend database and business logic.
- Communicates via RESTful / WebSocket APIs with the main CrowdOS Backend.
