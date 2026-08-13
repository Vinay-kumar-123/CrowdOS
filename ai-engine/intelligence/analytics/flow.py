"""
Flow Analytics Engine.
Calculates windowed entry rates, exit rates, net flow rates (1m, 5m, 15m, 60m),
and cumulative totals per gate and venue-wide.
Handles out-of-order timestamps and duplicate suppression deterministically.
"""
import time
import threading
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field
from intelligence.utils.bounded_window import BoundedTimeWindow, parse_timestamp_epoch


class FlowMetrics(BaseModel):
    """
    Structured payload for venue or gate-level Flow Analytics.
    """
    venue_id: str = Field(default="default_venue")
    gate_id: Optional[str] = Field(default=None, description="None for venue-wide, str for gate-level")

    # Cumulative totals
    cumulative_entries: int = Field(default=0)
    cumulative_exits: int = Field(default=0)
    cumulative_net_flow: int = Field(default=0, description="cumulative_entries - cumulative_exits")

    # Windowed Rates (persons per minute)
    entry_rate_1m: float = Field(default=0.0)
    exit_rate_1m: float = Field(default=0.0)
    net_flow_rate_1m: float = Field(default=0.0)

    entry_rate_5m: float = Field(default=0.0)
    exit_rate_5m: float = Field(default=0.0)
    net_flow_rate_5m: float = Field(default=0.0)

    entry_rate_15m: float = Field(default=0.0)
    exit_rate_15m: float = Field(default=0.0)
    net_flow_rate_15m: float = Field(default=0.0)

    entry_rate_60m: float = Field(default=0.0)
    exit_rate_60m: float = Field(default=0.0)
    net_flow_rate_60m: float = Field(default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class FlowAnalytics:
    """
    Thread-safe Flow Analytics Calculator.
    Maintains 1m, 5m, 15m, and 60m bounded time windows for arbitrary gates and venue-wide.
    """

    def __init__(self, venue_id: str = "default_venue"):
        self.venue_id = venue_id
        self._lock = threading.Lock()

        # Cumulative totals
        self._venue_cum_entries = 0
        self._venue_cum_exits = 0
        self._gate_cum_entries: Dict[str, int] = {}
        self._gate_cum_exits: Dict[str, int] = {}

        # Deduplication tracking for duplicate events
        self._seen_event_ids: Set[str] = set()
        self._max_seen_event_ids = 20000

        # Sliding windows for venue (entry & exit)
        self._venue_entry_1m = BoundedTimeWindow(60.0)
        self._venue_entry_5m = BoundedTimeWindow(300.0)
        self._venue_entry_15m = BoundedTimeWindow(900.0)
        self._venue_entry_60m = BoundedTimeWindow(3600.0)

        self._venue_exit_1m = BoundedTimeWindow(60.0)
        self._venue_exit_5m = BoundedTimeWindow(300.0)
        self._venue_exit_15m = BoundedTimeWindow(900.0)
        self._venue_exit_60m = BoundedTimeWindow(3600.0)

        # Sliding windows per gate: gate_id -> { 'entry_1m': ..., 'exit_1m': ... }
        self._gate_windows: Dict[str, Dict[str, BoundedTimeWindow]] = {}

    def _get_or_create_gate_windows(self, gate_id: str) -> Dict[str, BoundedTimeWindow]:
        if gate_id not in self._gate_windows:
            self._gate_windows[gate_id] = {
                "entry_1m": BoundedTimeWindow(60.0),
                "entry_5m": BoundedTimeWindow(300.0),
                "entry_15m": BoundedTimeWindow(900.0),
                "entry_60m": BoundedTimeWindow(3600.0),
                "exit_1m": BoundedTimeWindow(60.0),
                "exit_5m": BoundedTimeWindow(300.0),
                "exit_15m": BoundedTimeWindow(900.0),
                "exit_60m": BoundedTimeWindow(3600.0),
            }
        return self._gate_windows[gate_id]

    def record_event(
        self,
        event_type: str,
        gate_id: str,
        timestamp: Optional[str] = None,
        event_id: Optional[str] = None
    ) -> bool:
        """
        Record a movement event (ENTRY or EXIT).
        Returns True if processed, False if duplicate.
        """
        if event_type not in ("ENTRY", "EXIT"):
            return False

        with self._lock:
            if event_id:
                if event_id in self._seen_event_ids:
                    return False
                self._seen_event_ids.add(event_id)
                if len(self._seen_event_ids) > self._max_seen_event_ids:
                    # Clear half of oldest event IDs
                    self._seen_event_ids = set(list(self._seen_event_ids)[10000:])

            # Cumulative counts
            if event_type == "ENTRY":
                self._venue_cum_entries += 1
                self._gate_cum_entries[gate_id] = self._gate_cum_entries.get(gate_id, 0) + 1
            elif event_type == "EXIT":
                self._venue_cum_exits += 1
                self._gate_cum_exits[gate_id] = self._gate_cum_exits.get(gate_id, 0) + 1

            # Sliding windows
            gate_wins = self._get_or_create_gate_windows(gate_id)

            if event_type == "ENTRY":
                self._venue_entry_1m.add(1, timestamp)
                self._venue_entry_5m.add(1, timestamp)
                self._venue_entry_15m.add(1, timestamp)
                self._venue_entry_60m.add(1, timestamp)

                gate_wins["entry_1m"].add(1, timestamp)
                gate_wins["entry_5m"].add(1, timestamp)
                gate_wins["entry_15m"].add(1, timestamp)
                gate_wins["entry_60m"].add(1, timestamp)
            else:
                self._venue_exit_1m.add(1, timestamp)
                self._venue_exit_5m.add(1, timestamp)
                self._venue_exit_15m.add(1, timestamp)
                self._venue_exit_60m.add(1, timestamp)

                gate_wins["exit_1m"].add(1, timestamp)
                gate_wins["exit_5m"].add(1, timestamp)
                gate_wins["exit_15m"].add(1, timestamp)
                gate_wins["exit_60m"].add(1, timestamp)

        return True

    def get_venue_flow(self, current_time: Optional[float] = None) -> FlowMetrics:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            e1 = self._venue_entry_1m.count(now) / 1.0
            e5 = self._venue_entry_5m.count(now) / 5.0
            e15 = self._venue_entry_15m.count(now) / 15.0
            e60 = self._venue_entry_60m.count(now) / 60.0

            x1 = self._venue_exit_1m.count(now) / 1.0
            x5 = self._venue_exit_5m.count(now) / 5.0
            x15 = self._venue_exit_15m.count(now) / 15.0
            x60 = self._venue_exit_60m.count(now) / 60.0

            cum_e = self._venue_cum_entries
            cum_x = self._venue_cum_exits

        return FlowMetrics(
            venue_id=self.venue_id,
            gate_id=None,
            cumulative_entries=cum_e,
            cumulative_exits=cum_x,
            cumulative_net_flow=cum_e - cum_x,
            entry_rate_1m=round(e1, 2),
            exit_rate_1m=round(x1, 2),
            net_flow_rate_1m=round(e1 - x1, 2),
            entry_rate_5m=round(e5, 2),
            exit_rate_5m=round(x5, 2),
            net_flow_rate_5m=round(e5 - x5, 2),
            entry_rate_15m=round(e15, 2),
            exit_rate_15m=round(x15, 2),
            net_flow_rate_15m=round(e15 - x15, 2),
            entry_rate_60m=round(e60, 2),
            exit_rate_60m=round(x60, 2),
            net_flow_rate_60m=round(e60 - x60, 2)
        )

    def get_gate_flow(self, gate_id: str, current_time: Optional[float] = None) -> FlowMetrics:
        now = current_time if current_time is not None else time.time()
        with self._lock:
            gate_wins = self._gate_windows.get(gate_id)
            if not gate_wins:
                return FlowMetrics(venue_id=self.venue_id, gate_id=gate_id)

            e1 = gate_wins["entry_1m"].count(now) / 1.0
            e5 = gate_wins["entry_5m"].count(now) / 5.0
            e15 = gate_wins["entry_15m"].count(now) / 15.0
            e60 = gate_wins["entry_60m"].count(now) / 60.0

            x1 = gate_wins["exit_1m"].count(now) / 1.0
            x5 = gate_wins["exit_5m"].count(now) / 5.0
            x15 = gate_wins["exit_15m"].count(now) / 15.0
            x60 = gate_wins["exit_60m"].count(now) / 60.0

            cum_e = self._gate_cum_entries.get(gate_id, 0)
            cum_x = self._gate_cum_exits.get(gate_id, 0)

        return FlowMetrics(
            venue_id=self.venue_id,
            gate_id=gate_id,
            cumulative_entries=cum_e,
            cumulative_exits=cum_x,
            cumulative_net_flow=cum_e - cum_x,
            entry_rate_1m=round(e1, 2),
            exit_rate_1m=round(x1, 2),
            net_flow_rate_1m=round(e1 - x1, 2),
            entry_rate_5m=round(e5, 2),
            exit_rate_5m=round(x5, 2),
            net_flow_rate_5m=round(e5 - x5, 2),
            entry_rate_15m=round(e15, 2),
            exit_rate_15m=round(x15, 2),
            net_flow_rate_15m=round(e15 - x15, 2),
            entry_rate_60m=round(e60, 2),
            exit_rate_60m=round(x60, 2),
            net_flow_rate_60m=round(e60 - x60, 2)
        )

    def get_all_gate_flows(self, current_time: Optional[float] = None) -> Dict[str, FlowMetrics]:
        with self._lock:
            gate_ids = list(self._gate_windows.keys())
        return {gid: self.get_gate_flow(gid, current_time) for gid in gate_ids}

    def reset(self) -> None:
        with self._lock:
            self._venue_cum_entries = 0
            self._venue_cum_exits = 0
            self._gate_cum_entries.clear()
            self._gate_cum_exits.clear()
            self._seen_event_ids.clear()

            self._venue_entry_1m.clear()
            self._venue_entry_5m.clear()
            self._venue_entry_15m.clear()
            self._venue_entry_60m.clear()

            self._venue_exit_1m.clear()
            self._venue_exit_5m.clear()
            self._venue_exit_15m.clear()
            self._venue_exit_60m.clear()

            self._gate_windows.clear()
