# CrowdOS — Sprint 7: Event Intelligence & Session Management Engine

---

## Technical Specification & Architecture Document

### 1. Overview

The **Event Intelligence & Session Management Engine** (Sprint 7) converts low-level physical movement events, occupant state vectors, and journey lifecycles from the locked Sprint 6 Movement Engine into high-level venue intelligence, flow analytics, crowd density levels, rule-based congestion alerts, and post-session summaries.

---

### 2. Architectural Blueprint

```
Sprint 6 Movement Engine
       │ (EntryEvent, ExitEvent, OccupancyState, Journey)
       ▼
EventIntelligenceEngine (Orchestrator)
 ├── SessionManager           (CREATED -> ACTIVE -> PAUSED -> STOPPED -> EXPIRED)
 ├── FlowAnalytics            (Windowed rates 1m/5m/15m/60m, Net Flow = Entry - Exit)
 ├── OccupancyAnalytics       (Consumes Sprint 6 OccupancyState source of truth)
 ├── DensityAnalytics         (LOW, MODERATE, HIGH, CRITICAL & Congestion rules)
 ├── DwellAnalytics           (Mean, Median, Min, Max, Nearest-rank P95)
 ├── PeakTracker              (Peak occupancy, flow rates, timestamps, tie-breaking)
 ├── AnomalyDetector          (ENTRY_SURGE, EXIT_SURGE, SPIKE, STAGNATION, GATE_FLOW)
 ├── AlertManager             (ACTIVE/RESOLVED lifecycle, session-aware deduplication)
 └── IntelligenceMetricsTracker (In-process latency, error, throughput counters)
```

---

### 3. Key Subsystems & Rules

#### A. Occupancy Source of Truth Rule
Sprint 6 `OccupancyTracker` is the single authoritative source of physical occupancy. Sprint 7 `OccupancyAnalytics` consumes `OccupancyState` payloads and computes gate distributions, busiest gates, and least active gates without maintaining a competing entry/exit counter.

#### B. Session Lifecycle
- States: `CREATED`, `ACTIVE`, `PAUSED`, `STOPPED`, `EXPIRED`.
- Expiration: Evaluated deterministically via `check_expiration(now)`.
- Stopping a session generates an immutable frozen `SessionSummary` snapshot.

#### C. Flow & Rate Formulas
- Windowed Rate: `rate_per_minute = event_count / window_duration_minutes`
- Net Flow Rate: `net_flow_rate = entry_rate - exit_rate`
- Windows: 60s (1m), 300s (5m), 900s (15m), 3600s (60m).

#### D. Density & Congestion Rules
- Density Levels: `LOW`, `MODERATE`, `HIGH`, `CRITICAL` based on `CrowdThresholdConfig`.
- Congestion Levels: `NORMAL`, `BUILDING`, `CONGESTED`, `SEVERE_CONGESTION`. Hysteresis buffer prevents alert flapping.

#### E. Anomaly Detection & Alerts
- Rule-based sustained condition detection prevents alert spam on single noisy frames.
- Session-aware Deduplication Key: `session_id:venue_id:gate_id_or_GLOBAL:alert_type`.
- Resolution: Active alerts transition to `RESOLVED` when conditions subside. Recurrence generates a new `AlertEvent`.

---

### 4. Privacy & Security Guarantees
- Zero biometric vectors, face crops, or embeddings stored or logged.
- Bounded in-memory sliding windows prevent memory leaks.
- Structured JSON logging under logger namespace `crowdos.intelligence`.
