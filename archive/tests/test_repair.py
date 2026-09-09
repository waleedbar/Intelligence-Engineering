"""Tests for sahacore/engine/repair.py (Layer C, equation C6).

Source: v39sEng2.xlsx, sheet 'P1 Core Equations', row C6 ("*** CORRECTED
***" competitive MM repair), Vm/Km data from sheet 'O·O11 Damage State
Init', rows 10-24 (15 TVMCD pathways Z1-Z15).
"""
import json
from pathlib import Path

import pytest

from sahacore.engine.repair import competitive_repair_rate, competitive_repair_rates

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def pathways() -> list[dict]:
    return json.loads((DATA_DIR / "tvmcd_pathways_15.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vm_km(pathways) -> tuple[dict, dict]:
    vm = {p["pathway_id"]: p["vm"] for p in pathways}
    km = {p["pathway_id"]: p["km"] for p in pathways}
    return vm, km


def test_repair_rate_is_zero_when_own_damage_is_zero(vm_km):
    vm, km = vm_km
    z_values = {pid: 5.0 for pid in vm}
    z_values["Z1"] = 0.0
    assert competitive_repair_rate("Z1", z_values, vm, km) == 0.0


def test_single_pathway_reduces_to_standard_michaelis_menten():
    """With only one pathway active, competitive_sum=0 and the formula
    collapses to plain MM: repair_k = Vm*Z_k/(Km+Z_k)."""
    vm = {"Z1": 0.1}
    km = {"Z1": 0.3}
    for z_k in (0.0, 1.0, 5.0, 50.0):
        z_values = {"Z1": z_k}
        expected = vm["Z1"] * z_k / (km["Z1"] + z_k) if z_k > 0 else 0.0
        assert competitive_repair_rate("Z1", z_values, vm, km) == pytest.approx(expected)


def test_repair_rate_strictly_decreases_as_a_competing_pathway_rises(vm_km):
    """Competitive inhibition: raising any other pathway's Z_j (holding Z_k
    fixed) must strictly lower repair_k, since it only adds to the
    denominator's competitive_sum term."""
    vm, km = vm_km
    base = {pid: 1.0 for pid in vm}
    rates = []
    for z_other in (0.0, 1.0, 5.0, 20.0, 100.0):
        z_values = dict(base)
        z_values["Z2"] = z_other
        rates.append(competitive_repair_rate("Z1", z_values, vm, km))
    assert rates == sorted(rates, reverse=True)
    assert len(set(rates)) == len(rates)


def test_repair_rate_increases_with_own_damage_holding_others_fixed(vm_km):
    vm, km = vm_km
    others = {pid: 1.0 for pid in vm if pid != "Z1"}
    rates = []
    for z_k in (0.0, 1.0, 5.0, 20.0, 100.0):
        z_values = dict(others)
        z_values["Z1"] = z_k
        rates.append(competitive_repair_rate("Z1", z_values, vm, km))
    assert rates == sorted(rates)


def test_repair_rate_is_bounded_by_vm(vm_km):
    """repair_k = Vm*Z_k/(denom), and denom >= Z_k always (since the Km*(...)
    term is >= 0), so repair_k <= Vm for any nonnegative damage stocks."""
    vm, km = vm_km
    z_values = {pid: 1000.0 for pid in vm}
    for pid in vm:
        rate = competitive_repair_rate(pid, z_values, vm, km)
        assert 0.0 <= rate <= vm[pid]


def test_competitive_repair_rates_matches_per_pathway_calls(vm_km):
    vm, km = vm_km
    z_values = {pid: float(i + 1) for i, pid in enumerate(vm)}
    rates = competitive_repair_rates(z_values, vm, km)
    for pid in vm:
        assert rates[pid] == pytest.approx(competitive_repair_rate(pid, z_values, vm, km))


def test_all_15_real_tvmcd_pathways_produce_valid_bounded_rates(pathways, vm_km):
    vm, km = vm_km
    assert len(pathways) == 15
    assert set(vm) == {f"Z{i}" for i in range(1, 16)}
    z_values = {pid: 1.0 for pid in vm}
    rates = competitive_repair_rates(z_values, vm, km)
    assert len(rates) == 15
    for pid, rate in rates.items():
        assert 0.0 <= rate <= vm[pid], f"{pid}: rate={rate} vm={vm[pid]}"


def test_all_vm_and_km_values_are_strictly_positive(pathways):
    for p in pathways:
        assert p["vm"] > 0.0, p["pathway_id"]
        assert p["km"] > 0.0, p["pathway_id"]


def test_pathway_ids_are_exactly_z1_to_z15(pathways):
    ids = {p["pathway_id"] for p in pathways}
    assert ids == {f"Z{i}" for i in range(1, 16)}
