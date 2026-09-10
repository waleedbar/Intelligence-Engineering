"""Every symbol an imported onboarding equation reads must resolve somewhere.

ONB-002 turned up three symbols the workbook names and never defines. They
were found by hand while reading, and a later audit found three more that the
same reading had walked past -- e_WHtR and e_BMI in O1.9 and f_u_ref in O1.8,
after ONB-001 had already been committed as complete.

Reading does not scale to twelve more O-sheets. This makes the check
mechanical, and pins the holes that are known so a new one fails loudly.
"""
import json
import pathlib

import pytest

from sahacore.data.onboarding_symbols import (
    KNOWN_BROKEN_ROUTINGS, KNOWN_UNRESOLVED, analyse, formula_parts,
)

DATA_DIR = pathlib.Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def result() -> dict:
    return analyse()


def test_no_symbol_is_unresolved_that_has_not_been_reported(result):
    """THE GUARD. A symbol nothing defines is a hole in the source, and an
    unreported one is a hole nobody has looked at. Adding to KNOWN_UNRESOLVED
    means reading the sheet and writing down what is missing -- which is the
    work this test exists to force."""
    surprises = sorted(set(result["unresolved"]) - set(KNOWN_UNRESOLVED))
    assert not surprises, (
        f"these symbols are used by an imported equation and defined nowhere, "
        f"and have not been reported: {surprises}")


def test_the_known_holes_are_still_holes(result):
    """If one of these is defined later, this test fails and the entry comes
    out of KNOWN_UNRESOLVED -- so the list cannot quietly go stale.

    Twelve of the eighteen are O6.8-O6.11: standard statistics stated with
    none of their inputs. They are listed one symbol at a time rather than as
    a single note, because each is separately missing.
    """
    assert set(result["unresolved"]) == {
        "e_WHtR", "e_BMI", "f_u_ref", "HR_Arem", "rho_pop", "sitting_hrs",
        # O6.8's Pearson-Aitken update
        "Sigma_12", "Sigma_22", "mu", "mu_2", "x2",
        # O6.9's liability threshold model
        "g", "e", "threshold", "sigma",
        # O6.10 and O6.11
        "FH_relevant", "eta_hi", "sigma2_base",
        # O7.1's 1,296 absent numbers, and O7.2's two runtime inputs
        "mu_pattern_i", "sigma2_pattern_i", "sigma2_prior", "sigma2_obs", "k"}
    assert result["unresolved"]["e_WHtR"] == ["O1.9"]
    assert result["unresolved"]["e_BMI"] == ["O1.9"]
    assert result["unresolved"]["f_u_ref"] == ["O1.8"]
    assert result["unresolved"]["HR_Arem"] == ["O2.4"]
    assert result["unresolved"]["rho_pop"] == ["O2.5"]
    assert result["unresolved"]["sitting_hrs"] == ["O2.8"]


def test_the_ui_contract_supplies_the_inputs_a_hand_written_set_used_to(result):
    """THE PAYOFF OF IMPORTING MANIFEST ORDER 70.

    DECLARED_INPUTS was a set written by hand, with a comment saying a parser
    could not tell a user's answer from any other name. 'O·Step-by-Step
    Questions' says exactly that for all 62 inputs, in a column called Maps
    To, and nine of the twenty-one hand-written entries were that list
    retyped.

    What remains hand-written is only the bridges -- an O-sheet's own
    spelling for something already accounted for -- and each carries its
    reason. That distinction matters: `SSB_serv_day` is declared to be
    `SSB_serv` per day by a person, and `f_u_ref` is NOT declared to be
    parameter #37 despite the same kind of resemblance.
    """
    from sahacore.data.onboarding_symbols import SHEET_SPELLINGS, ui_inputs

    collected = ui_inputs()
    assert len(collected) == 62
    for expected in ("BW", "age", "sex", "height_cm", "waist_cm", "sleep_hrs",
                     "drinks_wk", "smoke_status", "quit_time", "SSB_serv"):
        assert expected in collected, expected

    # A bridge must not silently duplicate what the UI already names.
    overlap = set(SHEET_SPELLINGS) & collected
    assert overlap == {"smoke_status"}, overlap
    for name, reason in SHEET_SPELLINGS.items():
        assert reason, name


