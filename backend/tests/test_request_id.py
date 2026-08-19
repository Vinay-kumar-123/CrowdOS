import pytest


@pytest.mark.asyncio
async def test_request_id_generated_and_returned_in_header(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    assert len(req_id) > 0


@pytest.mark.asyncio
async def test_request_id_propagated_from_client_header(async_client):
    custom_id = "custom-client-trace-12345"
    response = await async_client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


@pytest.mark.asyncio
async def test_request_id_present_on_error_responses(async_client):
    custom_id = "err-trace-999"
    response = await async_client.get(
        "/api/v1/venues/non_existent_venue/sessions",
        headers={"X-Request-ID": custom_id}
    )
    assert response.status_code == 404
    assert response.headers.get("X-Request-ID") == custom_id
    data = response.json()
    assert data.get("request_id") == custom_id
