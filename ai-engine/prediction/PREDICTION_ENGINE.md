# CrowdOS — Sprint 8: Predictive Crowd Risk & Decision Intelligence Engine

## 1. Overview & Architecture

The **Predictive Crowd Risk & Decision Intelligence Engine** is the Sprint 8 layer of the CrowdOS AI Engine. It consumes Sprint 7 outputs (flow analytics, occupancy states, crowd density, congestion levels, anomalies, dwell statistics) and transforms them into short-horizon predictive risk intelligence and explainable operational decision recommendations.

```
ai-engine/prediction/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py           # Forecast horizons, history bounds, hysteresis config
│   └── thresholds.py         # RiskLevel enum, risk score ranges, weight config
├── features/
│   ├── __init__.py
│   ├── snapshot.py           # PredictionInputSnapshot & GateInputSnapshot (immutable DTOs)
│   ├── feature_vector.py     # FeatureVector model (9 deterministic features)
│   ├── feature_extractor.py  # FeatureExtractor (deterministic computation)
│   └── normalization.py      # Safe normalizer (clamp, zero-denominator guard)
├── risk/
│   ├── __init__.py
│   ├── risk_level.py         # RiskLevel enum (LOW/GUARDED/ELEVATED/HIGH/CRITICAL)
│   ├── risk_score.py         # RiskScorer & RiskResult (weighted rule-based model)
│   └── risk_factors.py       # RiskFactor model & factor definitions
├── trend/
│   ├── __init__.py
│   ├── trend_state.py        # TrendDirection, TrendStrength, TrendResult
│   └── trend_detector.py     # TrendDetector (Theil-Sen median slope, bounded history)
├── forecast/
│   ├── __init__.py
│   ├── occupancy_forecast.py # OccupancyForecaster (Theil-Sen linear extrapolation)
│   └── flow_forecast.py      # FlowForecaster (rate trend projection)
├── decision/
│   ├── __init__.py
│   ├── decision_schema.py    # DecisionAction enum, DecisionResult model
│   ├── recommendations.py    # Explicit configurable rule table & priority resolution
│   └── decision_engine.py    # DecisionEngine (rule evaluation)
├── engine/
│   ├── __init__.py
│   └── prediction_engine.py  # PredictionEngine top-level orchestrator
├── metrics/
│   ├── __init__.py
│   └── metrics.py            # PredictionMetricsTracker (thread-safe counters)
├── utils/
│   ├── __init__.py
│   ├── bounded_history.py    # BoundedObservationHistory (max items + max age)
│   └── logger.py             # Structured JSON logger (crowdos.prediction namespace)
├── benchmark/
│   ├── __init__.py
│   └── benchmark.py          # PREDICTION ENGINE MICRO-BENCHMARK
└── tests/                    # 10 test modules with full edge case & regression coverage
```

---

## 2. Input Contract (`PredictionInputSnapshot`)

Sprint 8 accepts an immutable snapshot DTO capturing aggregate operational metrics.

### Privacy Assurance
- **ZERO** face crops
- **ZERO** raw images
- **ZERO** embeddings / biometric feature vectors
- **ZERO** individual identity tokens

### Input Validation Semantics
- **Negative occupancy / entry rate / exit rate / dwell:** Raises `ValueError("INVALID_INPUT: ...")`
- **NaN / Infinity in any field:** Raises `ValueError("INVALID_INPUT: ...")`
- **Negative venue capacity:** Raises `ValueError("INVALID_CONFIGURATION: ...")`
- **Zero venue capacity:** Valid configuration; sets `occupancy_ratio.feature_unavailable = True`
- **Negative net flow rate:** Valid physical signal (exits > entries); preserved as signed value

---

## 3. Feature Extraction Layer (9 Deterministic Features)

| Feature | Formula / Source | Valid Range | Zero-Denominator Policy |
|---|---|---|---|
| `occupancy_ratio` | `occupancy / venue_capacity` | [0.0, 2.0] | Unavailable if capacity == 0 |
| `entry_pressure` | `entry_rate_5m / safe_entry_rate` | [0.0, 3.0] | 0.0 if safe_rate == 0 |
| `exit_pressure` | `exit_rate_5m / safe_exit_rate` | [0.0, 3.0] | 0.0 if safe_rate == 0 |
| `net_inflow_pressure` | `net_flow_rate_5m / safe_net_flow_rate` | (-inf, +inf) | Signed (negative preserved) |
| `density_score` | Mapped from `CrowdDensityLevel` | [0.1, 1.0] | Always computable |
| `congestion_score` | Mapped from `CongestionLevel` | [0.0, 1.0] | Always computable |
| `anomaly_pressure` | Weighted sum / `max_anomaly_score` | [0.0, 1.0] | Clamped [0, 1] |
| `gate_imbalance` | `(max_rate - avg_rate) / max(0.01, avg_rate)` | [0.0, +inf) | 0.0 for single gate |
| `dwell_pressure` | `average_dwell / safe_dwell_seconds` | [0.0, 3.0] | 0.0 if safe_dwell == 0 |

