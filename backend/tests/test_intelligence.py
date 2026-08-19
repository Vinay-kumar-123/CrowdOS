import pytest


@pytest.mark.asyncio
async def test_intelligence_flow_and_gate_endpoints(async_client):
    # Setup session
    res = await async_client.post("/api/v1/venues/intel_venue/sessions", json={"venue_capacity": 500})
    session_id = res.json()["session_id"]
    await async_client.post(f"/api/v1/venues/intel_venue/sessions/{session_id}/start")

    # Ingest 3 entries at gate_A and 2 entries at gate_B
    for i in range(3):
        await async_client.post(
            f"/api/v1/venues/intel_venue/sessions/{session_id}/events",
            json={"event_type": "ENTRY", "gate_id": "gate_A", "event_id": f"a_{i}"},
        )
    for i in range(2):
        await async_client.post(
            f"/api/v1/venues/intel_venue/sessions/{session_id}/events",
            json={"event_type": "ENTRY", "gate_id": "gate_B", "event_id": f"b_{i}"},
        )

    # 1. Full intelligence snapshot
    intel_res = await async_client.get("/api/v1/venues/intel_venue/intelligence")
    assert intel_res.status_code == 200
    intel = intel_res.json()
    assert intel["venue_id"] == "intel_venue"
    assert intel["active_session_id"] == session_id
    assert intel["flow"]["cumulative_entries"] == 5
    assert intel["flow"]["cumulative_exits"] == 0

    # 2. Venue flow
    flow_res = await async_client.get("/api/v1/venues/intel_venue/intelligence/flow")
    assert flow_res.status_code == 200
    assert flow_res.json()["cumulative_entries"] == 5

    # 3. All gate flows
    gates_res = await async_client.get("/api/v1/venues/intel_venue/intelligence/flow/gates")
    assert gates_res.status_code == 200
    gate_data = gates_res.json()
    assert "gate_A" in gate_data
    assert "gate_B" in gate_data
    assert gate_data["gate_A"]["cumulative_entries"] == 3
    assert gate_data["gate_B"]["cumulative_entries"] == 2

    # 4. Single gate flow
    single_gate_res = await async_client.get(
        "/api/v1/venues/intel_venue/intelligence/flow/gates/gate_A"
    )
    assert single_gate_res.status_code == 200
    assert single_gate_res.json()["cumulative_entries"] == 3

    # 5. Occupancy
    occ_res = await async_client.get("/api/v1/venues/intel_venue/intelligence/occupancy")
    assert occ_res.status_code == 200
    assert occ_res.json()["venue_id"] == "intel_venue"

    # 6. Density
    density_res = await async_client.get("/api/v1/venues/intel_venue/intelligence/density")
    assert density_res.status_code == 200
    assert "density_level" in density_res.json()
    assert "congestion_level" in density_res.json()

    # 7. Dwell
    dwell_res = await async_client.get("/api/v1/venues/intel_venue/intelligence/dwell")
    assert dwell_res.status_code == 200
    assert "average_dwell" in dwell_res.json()


@pytest.mark.asyncio
async def test_intelligence_non_existent_venue(async_client):
    res = await async_client.get("/api/v1/venues/non_existent_venue/intelligence")
    assert res.status_code == 404
