"""Extracts 'O·O1 Anthropometrics' into onboarding_o1.json.

Source: v39sEng2.xlsx, sheet 'O·O1 Anthropometrics'.
'01_IMPORT_MANIFEST' order 71, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o1 <path-to-workbook>

THE AUTHORITY for ONB-001, the first of Layer 0's fourteen modules and the
first thing in this build that computes rather than records. Ten equations
and the twelve parameters they read:

    O1.1  V_f  = V_ref * (BW/70)^0.75
    O1.2  V_s  = V_s_ref * (BW/70)^0.85
    O1.3  BMI  = BW / height_m^2
    O1.4  WHtR = waist_cm / height_cm
    O1.5  kappa_IR = 1 / (1 + exp(-k_IR*(WHtR - 0.5)))
    O1.6  BMR  = Mifflin-St Jeor, by sex
    O1.7  CRP_mult = 1 + 0.3 * max(BMI - 25, 0)
    O1.8  f_u  = f_u_ref * (1 - 0.1 * max(BMI - 25, 0) / 25)
    O1.9  mu_centadip = 0.45*e_waist + 0.30*e_WHtR + 0.20*e_BMI
                        + 0.05*I(neck > 40cm)
    O1.10 e_waist = min(1, max(0, (waist - lo) / (hi - lo)))

EVERY VALUE IS EXTRACTED, NOT TYPED INTO PYTHON. The module that implements
these reads V_ref, V_s_ref, the allometric exponents, k_IR, the WHtR cutoff,
the sex-specific waist thresholds, the neck threshold and the BMI cutoff from
this file. None of them is a literal in a .py -- a physiological constant
inside code is a constant nobody can version, diff or trace to a source, and
this sheet gives a source for each.

TWO CAUTIONS THE SHEET RAISES ABOUT ITS OWN NUMBERS, kept in the extract
because they change what the values mean:

    V_ref=15L   "GENERIC PRIOR ONLY, not a universal physiological plasma
                 volume. Apparent volume is..."
    V_s_ref=30L "GENERIC PRIOR ONLY (see V_ref note). Use per-nutrient V_s,i
                 where characterised."

So O1.1 and O1.2 are priors to be replaced per nutrient, not compartment
volumes to be trusted. `check()` requires that wording to still be there.

BSA IS SPECIFIED SOMEWHERE ELSE AND DEFINED NOWHERE HERE. 'O · Onboarding
Canonical' and 'EQ · Canonical Build Rows' both give ONB-001 as including
`BSA=sqrt(height_cm*weight_kg/3600)` -- the Mosteller formula, identically
worded in both -- and 'P1 DataMap' says height is "Used for BMI, BSA
calculations". This sheet, which those rows name as the authority, has no
BSA equation, and no other equation in O1 consumes BSA. It is implemented
from the two consolidated rows and reported: see docs/parameter-gaps.md.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "O·O1 Anthropometrics"
FIRST_COL = 3
OUT = Path(__file__).parent / "onboarding_o1.json"

EQUATION_HEADER_ROW = 9
EQUATION_ROWS = range(10, 20)
EQUATION_LABELS = ["ID", "Name", "Formula", "Variables", "Units", "Value/Range"]

PARAMETER_HEADER_ROW = 24
PARAMETER_ROWS = range(25, 37)
PARAMETER_LABELS = ["Parameter", "Value", "Units", "Source", "Calibration",
                    "Notes"]

EXPECTED_EQUATIONS = 10
EXPECTED_PARAMETERS = 12

# The sheet writes parameter names for a reader. The engine needs keys, so
# the pairing is declared here rather than derived by slugifying -- a
# slugifier would silently rename a parameter the day the sheet reworded it,
# and the module reads these keys by name.
PARAMETER_KEYS: dict[str, str] = {
    "V_ref":                      "v_ref_l",
    "V_s_ref":                    "v_s_ref_l",
    "k_IR (sigmoid slope)":       "k_ir",
    "WHtR cutoff":                "whtr_cutoff",
    "Allometric exponent (V_f)":  "allometric_exponent_v_f",
    "Allometric exponent (V_s)":  "allometric_exponent_v_s",
    "Waist threshold (M) low":    "waist_threshold_male_low_cm",
    "Waist threshold (M) high":   "waist_threshold_male_high_cm",
    "Waist threshold (F) low":    "waist_threshold_female_low_cm",
    "Waist threshold (F) high":   "waist_threshold_female_high_cm",
    "Neck threshold (OSA)":       "neck_threshold_cm",
    "BMI obesity threshold":      "bmi_obesity_threshold",
}

# Stated by 'O · Onboarding Canonical' and 'EQ · Canonical Build Rows' in the
# same words, and by no equation on this sheet. Carried so the module has one
# place to read it from and the discrepancy stays attached to the value.
BSA_FROM_CONSOLIDATED_ROWS = {
    "equation_id": "ONB-001.BSA",
    "name": "Body surface area (Mosteller)",
    "formula": "BSA=sqrt(height_cm*weight_kg/3600)",
    "units": "m2",
    "declared_by": ["O · Onboarding Canonical", "EQ · Canonical Build Rows"],
    "absent_from_authority_sheet": True,
    "consumed_by": [],
}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _number(value, where: str) -> float | int:
    """A parameter value, as a number, whatever the cell's storage type.

    This sheet stores its parameter values as TEXT -- '15', not 15. The same
    thing cost this build 119 of 192 rows in the parameter registry, which
    loaded silently and short. Converting here, and refusing anything that is
    not a number, keeps that failure loud and local: an unparseable value
    stops the extract rather than reaching a physiological calculation as a
    string.
    """
    if isinstance(value, bool) or value is None:
        raise SystemExit(f"{where}: value is {value!r}, not a number.")
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        return int(text) if text.lstrip("-").isdigit() else float(text)
    except ValueError:
        raise SystemExit(
            f"{where}: value {value!r} is neither a number nor a string that "
            "parses as one.") from None


def _check_header(ws, row: int, labels: list[str]) -> None:
    for offset, expected in enumerate(labels):
        found = _text(_cell(ws, row, offset))
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {row} column {FIRST_COL + offset} reads "
                f"{found!r}, expected {expected!r}. The sheet moved; fix the "
                "offsets rather than the expectation.")


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]

    _check_header(ws, EQUATION_HEADER_ROW, EQUATION_LABELS)
    _check_header(ws, PARAMETER_HEADER_ROW, PARAMETER_LABELS)

    equations = []
    for row in EQUATION_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: equation row {row} has no id.")
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": _text(_cell(ws, row, 2)),
            "variables": _text(_cell(ws, row, 3)),
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
        })

    parameters = []
    for row in PARAMETER_ROWS:
        name = _text(_cell(ws, row, 0))
        if name is None:
            raise SystemExit(f"{SHEET}: parameter row {row} has no name.")
        key = PARAMETER_KEYS.get(name)
        if key is None:
            raise SystemExit(
                f"{SHEET}: parameter {name!r} at row {row} has no declared "
                "key. A new or reworded parameter must be given one by hand "
                "-- the module reads these by name.")
        parameters.append({
            "key": key,
            "name": name,
            "source_row": row,
            "value": _number(_cell(ws, row, 1), f"{SHEET} row {row} ({name})"),
            "units": _text(_cell(ws, row, 2)),
            "source": _text(_cell(ws, row, 3)),
            "calibration": _text(_cell(ws, row, 4)),
            "notes": _text(_cell(ws, row, 5)),
        })

    wb.close()
    return {"sheet": SHEET, "equations": equations, "parameters": parameters,
            "declared_elsewhere": [BSA_FROM_CONSOLIDATED_ROWS]}


def check(data: dict) -> None:
    equations, parameters = data["equations"], data["parameters"]

    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected_ids = [f"O1.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected_ids:
        raise SystemExit(f"{SHEET}: equations are not O1.1..O1.{EXPECTED_EQUATIONS}: "
                         f"{[e['equation_id'] for e in equations]}")
    for equation in equations:
        for field in ("name", "formula", "units", "value_range"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    if len(parameters) != EXPECTED_PARAMETERS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_PARAMETERS} parameters, "
                         f"got {len(parameters)}.")
    keys = [p["key"] for p in parameters]
    if sorted(keys) != sorted(PARAMETER_KEYS.values()):
        raise SystemExit(f"{SHEET}: parameter keys are {sorted(keys)}.")
    for parameter in parameters:
        if not isinstance(parameter["value"], (int, float)):
            raise SystemExit(
                f"{SHEET}: {parameter['name']} survived extraction as "
                f"{parameter['value']!r}, which is not a number.")
        if not parameter["source"]:
            raise SystemExit(
                f"{SHEET}: {parameter['name']} names no source. A constant "
                "with no provenance is a constant nobody can check.")

    by_key = {p["key"]: p for p in parameters}

    # The two volume references are priors, and the sheet says so on the
    # equation rows rather than in the parameter table. Losing that wording
    # would turn a placeholder into a physiological claim.
    for equation_id, key in (("O1.1", "v_ref_l"), ("O1.2", "v_s_ref_l")):
        variables = next(e for e in equations if e["equation_id"] == equation_id)["variables"]
        if "GENERIC PRIOR ONLY" not in variables:
            raise SystemExit(
                f"{SHEET}: {equation_id} no longer calls {key} a generic prior. "
                "Re-read it before removing this check -- the value is not a "
                "measured compartment volume.")

    # Relationships the sheet states twice, so they can be checked once.
    if by_key["waist_threshold_male_low_cm"]["value"] >= by_key["waist_threshold_male_high_cm"]["value"]:
        raise SystemExit(f"{SHEET}: male waist thresholds are not ordered.")
    if by_key["waist_threshold_female_low_cm"]["value"] >= by_key["waist_threshold_female_high_cm"]["value"]:
        raise SystemExit(f"{SHEET}: female waist thresholds are not ordered.")

    # O1.5 subtracts 0.5 inline; the parameter table calls that the WHtR
    # cutoff. If they ever diverge the formula is the one that runs, so the
    # divergence has to fail here.
    o1_5 = next(e for e in equations if e["equation_id"] == "O1.5")["formula"]
    cutoff = by_key["whtr_cutoff"]["value"]
    if f"- {cutoff}" not in o1_5 and f"-{cutoff}" not in o1_5:
        raise SystemExit(
            f"{SHEET}: O1.5 reads {o1_5!r} but the WHtR cutoff parameter is "
            f"{cutoff}. The formula and the parameter table disagree.")

    # O1.7 and O1.8 both subtract the BMI obesity threshold inline.
    threshold = by_key["bmi_obesity_threshold"]["value"]
    for equation_id in ("O1.7", "O1.8"):
        formula = next(e for e in equations if e["equation_id"] == equation_id)["formula"]
        if f"BMI - {threshold}" not in formula:
            raise SystemExit(
                f"{SHEET}: {equation_id} reads {formula!r}, which does not use "
                f"the declared BMI threshold {threshold}.")

    # O1.9's weights are a stated composite and must still be one.
    o1_9 = next(e for e in equations if e["equation_id"] == "O1.9")["formula"]
    weights = [0.45, 0.30, 0.20, 0.05]
    if abs(sum(weights) - 1.0) > 1e-12:
        raise SystemExit("O1.9's declared weights do not sum to 1.")
    for weight in weights:
        if f"{weight:g}*" not in o1_9.replace("0.30", "0.3").replace("0.20", "0.2"):
            raise SystemExit(f"{SHEET}: O1.9 no longer carries weight {weight}.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o1 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.name}")
    print(f"  {len(data['equations'])} equations O1.1..O1.10")
    print(f"  {len(data['parameters'])} parameters, every one with a source")
    print(f"  {len(data['declared_elsewhere'])} equation declared by the "
          "consolidated rows and absent here (BSA)")


if __name__ == "__main__":
    main()
