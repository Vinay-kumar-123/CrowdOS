import time
from enum import Enum
from typing import List, Tuple, Optional
from collections import deque


class MovementState(str, Enum):
    """
    Standardized movement state machine states for person tracklets.
    UNKNOWN -> OUTSIDE -> APPROACHING_ENTRY -> ENTERED -> INSIDE -> APPROACHING_EXIT -> EXITED -> OUTSIDE
    (LOST and EXPIRED handle temporary track loss and track termination safely)
    """
    UNKNOWN = "UNKNOWN"
    OUTSIDE = "OUTSIDE"
    APPROACHING_ENTRY = "APPROACHING_ENTRY"
    ENTERED = "ENTERED"
    INSIDE = "INSIDE"
    APPROACHING_EXIT = "APPROACHING_EXIT"
    EXITED = "EXITED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"


class TrackMovementState:
    """
    Per-track movement state machine and sliding trajectory window buffer.
    Scoped by camera_id + gate_id + track_id.
    """

    def __init__(
        self,
        camera_id: str,
        gate_id: str,
        track_id: str,
        trajectory_window: int = 8,
        max_lost_frames: int = 30
    ):
        self.camera_id = camera_id
        self.gate_id = gate_id
        self.track_id = track_id
        self.trajectory_window = trajectory_window
        self.max_lost_frames = max_lost_frames

        self.current_state = MovementState.UNKNOWN
        self.previous_state = MovementState.UNKNOWN
        self.trajectory: deque[Tuple[float, float]] = deque(maxlen=trajectory_window)

        self.last_seen_frame: int = 0
        self.last_seen_time: float = time.time()
        self.frames_lost: int = 0
        self.entry_frame: Optional[int] = None
        self.entry_time: Optional[float] = None
        self.exit_frame: Optional[int] = None
        self.exit_time: Optional[float] = None

        self.associated_identity_id: str = "UNKNOWN"
        self.associated_identity_status: str = "UNKNOWN"

    def update_position(
        self,
        center: Tuple[float, float],
        frame_number: int,
        identity_id: Optional[str] = None,
        identity_status: Optional[str] = None
    ) -> None:
        """
        Record new center point position and update frame counter.
        """
        self.trajectory.append((float(center[0]), float(center[1])))
        self.last_seen_frame = frame_number
        self.last_seen_time = time.time()
        self.frames_lost = 0

        # Update identity enrichment if valid (non-unknown or preserving established)
        if identity_id and identity_id != "UNKNOWN":
            self.associated_identity_id = identity_id
            if identity_status:
                self.associated_identity_status = identity_status

        # Recover from LOST state if track reappears
        if self.current_state == MovementState.LOST:
            self.transition_to(self.previous_state if self.previous_state != MovementState.LOST else MovementState.INSIDE)

    def transition_to(self, new_state: MovementState) -> None:
        """
        Transition to a new movement state.
        """
        if self.current_state != new_state:
            self.previous_state = self.current_state
            self.current_state = new_state

    def mark_lost(self) -> None:
        """
        Temporarily mark track as LOST during detection gaps.
        DOES NOT TRIGGER premature EXIT.
        """
        self.frames_lost += 1
        if self.current_state != MovementState.LOST and self.current_state not in (MovementState.EXITED, MovementState.EXPIRED):
            self.previous_state = self.current_state
            self.current_state = MovementState.LOST

    def is_expired(self) -> bool:
        return self.frames_lost > self.max_lost_frames

    def get_trajectory_list(self) -> List[Tuple[float, float]]:
        return list(self.trajectory)
