# Shared Enums Module
from enum import Enum


class CameraType(str, Enum):
    IP_RTSP = "rtsp"
    USB = "usb"
    VIDEO_FILE = "video"
    DRONE = "drone"


class EventType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    OCCUPANCY_THRESHOLD = "occupancy_threshold"
    SECURITY_ALERT = "security_alert"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
