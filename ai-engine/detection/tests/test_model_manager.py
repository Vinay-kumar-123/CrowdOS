"""
Test: ModelManager lifecycle — load, warmup, unload, reload, health check, device detection.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detection.models.model_manager import ModelManager


@pytest.fixture(autouse=True)
def reset_model_manager():
    """Reset singleton state between tests."""
    manager = ModelManager()
    manager.is_loaded = False
    manager.model = None
    yield
    manager.unload_model()


def test_model_manager_is_singleton():
    """ModelManager must be a singleton — two instances must be the same object."""
    m1 = ModelManager()
    m2 = ModelManager()
    assert m1 is m2


def test_model_manager_load_success():
    """ModelManager should load successfully with mock fallback when weights unavailable."""
    manager = ModelManager()
    result = manager.load_model()
    # With MockYOLOModel fallback when ultralytics/weights unavailable
    assert result is True
    assert manager.is_loaded is True


def test_model_manager_health_check():
    """Health check must return True after model load."""
    manager = ModelManager()
    manager.load_model()
    assert manager.health_check() is True


def test_model_manager_unload():
    """After unload, model must be None and is_loaded must be False."""
    manager = ModelManager()
    manager.load_model()
    manager.unload_model()
    assert manager.is_loaded is False
    assert manager.model is None


def test_model_manager_reload():
    """Reload should unload and re-load the model successfully."""
    manager = ModelManager()
    manager.load_model()
    result = manager.reload_model()
    assert result is True
    assert manager.is_loaded is True


def test_model_manager_get_info():
    """get_model_info must return a dict with expected keys."""
    manager = ModelManager()
    manager.load_model()
    info = manager.get_model_info()
    assert "model_name" in info
    assert "device" in info
    assert "is_loaded" in info
    assert info["is_loaded"] is True


def test_model_manager_warmup_without_load():
    """Warmup should gracefully return False if model is not loaded."""
    manager = ModelManager()
    manager.is_loaded = False
    manager.model = None
    result = manager.warmup_model()
    assert result is False
