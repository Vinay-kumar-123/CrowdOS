from detection.config.settings import detection_settings


def detect_device(preferred_device: str = None) -> str:
    """
    Automatically detects available hardware accelerator (CUDA, MPS, CPU).
    Supports override via preferred_device.
    """
    target = preferred_device or detection_settings.DEVICE

    if target != "auto":
        return target.lower()

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    except ImportError:
        return "cpu"


def get_device_info() -> dict:
    """
    Returns hardware device information and memory metrics.
    """
    device = detect_device()
    info = {"device": device, "gpu_available": False, "gpu_name": None, "vram_total_mb": None}

    if device == "cuda":
        try:
            import torch
            info["gpu_available"] = True
            info["gpu_name"] = torch.cuda.get_device_name(0)
            info["vram_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024), 2)
        except Exception:
            pass

    return info
