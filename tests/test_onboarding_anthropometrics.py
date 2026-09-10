"""ONB-001, the first module in this build that computes.

Authority: 'O·O1 Anthropometrics' -- manifest order 71.
QA required by 'O · Onboarding Canonical': "unit tests for BMI/BMR".

Two kinds of test here. The first checks the arithmetic against values
worked by hand from the sheet's formulas. The second checks the module
against the sheet's own PARAMETERS table and Value/Range column, so an
implementation that drifts from its source fails even when its arithmetic is
self-consistent.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.onboarding import anthropometrics as o1
from sahacore.onboarding.parameters import load_o1

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def params() -> o1.O1Parameters:
    return load_o1()


@pytest.fixture(scope="module")
def sheet() -> dict:
    return json.loads((DATA_DIR / "onboarding_o1.json").read_text(encoding="utf-8"))


# --- the parameters come from the sheet, not from the code ----------------

def test_no_parameter_value_is_written_into_the_module(params, sheet):
    """The package's standing rule. Every value in O1Parameters must be the
    one the registry holds -- if the module carried its own copy this would
    still pass by luck, so the next test closes that."""
    declared = {p["key"]: p["value"] for p in sheet["parameters"]}
    for key, value in declared.items():
        assert getattr(params, key) == value, key


def test_the_module_declares_exactly_the_sheets_parameters(params, sheet):
    """O1Parameters is built by keyword from the registry, so a parameter
    added to the sheet without a field here fails at construction and a field
    here with no row in the sheet fails too."""
    declared = {p["key"] for p in sheet["parameters"]}
    fields = set(o1.O1Parameters.__dataclass_fields__)
    assert fields == declared


def test_the_sourced_values_are_the_ones_the_literature_gives(params):
    """Spot-checks against the sheet's cited sources, so a transcription slip
    in the extract shows up as a wrong constant rather than a passing test.

    IDF/WHO harmonized 2009 waist thresholds; Ashwell et al. 2012's universal
    WHtR cutoff; West et al. 1997's 3/4 metabolic scaling exponent.
    """
    assert params.waist_threshold_male_low_cm == 94
    assert params.waist_threshold_male_high_cm == 102
    assert params.waist_threshold_female_low_cm == 80
    assert params.waist_threshold_female_high_cm == 88
    assert params.whtr_cutoff == 0.5
    assert params.allometric_exponent_v_f == 0.75
    assert params.bmi_obesity_threshold == 25


# --- O1.3 BMI and O1.6 BMR: the QA the canonical sheet asks for -----------

def test_bmi_against_hand_worked_values():
    assert o1.body_mass_index(70, 175) == pytest.approx(22.857142857, rel=1e-9)
    assert o1.body_mass_index(100, 180) == pytest.approx(30.864197531, rel=1e-9)
    # A square person: 100 kg at 100 cm is 100 kg/m^2 exactly.
    assert o1.body_mass_index(100, 100) == pytest.approx(100.0)


def test_bmr_is_mifflin_st_jeor_and_the_sexes_differ_only_by_intercept():
    """O1.6. 10*BW + 6.25*height_cm - 5*age, then +5 for male and -161 for
    female -- so the difference is exactly 166 kcal/day at every input."""
    male = o1.basal_metabolic_rate(70, 175, 30, o1.MALE)
    female = o1.basal_metabolic_rate(70, 175, 30, o1.FEMALE)
    assert male == pytest.approx(10 * 70 + 6.25 * 175 - 5 * 30 + 5)
    assert male == pytest.approx(1648.75)
    assert female == pytest.approx(1482.75)
    assert male - female == pytest.approx(166.0)

    for weight, height, age in ((55, 160, 22), (95, 190, 61), (70, 175, 30)):
        assert (o1.basal_metabolic_rate(weight, height, age, o1.MALE)
                - o1.basal_metabolic_rate(weight, height, age, o1.FEMALE)
                == pytest.approx(166.0))


def test_bmr_falls_with_age_and_rises_with_mass():
    assert (o1.basal_metabolic_rate(70, 175, 60, o1.MALE)
            < o1.basal_metabolic_rate(70, 175, 30, o1.MALE))
    assert (o1.basal_metabolic_rate(90, 175, 30, o1.MALE)
            > o1.basal_metabolic_rate(70, 175, 30, o1.MALE))


def test_an_unknown_sex_is_refused_rather_than_defaulted(params):
    """Defaulting to one sex would produce a plausible number for the wrong
    person, which is worse than an error."""
    with pytest.raises(ValueError):
        o1.basal_metabolic_rate(70, 175, 30, "unspecified")
    with pytest.raises(ValueError):
        params.waist_thresholds("unspecified")


# --- the rest of the equations --------------------------------------------

def test_o1_1_and_o1_2_are_allometric_and_agree_at_the_reference(params):
    """At 70 kg both return their reference exactly, whatever the exponent --
    which is what makes 70 the reference rather than a fitted constant."""
    assert o1.fast_compartment_volume(70, params) == pytest.approx(params.v_ref_l)
    assert o1.slow_compartment_volume(70, params) == pytest.approx(params.v_s_ref_l)
    # Sub-linear scaling: double the mass, less than double the volume.
    assert o1.fast_compartment_volume(140, params) < 2 * params.v_ref_l
    assert o1.slow_compartment_volume(140, params) < 2 * params.v_s_ref_l


def test_a_characterised_nutrient_can_override_the_generic_prior(params):
    """The sheet: 'Use per-nutrient V_s,i where characterised.' The default
    is the generic prior; a caller with a real value supplies it."""
    assert o1.slow_compartment_volume(70, params, v_s_ref_l=12.0) == pytest.approx(12.0)
    assert o1.fast_compartment_volume(70, params, v_ref_l=8.0) == pytest.approx(8.0)


def test_o1_5_is_a_logistic_centred_on_the_whtr_cutoff(params):
    """kappa_IR = 1/(1+exp(-k*(WHtR - cutoff))). Exactly 0.5 at the cutoff,
    monotone, and strictly inside (0, 1) everywhere."""
    assert o1.insulin_resistance_index(params.whtr_cutoff, params) == pytest.approx(0.5)
    assert (o1.insulin_resistance_index(0.4, params)
            < o1.insulin_resistance_index(0.5, params)
            < o1.insulin_resistance_index(0.6, params))
    for whtr in (0.0, 0.3, 0.5, 0.8, 2.0):
        value = o1.insulin_resistance_index(whtr, params)
        assert 0.0 < value < 1.0


def test_o1_7_does_not_amplify_below_the_obesity_threshold(params):
    """CRP_mult = 1 + 0.3*max(BMI-25, 0). The max() is the whole point: a
    lean user gets exactly 1.0, not a fraction below it."""
    assert o1.crp_multiplier(20, params) == 1.0
    assert o1.crp_multiplier(25, params) == 1.0
    assert o1.crp_multiplier(30, params) == pytest.approx(1 + 0.3 * 5)


def test_o1_7_stays_inside_the_sheets_declared_range(params, sheet):
    """The sheet gives CRP_mult a range of 1.0-8.5, which is reached at
    BMI = 50 -- the top of O1.3's own declared range. The two ranges agree,
    and that is worth pinning: it means the sheet's ranges were derived
    together rather than written independently.
    """
    declared = next(e for e in sheet["equations"] if e["equation_id"] == "O1.7")
    assert declared["value_range"] == "1.0-8.5"
    assert o1.crp_multiplier(50, params) == pytest.approx(8.5)

    bmi_range = next(e for e in sheet["equations"] if e["equation_id"] == "O1.3")
    assert bmi_range["value_range"] == "15-50"


def test_o1_8_reduces_the_unbound_fraction_and_never_inverts_it(params):
    """f_u = f_u_ref * (1 - 0.1*max(BMI-25,0)/25). At the top of the BMI
    range the multiplier is 0.9, so f_u stays positive and below its
    reference -- a bound worth checking, since a negative unbound fraction
    would be meaningless downstream in Layer B."""
    assert o1.unbound_fraction(0.5, 25, params) == pytest.approx(0.5)
    assert o1.unbound_fraction(0.5, 20, params) == pytest.approx(0.5)
    assert o1.unbound_fraction(0.5, 50, params) == pytest.approx(0.5 * 0.9)
    for bmi in (15, 25, 35, 50):
        value = o1.unbound_fraction(0.5, bmi, params)
        assert 0.0 < value <= 0.5


def test_o1_10_clamps_the_waist_index_at_both_ends(params):
    """e_waist is [0, 1] by construction, and the thresholds differ by sex --
    88 cm is 1.0 for a woman and 0.0 for a man."""
    assert o1.waist_exposure_index(80, o1.FEMALE, params) == 0.0
    assert o1.waist_exposure_index(88, o1.FEMALE, params) == 1.0
    assert o1.waist_exposure_index(120, o1.FEMALE, params) == 1.0
    assert o1.waist_exposure_index(60, o1.FEMALE, params) == 0.0

    assert o1.waist_exposure_index(94, o1.MALE, params) == 0.0
    assert o1.waist_exposure_index(102, o1.MALE, params) == 1.0
    assert o1.waist_exposure_index(98, o1.MALE, params) == pytest.approx(0.5)

    assert o1.waist_exposure_index(88, o1.FEMALE, params) == 1.0
    assert o1.waist_exposure_index(88, o1.MALE, params) == 0.0


def test_o1_9_weights_sum_to_one_and_the_composite_is_bounded(params):
    """0.45 + 0.30 + 0.20 + 0.05 = 1, so a composite of normalised indices is
    itself in [0, 1] -- which is the range the sheet declares for it."""
    assert sum(o1._CENTADIP_WEIGHTS.values()) == pytest.approx(1.0)
    assert o1.central_adiposity_composite(0, 0, 0, 30, params) == 0.0
    assert o1.central_adiposity_composite(1, 1, 1, 45, params) == pytest.approx(1.0)
    assert o1.central_adiposity_composite(1, 1, 1, 30, params) == pytest.approx(0.95)
    for value in (o1.central_adiposity_composite(0.3, 0.7, 0.5, 41, params),
                  o1.central_adiposity_composite(0.9, 0.1, 0.4, 38, params)):
        assert 0.0 <= value <= 1.0


def test_the_neck_indicator_is_a_step_at_the_stop_bang_threshold(params):
    """40 cm, from STOP-Bang screening. Strictly greater, as the sheet
    writes I(neck > 40cm) -- so 40 itself does not fire."""
    assert params.neck_threshold_cm == 40
    below = o1.central_adiposity_composite(0, 0, 0, 40, params)
    above = o1.central_adiposity_composite(0, 0, 0, 40.1, params)
    assert below == 0.0
    assert above == pytest.approx(0.05)


# --- BSA, the equation the authority sheet does not carry -----------------

def test_bsa_is_mosteller_and_is_recorded_as_declared_elsewhere(sheet):
    """'O · Onboarding Canonical' and 'EQ · Canonical Build Rows' both give
    BSA=sqrt(height_cm*weight_kg/3600) for ONB-001. 'O·O1 Anthropometrics',
    which those rows name as the authority, has no BSA equation and nothing
    in O1 consumes it. Implemented from the two consolidated rows; the gap
    is recorded rather than papered over.
    """
    declared = sheet["declared_elsewhere"]
    assert len(declared) == 1
    bsa = declared[0]
    assert bsa["absent_from_authority_sheet"] is True
    assert bsa["consumed_by"] == []
    assert len(bsa["declared_by"]) == 2
    assert "O1" not in [e["equation_id"] for e in sheet["equations"]]

    # 1.9 m^2 for a 70 kg / 175 cm adult is the textbook Mosteller result.
    assert o1.body_surface_area(70, 175) == pytest.approx(
        math.sqrt(175 * 70 / 3600), rel=1e-12)
    assert o1.body_surface_area(70, 175) == pytest.approx(1.8447, abs=1e-4)


# --- the equations, against the sheet --------------------------------------

def test_all_ten_equations_are_present_with_formulas_and_ranges(sheet):
    equations = sheet["equations"]
    assert [e["equation_id"] for e in equations] == [f"O1.{n}" for n in range(1, 11)]
    for equation in equations:
        assert equation["formula"]
        assert equation["units"]
        assert equation["value_range"]


def test_the_volume_priors_still_say_they_are_priors(sheet):
    """The two cautions are the difference between a placeholder and a
    physiological claim. If this wording ever leaves the sheet, the values
    have to be re-read before they are trusted."""
    by_id = {e["equation_id"]: e for e in sheet["equations"]}
    assert "GENERIC PRIOR ONLY" in by_id["O1.1"]["variables"]
    assert "GENERIC PRIOR ONLY" in by_id["O1.2"]["variables"]
    assert "per-nutrient V_s,i" in by_id["O1.2"]["variables"]


# --- the convention itself, enforced --------------------------------------

def test_every_sheet_parameter_is_read_from_the_registry_not_typed_in(sheet):
    """The package's standing rule, checked by reading the source rather than
    by running it.

    A value that is a LITERAL in the module would still make every test above
    pass, because the arithmetic would be identical. What distinguishes the
    two is provenance: `p.whtr_cutoff` traces to 'Ashwell et al. 2012' through
    the registry, and `0.5` traces to nothing.

    So this asserts that each of the twelve keys is actually dereferenced off
    a parameter object somewhere in the module. It deliberately does NOT scan
    for bare numeric literals: the module has plenty, and they belong there --
    the 70 kg allometric reference, Mifflin-St Jeor's coefficients, the 0.3
    in O1.7, O1.9's composite weights and Mosteller's 3600 are written into
    the equations by the sheet itself. Changing one of those is changing the
    equation, not retuning a parameter, and a scan that could not tell the
    difference would have to be either wrong or ignored.
    """
    import ast

    source = (Path(__file__).parent.parent / "sahacore" / "onboarding"
              / "anthropometrics.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    dereferenced = {node.attr for node in ast.walk(tree)
                    if isinstance(node, ast.Attribute)}

    for parameter in sheet["parameters"]:
        assert parameter["key"] in dereferenced, (
            f"{parameter['key']} is declared in the registry with source "
            f"{parameter['source']!r} but is never read from a parameter "
            "object in anthropometrics.py")


def test_the_module_holds_no_constant_named_after_a_registry_parameter(sheet):
    """The other half: a module-level constant shadowing a registry key would
    be a second copy of a sourced value, and the two could drift apart."""
    import ast

    source = (Path(__file__).parent.parent / "sahacore" / "onboarding"
              / "anthropometrics.py").read_text(encoding="utf-8")
    module_level = {
        target.id
        for node in ast.parse(source).body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    keys = {p["key"] for p in sheet["parameters"]}
    assert not (module_level & keys), module_level & keys
