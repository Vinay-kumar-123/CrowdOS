import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone


class CameraHealthService:
    """
    Enhanced Health Monitoring service tracking connection state, rolling FPS,
    average latency, frame drop rates, reconnect history, uptime, and health percentage.
    """
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.status = "DISCONNECTED"
        self.is_connected = False
        self.reconnecting = False
        self.start_timestamp: Optional[float] = None
        
        self.total_frames_received = 0
        self.total_frames_dropped = 0
        self.reconnect_count = 0
        self.reconnect_history: List[Dict[str, Any]] = []
        
        self.last_frame_timestamp: Optional[float] = None
        self.last_heartbeat_timestamp = time.time()
        
        # Sliding Window FPS & Latency metrics
        self.rolling_fps = 0.0
        self.last_fps_calc_time = time.time()
        self.frames_since_last_calc = 0
        
        self.total_latency_ms = 0.0
        self.latency_samples = 0
        self.last_latency_ms = 0.0

    def mark_connected(self) -> None:
        now = time.time()
        if not self.start_timestamp:
            self.start_timestamp = now
        self.is_connected = True
        self.reconnecting = False
        self.status = "CONNECTED"
        self.last_heartbeat_timestamp = now
        self.reconnect_history.append({
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "event": "CONNECTED",
        })

    def mark_disconnected(self) -> None:
        now = time.time()
        self.is_connected = False
        self.reconnecting = False
        self.status = "DISCONNECTED"
        self.rolling_fps = 0.0
        self.reconnect_history.append({
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "event": "DISCONNECTED",
        })

    def mark_reconnecting(self) -> None:
        now = time.time()
        self.reconnecting = True
        self.status = "RECONNECTING"
        self.reconnect_count += 1
        self.reconnect_history.append({
            "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "event": "RECONNECTING",
            "attempt": self.reconnect_count,
        })

    def record_frame(self, timestamp: Optional[float] = None) -> None:
        now = time.time()
        self.total_frames_received += 1
        self.frames_since_last_calc += 1
        self.last_frame_timestamp = timestamp or now
        self.last_heartbeat_timestamp = now
        
        if timestamp:
            latency = max(0.0, (now - timestamp) * 1000.0)
            self.last_latency_ms = latency
            self.total_latency_ms += latency
            self.latency_samples += 1

        # Recalculate rolling FPS every 1.0 second
        elapsed = now - self.last_fps_calc_time
        if elapsed >= 1.0:
            self.rolling_fps = round(self.frames_since_last_calc / elapsed, 2)
            self.frames_since_last_calc = 0
            self.last_fps_calc_time = now

    def record_dropped_frame(self) -> None:
        self.total_frames_dropped += 1

    def get_uptime_seconds(self) -> float:
        if not self.start_timestamp or not self.is_connected:
            return 0.0
        return round(time.time() - self.start_timestamp, 2)

    def calculate_health_percentage(self) -> float:
        """
        Calculate health percentage score from 0.0% to 100.0%.
        Based on connection status, frame drop rates, and latency.
        """
        if not self.is_connected or self.status != "CONNECTED":
            return 0.0

        score = 100.0

        # Deduct for dropped frame percentage
        total_total = self.total_frames_received + self.total_frames_dropped
        if total_total > 0:
            drop_rate = (self.total_frames_dropped / total_total) * 100.0
            score -= min(50.0, drop_rate * 2.0)

        # Deduct for high latency (> 100ms)
        if self.last_latency_ms > 100.0:
            score -= min(30.0, (self.last_latency_ms - 100.0) / 10.0)

        # Deduct for stale frames (> 3 seconds since last frame)
        if self.last_frame_timestamp:
            stale_sec = time.time() - self.last_frame_timestamp
            if stale_sec > 2.0:
                score -= min(40.0, (stale_sec - 2.0) * 10.0)

        return round(max(0.0, min(100.0, score)), 2)

    def get_health_report(self) -> Dict[str, Any]:
        now = time.time()
        total_total = self.total_frames_received + self.total_frames_dropped
        drop_rate_pct = round((self.total_frames_dropped / total_total) * 100.0, 2) if total_total > 0 else 0.0
        avg_latency = round(self.total_latency_ms / self.latency_samples, 2) if self.latency_samples > 0 else 0.0
        seconds_since_last_frame = round(now - self.last_frame_timestamp, 2) if self.last_frame_timestamp else None

        health_pct = self.calculate_health_percentage()

        return {
            "camera_id": self.camera_id,
            "status": self.status,
            "is_connected": self.is_connected,
            "reconnecting": self.reconnecting,
            "rolling_fps": self.rolling_fps,
            "current_latency_ms": round(self.last_latency_ms, 2),
            "avg_latency_ms": avg_latency,
            "total_frames_received": self.total_frames_received,
            "total_frames_dropped": self.total_frames_dropped,
            "frame_drop_rate_pct": drop_rate_pct,
            "reconnect_count": self.reconnect_count,
            "uptime_seconds": self.get_uptime_seconds(),
            "health_percentage": health_pct,
            "last_frame_time": datetime.fromtimestamp(self.last_frame_timestamp, timezone.utc).isoformat() if self.last_frame_timestamp else None,
            "seconds_since_last_frame": seconds_since_last_frame,
            "reconnect_history": self.reconnect_history[-5:],  # Last 5 reconnect events
            "healthy": health_pct >= 70.0,
        }
