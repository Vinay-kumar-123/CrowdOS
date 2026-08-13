"""Tests for GateManager and GateConfig configuration."""
import pytest
from movement.config.gate_config import GateConfig, GateType, GateManager
from .conftest import make_gate, make_polygon_gate


# ─────────── GateConfig ───────────

def test_gate_config_line_zone_valid():
    gate = make_gate()
    assert gate.zone_type == "LINE"
    assert gate.gate_id == "gate_main"
    assert gate.camera_id == "cam_01"


def test_gate_config_polygon_zone_valid():
    gate = make_polygon_gate()
    assert gate.zone_type == "POLYGON"
    assert len(gate.zone_coordinates) == 4


def test_gate_type_defaults_to_bidirectional():
    gate = make_gate()
    assert gate.gate_type == GateType.BIDIRECTIONAL


def test_gate_type_entry_only():
    gate = make_gate(gate_type=GateType.ENTRY)
    assert gate.gate_type == GateType.ENTRY


def test_gate_type_exit_only():
    gate = make_gate(gate_type=GateType.EXIT)
    assert gate.gate_type == GateType.EXIT


def test_gate_config_to_dict_contains_required_fields():
    gate = make_gate()
    d = gate.to_dict()
    for key in ["gate_id", "gate_name", "camera_id", "gate_type", "zone_type"]:
        assert key in d, f"Missing key: {key}"


# ─────────── GateManager ───────────

def test_gate_manager_add_and_get():
    mgr = GateManager()
    gate = make_gate(gate_id="gate_1", camera_id="cam_01")
    mgr.add_gate(gate)
    found = mgr.get_gate("gate_1")
    assert found is not None
    assert found.gate_id == "gate_1"


def test_gate_manager_get_gates_for_camera():
    mgr = GateManager()
    mgr.add_gate(make_gate(gate_id="gate_A", camera_id="cam_01"))
    mgr.add_gate(make_gate(gate_id="gate_B", camera_id="cam_01"))
    mgr.add_gate(make_gate(gate_id="gate_C", camera_id="cam_02"))
    cam01_gates = mgr.get_gates_for_camera("cam_01")
    assert len(cam01_gates) == 2
    assert all(g.camera_id == "cam_01" for g in cam01_gates)


def test_gate_manager_no_gates_for_unknown_camera():
    mgr = GateManager()
    mgr.add_gate(make_gate(camera_id="cam_01"))
    gates = mgr.get_gates_for_camera("cam_unknown")
    assert gates == []


def test_gate_manager_remove_gate():
    mgr = GateManager()
    mgr.add_gate(make_gate(gate_id="gate_rm"))
    mgr.remove_gate("gate_rm")
    assert mgr.get_gate("gate_rm") is None


def test_gate_manager_list_all():
    mgr = GateManager()
    mgr.add_gate(make_gate(gate_id="g1", camera_id="c1"))
    mgr.add_gate(make_gate(gate_id="g2", camera_id="c2"))
    all_gates = mgr.list_all_gates()
    assert len(all_gates) == 2


def test_gate_manager_duplicate_gate_id_overwrites():
    mgr = GateManager()
    mgr.add_gate(make_gate(gate_id="gate_dup", gate_name="First", camera_id="cam_01"))
    mgr.add_gate(make_gate(gate_id="gate_dup", gate_name="Second", camera_id="cam_01"))
    gate = mgr.get_gate("gate_dup")
    assert gate.gate_name == "Second"