---

## 4. Risk Scoring & Factors

Risk is evaluated deterministically on a **0–100 scale**:
$$\text{Score} = \sum_{i=1}^n \left( w_i \times \text{clamp}(\text{norm}_i, 0, 1) \times 100 \right)$$

### Default Weights
- `occupancy_ratio`: **0.30**
- `congestion_score`: **0.20**
- `entry_pressure`: **0.15**
- `net_inflow_pressure`: **0.15** *(clamped to [0,1] for risk contribution)*
- `anomaly_pressure`: **0.12**
- `gate_imbalance`: **0.05**
- `dwell_pressure`: **0.03**
- **Total:** **1.00**

### Risk Levels
- **0.0 – 19.9:** `LOW`
- **20.0 – 39.9:** `GUARDED`
- **40.0 – 59.9:** `ELEVATED`
- **60.0 – 79.9:** `HIGH`
- **80.0 – 100.0:** `CRITICAL`

---

## 5. Trend Detection & Short-Horizon Forecasting

### Trend Detection (Theil-Sen Slope)
- Computes the median slope of pairwise observations over bounded time history.
- Classifications:
  - `INCREASING` (slope $\ge +0.5$ pts/min)
  - `DECREASING` (slope $\le -0.5$ pts/min)
  - `STABLE` ($-0.5 <$ slope $< +0.5$ pts/min)
  - `INSUFFICIENT_DATA` ($N < 3$ observations)

### Forecasting (5m, 10m, 15m)
- Uses robust slope-based linear extrapolation.
- Confidence is data-sufficiency-based only:
  - `INSUFFICIENT_DATA` ($N < 5$)
  - `LOW` ($N \in [5, 9]$ or span $< 120\text{s}$)
  - `MEDIUM` ($N \in [10, 19]$ and span $\ge 120\text{s}$)
  - `HIGH` ($N \ge 20$ and span $\ge 300\text{s}$)
- If projected occupancy $>$ venue capacity, emits `CAPACITY_EXCEEDED_RISK` without clipping.

---

## 6. Operational Decision Engine

### Recommendations Only
> [!IMPORTANT]
> The engine produces operational suggestions for human operators. It **NEVER** directly commands or interfaces with physical gates, turnstiles, fire alarms, access control hardware, or barrier systems.

### Priority Rule Table & Conflict Resolution
1. **Priority 90:** `CRITICAL` + `INCREASING` + capacity exceeded $\rightarrow$ `EMERGENCY_REVIEW`
2. **Priority 80:** `CRITICAL` $\rightarrow$ `ESCALATE_OPERATOR`
3. **Priority 70:** `HIGH` + gate imbalance $\ge 2.0 \rightarrow$ `REDIRECT_FLOW`
4. **Priority 65:** `HIGH` + `INCREASING` + entry pressure $> 1.5 \rightarrow$ `REDUCE_GATE_INFLOW`
5. **Priority 60:** `HIGH` + (`STABLE` or `INCREASING`) + positive net flow $\rightarrow$ `CONTROL_ENTRY`
6. **Priority 50:** `HIGH` + `DECREASING` $\rightarrow$ `INCREASE_MONITORING`
7. **Priority 45:** `ELEVATED` + `INCREASING` $\rightarrow$ `INCREASE_MONITORING`
8. **Priority 40:** `ELEVATED` + (`STABLE` or `DECREASING`) $\rightarrow$ `MONITOR`
9. **Priority 35:** `GUARDED` $\rightarrow$ `MONITOR`
10. **Priority 20:** `LOW` + (`STABLE`, `DECREASING`, `INSUFFICIENT_DATA`) $\rightarrow$ `NO_ACTION`
- **Default:** `MONITOR`

---

## 7. Multi-Gate Isolation & Venue Aggregation
- Gates are processed in complete isolation.
- Each gate maintains its own independent history, trend detector, and hysteresis state.
- Venue risk incorporates total occupancy, overall flow, and gate imbalance without data bleed between gates.

---

## 8. Hysteresis & Persistence
- **Escalation:** Requires crossing threshold for 2 consecutive evaluation frames.
- **Recovery:** Requires dropping below threshold for 3 consecutive evaluation frames.
- Prevents oscillation and alert fatigue near decision boundaries.
