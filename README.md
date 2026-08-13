# CrowdOS — Enterprise AI Crowd Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-blue)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)

---

## 1. Project Overview

**CrowdOS** is a scalable, modular, enterprise-grade **AI Crowd Intelligence Platform**.

Designed for high-throughput, real-time computer vision analysis, CrowdOS monitors multiple Entry and Exit gates using CCTV/IP cameras. The initial MVP provides foundational gate monitoring, count analytics, and occupancy tracking, while the architecture is engineered to seamlessly expand into massive multi-facility deployments.

### Target Deployment Domains
- **Smart Cities** (Public Squares, Transit Hubs, Pedestrian Zones)
- **Shopping Malls & Retail Centers**
- **Airports, Railway & Metro Stations**
- **Factories & Industrial Complexes**
- **Stadiums & Arenas**
- **Temples & Pilgrimage Venues**
- **Hospitals, Schools & Universities**
- **High-Security Government Deployments**

---

## 2. Architecture

CrowdOS follows a **decoupled monorepo microservice architecture**:

```
                              ┌─────────────────────────┐
                              │     Next.js 15 Web      │
                              │     Dashboard (UI)      │
                              └────────────┬────────────┘
                                           │ HTTP / WS
                                           ▼
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│     MongoDB 7.0         │◄──┤   FastAPI Backend Service│◄──┤      Redis 7.2 Cache    │
│   (Async Motor Driver)  │   │  (Core API / WebSockets)│   │     & Event Pub/Sub     │
└─────────────────────────┘   └────────────┬────────────┘   └─────────────────────────┘
                                           │ Async HTTP / REST
                                           ▼
                              ┌─────────────────────────┐
                              │  Standalone AI Engine   │
                              │ (OpenCV, YOLO, ByteTrack│
                              │    InsightFace, ONNX)   │
                              └─────────────────────────┘
```

- **Frontend**: Next.js 15 with React 19 (App Router, Tailwind CSS). Serves real-time telemetry dashboards.
- **Backend API**: FastAPI on Python 3.12+ with Pydantic v2 validation. Asynchronously interacts with MongoDB via Motor driver and Redis cache.
- **AI Engine**: Completely independent Python computer vision service encapsulating stream ingestion, object detection (YOLO), multi-object tracking (ByteTrack), facial recognition (InsightFace), and ONNX runtime optimization.
- **Data & Cache Layer**: MongoDB for persisted logs and configuration; Redis for low-latency pub/sub and session caching.

---

## 3. Monorepo Folder Structure

```
CrowdOS/
├── frontend/                 # Next.js 15 App Router Frontend
│   ├── app/                  # App Router Pages & Layouts
│   │   ├── (auth)/login/     # Login Page
│   │   ├── (dashboard)/      # Protected Dashboard Shell
│   │   │   ├── dashboard/    # Main Gate Monitoring Dashboard
│   │   │   ├── reports/      # Historical Occupancy & Flow Reports
│   │   │   ├── analytics/    # Crowd Density & Trend Analytics
│   │   │   └── settings/     # Camera & Facility Settings
│   │   ├── layout.js         # Root Layout
│   │   └── page.js           # Entry Redirect Page
│   ├── components/           # Reusable UI, Chart & Camera Components
│   ├── hooks/                # Custom React Hooks
│   ├── services/             # API & WebSocket Communication Layer
│   ├── lib/                  # Utility Functions & Constants
│   ├── store/                # Global Application State Management
│   ├── styles/               # Global CSS & Tailwind Configurations
│   └── public/               # Static Web Assets
│
├── backend/                  # FastAPI Application Service
│   ├── app/
│   │   ├── api/              # API Versioning & Endpoints
│   │   │   └── v1/
│   │   │       ├── endpoints/# Health & Status Endpoints
│   │   │       └── router.py # v1 Aggregated Router
│   │   ├── core/             # Configuration, Settings (Pydantic v2), Logger, Events
│   │   ├── database/         # MongoDB (Motor) & Redis Async Drivers
│   │   ├── models/           # Base Database Models
│   │   ├── schemas/          # Pydantic v2 Request/Response Schemas
│   │   ├── services/         # Service Business Logic Layer
│   │   ├── repositories/     # Repository Data Access Layer
│   │   ├── middleware/       # CORS, Logging & Rate Limiting Middleware
│   │   ├── websocket/        # WebSocket Connection Manager & Stream Router
│   │   ├── utils/            # Helper Functions & Validators
│   │   └── main.py           # FastAPI Application Entry Point
│   └── tests/                # Async Unit & Integration Tests (pytest)
│
├── ai-engine/                # Independent AI Computer Vision Engine
│   ├── camera/               # RTSP / IP Camera Frame Capture Abstraction
│   ├── detection/            # YOLO & ONNX Object Detector Wrappers
│   ├── tracking/             # ByteTrack Multi-Object Tracking Engine
│   ├── recognition/          # InsightFace Feature Embeddings & Matching
│   ├── pipelines/            # High-Throughput Analytics Pipelines
│   ├── services/             # Inference Service Runners
│   ├── models/               # Model Weight Management
│   ├── utils/                # Preprocessing, Logger & Validators
│   ├── config/               # AI Engine Settings & Loggers
│   ├── main.py               # AI Engine FastAPI Entry Point
│   └── README.md             # AI Engine Architecture Guide
│
├── deployment/               # Enterprise Deployment Infrastructure
│   ├── nginx/                # Reverse Proxy Nginx Configuration
│   └── scripts/              # Automated Deployment & Health Check Scripts
│
├── datasets/                 # Training & Evaluation Datasets (.gitkeep)
├── models/                   # Local YOLO / ONNX Model Weights (.gitkeep)
├── docs/                     # System Architecture & API Specifications
├── scripts/                  # Project Management Scripts (setup.sh, etc.)
├── tests/                    # Integration & E2E Test Suite Placeholder
├── docker-compose.yml        # Docker Multi-Container Orchestration
├── .env.example              # Environment Variable Template
├── .gitignore                # Enterprise-Grade Git Ignore Specification
├── LICENSE                   # MIT Open-Source License
└── README.md                 # Master Project Documentation
```

