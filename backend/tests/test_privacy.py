import pytest

FORBIDDEN_KEYS = {
    "embedding",
    "embeddings",
    "face_crop",
    "face_crops",
    "biometric_vector",
    "biometric_vectors",
    "raw_frame",
    "raw_frames",
    "raw_image",
    "raw_images",
    "raw_video",
    "face_embedding",
    "face_embeddings",
    "identity_token",
}


def assert_no_forbidden_keys(data, path="root"):
    """Recursively assert that none of the forbidden keys exist in the payload."""
    if isinstance(data, dict):
        for k, v in data.items():
            assert (
                k.lower() not in FORBIDDEN_KEYS
            ), f"Forbidden biometric/identity key '{k}' found at path '{path}.{k}'"
            assert_no_forbidden_keys(v, f"{path}.{k}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            assert_no_forbidden_keys(item, f"{path}[{i}]")


@pytest.mark.asyncio
async def test_privacy_guarantee_across_all_endpoints(async_client):
    # 1. Create and start session
    s_res = await async_client.post(
        "/api/v1/venues/privacy_venue/sessions", json={"venue_capacity": 600}
    )
    assert_no_forbidden_keys(s_res.json(), "create_session")
    session_id = s_res.json()["session_id"]

    start_res = await async_client.post(
        f"/api/v1/venues/privacy_venue/sessions/{session_id}/start"
    )
    assert_no_forbidden_keys(start_res.json(), "start_session")

    # 2. Ingest ENTRY and EXIT
    e_res = await async_client.post(
        f"/api/v1/venues/privacy_venue/sessions/{session_id}/events",
        json={"event_type": "ENTRY", "gate_id": "gate_1", "event_id": "priv_1"},
    )
    assert_no_forbidden_keys(e_res.json(), "ingest_event")

    # 3. Query Intelligence endpoints
    endpoints_to_test = [
        "/api/v1/venues/privacy_venue/intelligence",
        "/api/v1/venues/privacy_venue/intelligence/flow",
        "/api/v1/venues/privacy_venue/intelligence/flow/gates",
        "/api/v1/venues/privacy_venue/intelligence/occupancy",
        "/api/v1/venues/privacy_venue/intelligence/density",
        "/api/v1/venues/privacy_venue/intelligence/dwell",
        "/api/v1/venues/privacy_venue/predictions",
        "/api/v1/venues/privacy_venue/predictions/risk",
        "/api/v1/venues/privacy_venue/predictions/decision",
        "/api/v1/venues/privacy_venue/predictions/forecast/occupancy",
        "/api/v1/venues/privacy_venue/predictions/forecast/flow",
        "/api/v1/venues/privacy_venue/alerts",
        "/api/v1/venues/privacy_venue/alerts/active",
        "/api/v1/venues/privacy_venue",
    ]

    for ep in endpoints_to_test:
        resp = await async_client.get(ep)
        assert resp.status_code == 200, f"Endpoint {ep} returned status {resp.status_code}"
        assert_no_forbidden_keys(resp.json(), ep)

    # 4. Stop session summary
    stop_res = await async_client.post(
        f"/api/v1/venues/privacy_venue/sessions/{session_id}/stop"
    )
    assert_no_forbidden_keys(stop_res.json(), "stop_session")