def test_sitting_hrs_is_the_hole_only_the_ui_contract_could_find(result):
    """O2.8 says "sitting_hrs from Step 2 UI" and Step 2 does not collect it
    -- it asks how many hours the user SPENDS STANDING, which is a different
    quantity.

    It is not in SHEET_SPELLINGS, and the resemblance to `standing_hrs` is
    exactly why: bridging two names because they look alike is the mistake
    this repo refuses to make.

    Sitting time is real elsewhere in the engine -- state slot 185, and 'P1
    DataMap' row 53, fed by device sedentary detection. What is missing is a
    way to get it AT ONBOARDING, which is when O2.8 runs.
    """
    from sahacore.data.onboarding_symbols import SHEET_SPELLINGS, ui_inputs

    collected = ui_inputs()
    assert "standing_hrs" in collected
    assert "sitting_hrs" not in collected
    assert "sitting_hrs" not in SHEET_SPELLINGS
    assert result["unresolved"]["sitting_hrs"] == ["O2.8"]


# --- the second mechanical check: routings that go nowhere -----------------

def test_no_broken_routing_that_has_not_been_reported(result):
    """THE OTHER GUARD, and the reason it exists is worth keeping.

    An equation can define something real, declare which equations consume
    it, and be read by none of them. Every other check in this repo passes on
    that: the symbols resolve, the formula transcribes, the header matches.

    Two of these were found by hand, one per sheet, by writing a test that
    had to state a best and a worst case -- O3.1's quality weighting and
    O4.3's stress-practice credit. Finding the second the same way as the
    first is the signal that it needs a tool, because ten O-sheets remain.

    Running it over what was already imported immediately turned up a third
    in O2, which two passes of reading had not.
    """
    surprises = sorted({r["equation_id"] for r in result["broken_routings"]}
                       - set(KNOWN_BROKEN_ROUTINGS))
    assert not surprises, (
        f"these equations declare on-sheet consumers that do not read what "
        f"they define, and have not been reported: {surprises}")


def test_the_three_known_broken_routings_are_still_broken(result):
    """So the list cannot go stale if a sheet is corrected."""
    broken = {r["equation_id"]: r for r in result["broken_routings"]}
    assert set(broken) == {"O2.1", "O3.1", "O4.3"}

    # O3.1 routes to four and is read by none of the three on its own sheet;
    # O11 is unimported and so cannot be checked either way.
    assert broken["O3.1"]["consumers_that_do_not_read_it"] == [
        "O3.2", "O3.3", "O3.4"]
    assert broken["O4.3"]["consumers_that_do_not_read_it"] == [
        "O4.4", "O4.5", "O4.6", "O4.7"]
    # O2.1 is the mildest: two of its three consumers DO read MVPA_wk.
    assert broken["O2.1"]["consumers_that_do_not_read_it"] == ["O2.4"]


def test_a_routing_into_a_layer_is_not_checked(result):
    """The check can only see this workbook's equations. 'Layer C: Z3
    Inflammation rate' is a claim about code that does not exist yet, and
    reporting it as broken would fill the output with noise that cannot be
    acted on -- which is how a useful check becomes one nobody reads."""
    by_id = {e["equation_id"]: e for e in result["equations"]}
    assert by_id["O3.2"]["engine_target"] == "Layer C: Z3 Inflammation rate"
    assert "O3.2" not in {r["equation_id"] for r in result["broken_routings"]}


def test_every_hole_says_what_is_missing(result):
    for name in result["unresolved"]:
        assert KNOWN_UNRESOLVED[name].strip(), name