---

## 4. Tech Stack (Locked Specification)

| Layer | Technology | Version / Details |
|---|---|---|
| **Frontend Framework** | Next.js | 15 (App Router) |
| **Frontend UI Library** | React | 19 |
| **Frontend Language** | JavaScript | ES6+ (No TypeScript) |
| **Styling** | Tailwind CSS | 3.4+ |
| **Frontend Package Manager** | pnpm | 9+ |
| **Backend Framework** | FastAPI | 0.115+ |
| **Backend Runtime** | Python | 3.12+ |
| **Validation Engine** | Pydantic | v2.9+ |
| **Backend Package Manager** | uv / pip | Latest |
| **Database Driver** | Motor | Async MongoDB Driver 3.6+ |
| **Database** | MongoDB | 7.0 |
| **Cache & PubSub** | Redis | 7.2 (Async redis-py) |
| **AI Computer Vision** | OpenCV, Ultralytics YOLO | 4.10+, 8.3+ |
| **AI Tracking & Face** | ByteTrack, InsightFace | Latest |
| **AI Inference** | ONNX Runtime | 1.19+ |
| **Containerization** | Docker & Docker Compose | Engine 24+, Compose v2 |

---

## 5. Development Setup

### Prerequisites
- **Node.js**: `v20.x` or higher
- **pnpm**: `v9.x` or higher (`npm i -g pnpm`)
- **Python**: `v3.12` or higher
- **uv** (Optional, recommended): `pip install uv`
- **Docker & Docker Compose**: Installed and running

### Step 1: Clone & Initialize Environment
```bash
git clone https://github.com/your-org/CrowdOS.git
cd CrowdOS

# Run setup script to copy environment files
bash scripts/setup.sh
```

---

## 6. Running Services Locally

### Frontend Commands (Next.js 15)
```bash
cd frontend
pnpm install
pnpm dev
# App running at http://localhost:3000
```

### Backend Commands (FastAPI)
```bash
cd backend
# Using uv (preferred):
uv venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
uv pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or standard pip:
pip install -r requirements.txt
python app.main
# API running at http://localhost:8000 (Swagger docs at /docs)
```

### AI Engine Commands (Standalone Vision Service)
```bash
cd ai-engine
pip install -r requirements.txt
python main.py
# AI Engine API running at http://localhost:8001 (Swagger docs at /docs)
```

---

## 7. Docker Setup & Startup

To start the entire enterprise stack (Frontend, Backend, AI Engine, MongoDB, Redis) in containerized mode:

```bash
# Build and launch all services in background
docker compose up --build -d

# Verify container health status
docker compose ps

# View unified logs
docker compose logs -f

# Stop container stack
docker compose down
```

### Container Endpoints Summary
- **Frontend Dashboard**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Backend API Docs**: `http://localhost:8000/docs`
- **AI Engine API**: `http://localhost:8001`
- **AI Engine Health**: `http://localhost:8001/health`
- **MongoDB**: `localhost:27017`
- **Redis**: `localhost:6379`

---

## 8. Project Roadmap & Future Modules

- [x] **Phase 1: Enterprise Monorepo Foundation & Microservice Scaffolding** (Completed)
- [ ] **Phase 2: Live Gate & RTSP Stream Integration**
  - RTSP stream manager implementation with frame buffering
  - Real-time WebSocket streaming pipeline connecting AI Engine to Frontend
- [ ] **Phase 3: Core Perception Engine Implementation**
  - YOLOv8 / YOLOv11 TensorRT & ONNX runtime optimization
  - ByteTrack multi-camera tracking integration
- [ ] **Phase 4: Face Recognition & Security Gate Analytics**
  - InsightFace embedding indexing with Vector DB / HNSW search
  - VIP / Blocklist real-time notification alerts
- [ ] **Phase 5: Smart City & Multi-Facility Aggregation Engine**
  - Cross-camera spatial crowd density heatmaps
  - Anomaly detection (stampede warning, flow stagnation, perimeter breach)

---

## 9. Contribution Guide

1. **Fork the Repository** and create your feature branch: `git checkout -b feature/amazing-feature`.
2. **Follow Architectural Scaffolding Rules**:
   - Strictly separate Frontend, Backend, and AI Engine.
   - Do not leak business logic into API router files.
   - Maintain strict type validation with Pydantic v2 schemas.
3. **Commit your changes**: `git commit -m 'feat: Add stream buffer manager'`.
4. **Push to branch**: `git push origin feature/amazing-feature`.
5. **Open a Pull Request**.

---

## 10. License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
