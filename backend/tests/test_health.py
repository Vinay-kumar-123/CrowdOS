import pytest


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Welcome to CrowdOS API"


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_status_endpoint(async_client):
    response = await async_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_root_ready_endpoint(async_client):
    response = await async_client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "mongodb_connected" in data
    assert "redis_connected" in data
    assert "ai_engine_ready" in data
    assert "camera_runtime_ready" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_api_ready_endpoint(async_client):
    response = await async_client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ai_engine_ready" in data
    assert "camera_runtime_ready" in data