def test_f_u_ref_is_not_bridged_to_parameter_37_on_a_matching_range():
    """Parameter #37 f_unbound,i declares 0.01-1.0 and so does O1.8. That is
    suggestive and it is not evidence: the spellings differ, and matching a
    range is how a wrong alias gets made. Left unbridged deliberately, in the
    style of build_eq_param_fk.ALIASES, which requires a declared reason."""
    registry = json.loads(
        (DATA_DIR / "parameter_registry_192.json").read_text(encoding="utf-8"))
    thirty_seven = next(r for r in registry if r["param_no"] == 37)
    assert thirty_seven["symbol"] == "f_unbound,i"
    assert thirty_seven["default_or_range"] == "0.01-1.0"

    o1 = json.loads((DATA_DIR / "onboarding_o1.json").read_text(encoding="utf-8"))
    o1_8 = next(e for e in o1["equations"] if e["equation_id"] == "O1.8")
    assert o1_8["value_range"] == "0.01-1.0"
    assert "f_u_ref" in o1_8["variables"]
    assert "f_u_ref" not in {p["key"] for p in o1["parameters"]}

    nutrients = json.loads(
        (DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))
    assert not [k for k in nutrients[0] if "unbound" in k or k.startswith("f_u")]


def test_the_analyser_reads_formulas_the_way_the_sheet_writes_them():
    """The canary. Three things the workbook does that a naive tokeniser gets
    wrong, and getting any of them wrong makes the guard above vacuous."""
    # A version tag appended to a formula is not a symbol.
    defined, used = formula_parts("x = a + b  [v39l F-DM]")
    assert defined == {"x"} and used == {"a", "b"}

    # A unit glued to a number is not a symbol: 40cm must not yield 'cm'.
    _, used = formula_parts("y = 0.05*I(neck>40cm)")
    assert used == {"neck"}

    # A second definition on a second line is a definition, not a use.
    defined, used = formula_parts(
        "BMR_male = 10*BW + 5\nBMR_female = 10*BW - 161")
    assert defined == {"BMR_male", "BMR_female"}
    assert used == {"BW"}


def test_the_module_does_not_compute_the_indices_it_cannot_define():
    """O1.9's e_WHtR and e_BMI are arguments, not derived. Normalising BMI on
    a range this build chose would be inventing two thirds of a composite
    that feeds Layer C."""
    from sahacore.onboarding import anthropometrics as o1
    import inspect

    signature = inspect.signature(o1.central_adiposity_composite)
    assert "e_whtr" in signature.parameters
    assert "e_bmi" in signature.parameters
    assert not hasattr(o1, "whtr_exposure_index")
    assert not hasattr(o1, "bmi_exposure_index")


# --- two other things the audit turned up ---------------------------------

def test_every_built_onboarding_module_is_the_one_the_contract_names():
    """'O · Onboarding Canonical' names a sahacore.onboarding function per
    step. A module built under a different name would satisfy no contract."""
    import importlib

    contract = json.loads(
        (DATA_DIR / "onboarding_canonical.json").read_text(encoding="utf-8"))
    built, missing = [], []
    for step in contract["steps"]:
        try:
            importlib.import_module(step["python_function"])
            built.append(step["step_id"])
        except ModuleNotFoundError:
            missing.append(step["step_id"])

    assert built == ["ONB-001", "ONB-002", "ONB-003", "ONB-004",
                     "ONB-005", "ONB-006", "ONB-007", "ONB-008"], built
    assert len(missing) == 6
    # The two that are blocked must be among the unbuilt, not quietly written.
    blocked = [s["step_id"] for s in contract["steps"] if s["blocked_by"]]
    assert set(blocked) <= set(missing)


def test_no_data_file_is_loaded_by_nothing_beyond_the_known_six():
    """A JSON seed with no loader and no version is a file that looks used and
    is not.

    Six are left over from before this build's conventions -- Arthur's two
    signal files, and four state/pathway seeds written in an early session.
    A seventh would mean a new extractor shipped without its loader, which is
    the case this guards.
    """
    data = DATA_DIR
    loaders = "\n".join(p.read_text(encoding="utf-8")
                        for p in data.glob("load_*.py"))
    versions = (data / "record_registry_versions.py").read_text(encoding="utf-8")
    orphans = sorted(p.name for p in data.glob("*.json")
                     if p.name not in loaders and p.name not in versions)
    assert orphans == [
        "arthur_signals_raw.json",
        "arthur_signals_validated.json",
        "damage_clusters_12.json",
        "lifestyle_states_24.json",
        "mechanistic_states_9.json",
        "tvmcd_pathways_15.json",
    ], orphans
