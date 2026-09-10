"""Extracts 'P1 Activities 50' into activities_50.json.

Source: v39sEng2.xlsx, sheet 'P1 Activities 50'.
'01_IMPORT_MANIFEST' order 46, role CORE_ENGINE, import YES, backend Yes.

    python -m sahacore.data.build_activities_50 <path-to-workbook>

The MET catalogue ONB-002 needs. 'O · Onboarding Canonical' names this sheet
as one of ONB-002's two authorities, and its formula
`MET_min_week = Sigma_bouts MET_a * minutes_a` reads MET_a from here.

    "MET values from 2024 Compendium of Physical Activities (Herrmann et al.
     2024). Cluster impacts from exercise physiology literature."

FIFTY ACTIVITIES, SIX CLUSTER COLUMNS, TWELVE PROMISED. The sheet's own
banner reads "50-Activity Catalog — MET Values + 12-Cluster Impact Weights"
and its section heading "COMPLETE ACTIVITY CATALOG WITH CLUSTER IMPACTS".
It carries C1 Membrane, C2 Glucose, C3 Protein, C4 Electro, C5 Inflamm and
C6 Oxidative. There is no C7 through C12 -- not blank cells, no columns at
all: every row ends at column 15.

So an activity's impact can be computed for half the clusters and not the
other half. That is loaded as it stands, with `clusters_declared` and
`clusters_present` recorded, rather than padded with zeros -- a zero here
would read as "this activity does not affect methylation", which is a
physiological claim the sheet does not make. See docs/parameter-gaps.md.

CLUSTER IMPACTS ARE SIGNED. Sitting quietly carries -0.05 on C1 and -0.1 on
C2; walking carries +0.05 and +0.08. So these are directional effects on
damage, not magnitudes, and `check()` requires both signs to still be
present -- a catalogue that had lost its negatives would silently turn
sedentary behaviour into a benefit.

VALUES ARE STORED AS TEXT throughout, as in 'O·O1 Anthropometrics'. Converted
on the way in, and anything that will not parse stops the extract.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "P1 Activities 50"
FIRST_COL = 3
OUT = Path(__file__).parent / "activities_50.json"

HEADER_ROW = 10
DATA_ROWS = range(11, 61)
FIXED_LABELS = ["#", "ID", "Name", "MET", "Intensity", "Typical\nDuration",
                "Unit"]
CLUSTER_LABELS = ["C1\nMembrane", "C2\nGlucose", "C3\nProtein", "C4\nElectro",
                  "C5\nInflamm", "C6\nOxidative"]

BANNER_ROW = 6
EXPECTED_ACTIVITIES = 50

# What the banner promises against what the columns deliver.
CLUSTERS_DECLARED = 12
CLUSTERS_PRESENT = 6

# The sheet's own intensity vocabulary. A new word is a new band, and bands
# feed O2.6's moderate/vigorous split, so the extract stops rather than
# importing one it has not seen.
INTENSITIES = {"Sedentary", "Light", "Moderate", "Vigorous"}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _number(value, where: str) -> float | int:
    if isinstance(value, bool) or value is None:
        raise SystemExit(f"{where}: value is {value!r}, not a number.")
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    try:
        return int(text) if text.lstrip("-").isdigit() else float(text)
    except ValueError:
        raise SystemExit(f"{where}: {value!r} does not parse as a number.") from None


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]

    labels = FIXED_LABELS + CLUSTER_LABELS
    for offset, expected in enumerate(labels):
        found = _cell(ws, HEADER_ROW, offset)
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {HEADER_ROW} column {FIRST_COL + offset} "
                f"reads {found!r}, expected {expected!r}.")

    # A seventh cluster column would mean the sheet had been completed, which
    # changes what this registry can answer.
    beyond = _cell(ws, HEADER_ROW, len(labels))
    if beyond is not None:
        raise SystemExit(
            f"{SHEET}: a column now follows {CLUSTER_LABELS[-1]!r} -- "
            f"{beyond!r}. The catalogue may have grown past six clusters; "
            "re-read it before changing CLUSTERS_PRESENT.")

    cluster_ids = [label.split("\n")[0] for label in CLUSTER_LABELS]

    activities = []
    for row in DATA_ROWS:
        activity_id = _text(_cell(ws, row, 1))
        if activity_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no activity id.")
        where = f"{SHEET} row {row} ({activity_id})"
        activities.append({
            "activity_id": activity_id,
            "source_row": row,
            "number": _number(_cell(ws, row, 0), where + " #"),
            "name": _text(_cell(ws, row, 2)),
            "met": _number(_cell(ws, row, 3), where + " MET"),
            "intensity": _text(_cell(ws, row, 4)),
            "typical_duration": _number(_cell(ws, row, 5), where + " duration"),
            "duration_unit": _text(_cell(ws, row, 6)),
            "cluster_impact": {
                cluster_ids[i]: _number(_cell(ws, row, 7 + i),
                                        f"{where} {cluster_ids[i]}")
                for i in range(len(cluster_ids))
            },
        })

    banner = _text(ws.cell(row=BANNER_ROW, column=FIRST_COL).value)
    wb.close()
    return {
        "sheet": SHEET,
        "banner": banner,
        "clusters_declared": CLUSTERS_DECLARED,
        "clusters_present": CLUSTERS_PRESENT,
        "cluster_ids": cluster_ids,
        "activities": activities,
        "outside_compendium_bands": _outside_compendium_bands(activities),
    }


def _outside_compendium_bands(activities: list[dict]) -> list[dict]:
    """Rows whose intensity label disagrees with the Compendium's own numeric
    boundaries -- sedentary <= 1.5, light 1.6-2.9, moderate 3.0-5.9, vigorous
    >= 6.0.

    Recorded, not corrected, and not treated as an error. The sheet sources
    its MET VALUES from the Compendium and does not say its labels follow the
    Compendium's bands, so a disagreement is a thing to report to the sheet's
    author rather than a defect in the import. It matters because O2.6 splits
    activity into moderate and vigorous by these labels while using 4.5 and
    7.5 -- the midpoints of the Compendium's bands, not of this catalogue's.
    """
    def compendium_band(met: float) -> str:
        if met <= 1.5:
            return "Sedentary"
        if met < 3.0:
            return "Light"
        if met < 6.0:
            return "Moderate"
        return "Vigorous"

    return [
        {"activity_id": a["activity_id"], "met": a["met"],
         "sheet_intensity": a["intensity"],
         "compendium_intensity": compendium_band(a["met"])}
        for a in activities
        if compendium_band(a["met"]) != a["intensity"]
    ]


def check(data: dict) -> None:
    activities = data["activities"]
    if len(activities) != EXPECTED_ACTIVITIES:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_ACTIVITIES} activities, "
                         f"got {len(activities)}.")

    ids = [a["activity_id"] for a in activities]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{SHEET}: duplicate activity ids.")
    if [a["number"] for a in activities] != list(range(1, EXPECTED_ACTIVITIES + 1)):
        raise SystemExit(f"{SHEET}: activities are not numbered 1..{EXPECTED_ACTIVITIES}.")

    for activity in activities:
        if activity["met"] <= 0:
            raise SystemExit(
                f"{SHEET}: {activity['activity_id']} has MET {activity['met']}. "
                "A MET is a multiple of resting metabolic rate and cannot be "
                "zero or negative.")
        if activity["intensity"] not in INTENSITIES:
            raise SystemExit(
                f"{SHEET}: {activity['activity_id']} has intensity "
                f"{activity['intensity']!r}, not one of {sorted(INTENSITIES)}.")
        if activity["duration_unit"] != "min":
            raise SystemExit(
                f"{SHEET}: {activity['activity_id']} has duration unit "
                f"{activity['duration_unit']!r}. MET-minutes assumes minutes.")
        if len(activity["cluster_impact"]) != CLUSTERS_PRESENT:
            raise SystemExit(
                f"{SHEET}: {activity['activity_id']} has "
                f"{len(activity['cluster_impact'])} cluster impacts.")

    # Sleeping is the resting anchor of the Compendium: MET = 1 by definition.
    sleep = next((a for a in activities if a["activity_id"] == "sleep"), None)
    if sleep is None or sleep["met"] != 1:
        raise SystemExit(
            f"{SHEET}: 'sleep' should anchor the scale at MET 1; got "
            f"{sleep['met'] if sleep else 'no row'}.")

    # The bands must be weakly ordered in MET: nothing in a higher band may
    # sit below the floor of a lower one. This is an internal consistency
    # check, and deliberately not the Compendium's numeric boundaries -- the
    # sheet cites the Compendium for its MET VALUES, not for its intensity
    # labels, so holding the labels to 3.0 and 6.0 would be imposing a rule
    # the source does not claim. Where the two disagree is recorded below
    # instead, as an observation.
    order = ["Sedentary", "Light", "Moderate", "Vigorous"]
    floors = {}
    for band in order:
        mets = [a["met"] for a in activities if a["intensity"] == band]
        if not mets:
            raise SystemExit(f"{SHEET}: no activity is labelled {band}.")
        floors[band] = (min(mets), max(mets))
    for lower, higher in zip(order, order[1:]):
        if floors[higher][0] < floors[lower][0]:
            raise SystemExit(
                f"{SHEET}: {higher} starts at MET {floors[higher][0]} which is "
                f"below {lower}'s floor of {floors[lower][0]}. The bands are "
                "not ordered.")

    # Signed impacts. Losing the negatives would turn sitting into a benefit.
    values = [v for a in activities for v in a["cluster_impact"].values()]
    if not any(v < 0 for v in values):
        raise SystemExit(f"{SHEET}: no negative cluster impacts survived the "
                         "extract; the catalogue is signed.")
    if not any(v > 0 for v in values):
        raise SystemExit(f"{SHEET}: no positive cluster impacts survived.")

    outside = data["outside_compendium_bands"]
    if not isinstance(outside, list):
        raise SystemExit(f"{SHEET}: outside_compendium_bands is not a list.")

    if str(data["clusters_declared"]) not in (data["banner"] or ""):
        raise SystemExit(
            f"{SHEET}: the banner no longer promises "
            f"{data['clusters_declared']} clusters: {data['banner']!r}. "
            "Re-read it before changing the recorded gap.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_activities_50 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    bands: dict[str, int] = {}
    for activity in data["activities"]:
        bands[activity["intensity"]] = bands.get(activity["intensity"], 0) + 1
    mets = [a["met"] for a in data["activities"]]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['activities'])} activities, MET {min(mets)}-{max(mets)}")
    print("  intensity: " + ", ".join(f"{k} {v}" for k, v in sorted(bands.items())))
    print(f"  cluster impacts: {data['clusters_present']} of "
          f"{data['clusters_declared']} promised by the banner")
    print(f"  {len(data['outside_compendium_bands'])} rows whose intensity "
          "label disagrees with the Compendium's numeric bands")


if __name__ == "__main__":
    main()
