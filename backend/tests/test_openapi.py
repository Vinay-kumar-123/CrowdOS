import pytest
from app.main import app


def test_openapi_schema_generation():
    """Verify that OpenAPI schema generates completely without errors."""
    schema = app.openapi()
    assert schema is not None
    assert "paths" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "CrowdOS Backend API"

    # Verify key endpoints are documented
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/status" in paths
    assert "/api/v1/venues" in paths
    assert "/api/v1/venues/{venue_id}/sessions" in paths
    assert "/api/v1/venues/{venue_id}/sessions/{session_id}/events" in paths
    assert "/api/v1/venues/{venue_id}/intelligence" in paths
    assert "/api/v1/venues/{venue_id}/predictions" in paths
    assert "/api/v1/venues/{venue_id}/alerts" in paths
    assert "/api/v1/sessions/{session_id}/dashboard" in paths


@pytest.mark.asyncio
async def test_openapi_json_endpoint(async_client):
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "paths" in data
