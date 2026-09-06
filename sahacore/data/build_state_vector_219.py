"""Assembles the canonical 219-state vector definition from its four source
registries (nutrients, damage clusters, lifestyle, mechanistic subsystems)
and validates it against the authoritative block map before writing
state_vector_219.json.

Source of truth for the block map: Dr. Ali's v39sEng2 workbook, sheet
'★ State Vector v33 (219)', section 1 ("BLOCK MAP"), cross-checked against
sheet 'P1 Variables 219' (per-item lifestyle registry, rows 183-209) and
'K3 · Mechanistic Modules' (N1-N5 equations). Nothing in this file invents
values -- every field traces to one of those two sheets or to the already
-verified sahacore/data/*.json seed files.

    python -m sahacore.data.build_state_vector_219
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
OUT_FILE = DATA_DIR / "state_vector_219.json"

# (block, first_index, last_index, is_nonlinear) -- verbatim from the
# '1 - BLOCK MAP' table. is_nonlinear reproduces the sheet's "Filter class"
# column (conditionally linear -> False, nonlinear -> True); the resulting
# totals (164 linear / 55 nonlinear) match the sheet's stated totals exactly.
BLOCK_MAP = [
    ("C_fast",    1,   81,  False),
    ("C_slow",    82,  162, False),
    ("xi_hi",     163, 174, True),
    ("xi_lo",     175, 186, True),
    ("lifestyle", 187, 210, True),
    ("N1",        211, 213, True),
    ("N2",        214, 214, False),
    ("N3",        215, 216, True),
    ("N4",        217, 218, True),
    ("N5",        219, 219, False),
]


def _block_for_index(idx: int) -> tuple[str, bool]:
    for block, lo, hi, is_nonlinear in BLOCK_MAP:
        if lo <= idx <= hi:
            return block, is_nonlinear
    raise ValueError(f"index {idx} is not covered by any block")


def build() -> list[dict]:
    nutrients = json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))
    nutrients = sorted(nutrients, key=lambda r: r["num"])
    clusters = json.loads((DATA_DIR / "damage_clusters_12.json").read_text(encoding="utf-8"))
    lifestyle = json.loads((DATA_DIR / "lifestyle_states_24.json").read_text(encoding="utf-8"))
    mechanistic = json.loads((DATA_DIR / "mechanistic_states_9.json").read_text(encoding="utf-8"))

    states: list[dict] = []

    for i, nut in enumerate(nutrients):
        block, is_nonlinear = _block_for_index(i + 1)
        states.append({
            "idx": i + 1, "block": block, "symbol": nut["id"], "name": nut["name"],
            "unit": nut["unit"], "is_nonlinear": is_nonlinear,
            "nutrient_code": nut["id"], "cluster_id": None, "side": None,
        })
    for i, nut in enumerate(nutrients):
        idx = 82 + i
        block, is_nonlinear = _block_for_index(idx)
        states.append({
            "idx": idx, "block": block, "symbol": nut["id"], "name": nut["name"],
            "unit": nut["unit"], "is_nonlinear": is_nonlinear,
            "nutrient_code": nut["id"], "cluster_id": None, "side": None,
        })

    for side, start in (("hi", 163), ("lo", 175)):
        for i, cluster in enumerate(clusters):
            idx = start + i
            block, is_nonlinear = _block_for_index(idx)
            states.append({
                "idx": idx, "block": block,
                "symbol": f"xi_{side}_{cluster['id']}",
                "name": f"{cluster['name']} — {'high' if side == 'hi' else 'low'}-side damage (log coordinate)",
                "unit": "log(AU)", "is_nonlinear": is_nonlinear,
                "nutrient_code": None, "cluster_id": cluster["id"], "side": side,
            })

    for item in lifestyle:
        idx = item["canonical_index"]
        block, is_nonlinear = _block_for_index(idx)
        states.append({
            "idx": idx, "block": block, "symbol": item["symbol"], "name": item["name"],
            "unit": item["unit"], "is_nonlinear": is_nonlinear,
            "nutrient_code": None, "cluster_id": None, "side": None,
        })

    for item in mechanistic:
        idx = item["canonical_index"]
        block, is_nonlinear = _block_for_index(idx)
        assert block == item["block"], f"index {idx}: block map says {block}, seed says {item['block']}"
        states.append({
            "idx": idx, "block": block, "symbol": item["symbol"], "name": item["name"],
            "unit": None, "is_nonlinear": is_nonlinear,
            "nutrient_code": None, "cluster_id": None, "side": None,
        })

    states.sort(key=lambda s: s["idx"])
    _validate(states)
    return states


def _validate(states: list[dict]) -> None:
    assert len(states) == 219, f"expected 219 states, got {len(states)}"
    assert [s["idx"] for s in states] == list(range(1, 220)), "indices must be 1..219 with no gaps/duplicates"

    linear = sum(1 for s in states if not s["is_nonlinear"])
    nonlinear = sum(1 for s in states if s["is_nonlinear"])
    assert linear == 164, f"expected 164 linear states, got {linear}"
    assert nonlinear == 55, f"expected 55 nonlinear states, got {nonlinear}"

    for block, lo, hi, _ in BLOCK_MAP:
        block_states = [s for s in states if s["block"] == block]
        assert len(block_states) == hi - lo + 1, f"block {block}: expected {hi - lo + 1} states, got {len(block_states)}"
        assert all(lo <= s["idx"] <= hi for s in block_states), f"block {block}: index out of its declared range"


if __name__ == "__main__":
    states = build()
    OUT_FILE.write_text(json.dumps(states, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(states)} states to {OUT_FILE}")
