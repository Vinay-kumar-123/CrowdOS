import pytest
from camera.manager.camera_manager import CameraManager


@pytest.mark.asyncio
async def test_camera_manager_lifecycle():
    manager = CameraManager()

    # Register camera
    registered = manager.register_camera(
        camera_id="test_cam_01",
        camera_name="Entrance Gate Camera",
        camera_type="file",
        camera_source="non_existent_file.mp4",
    )
    assert registered is True

    # Check status
    status = manager.get_camera_status("test_cam_01")
    assert status == "DISCONNECTED"

    # Get camera statistics
    stats = manager.get_camera_statistics("test_cam_01")
    assert stats is not None
    assert stats["camera_id"] == "test_cam_01"
    assert "health_score" in stats
    assert "queue_statistics" in stats

    # Active cameras list
    active_cams = manager.list_active_cameras()
    assert len(active_cams) == 1
    assert active_cams[0]["camera_id"] == "test_cam_01"

    # Remove camera
    removed = await manager.remove_camera("test_cam_01")
    assert removed is True
    assert len(manager.list_active_cameras()) == 0
