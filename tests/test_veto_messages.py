"""The 24 templates the VETO library renders, and one safety finding.

Source: v39sEng2.xlsx, sheet 'MERGE·VETO FDA Messages',
'01_IMPORT_MANIFEST' order 175.

These are what a person actually reads when a drug-nutrient interaction
fires. The wording is regulated, so it is transcribed rather than
paraphrased, and the tests below check the posture the library is built on:
flag and defer, never advise.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def messages() -> list[dict]:
    return json.loads((DATA_DIR / "veto_messages.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def veto() -> list[dict]:
    return json.loads((DATA_DIR / "veto_drug_nutrient_339.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(messages) -> dict[str, dict]:
    return {m["message_id"]: m for m in messages}


# --- the reference that was dangling ---------------------------------------

def test_the_correspondence_with_the_veto_library_is_exact(messages, veto):
    """339 rules have carried a message_id since migration 014, pointing at
    nothing. 24 templates, 24 distinct ids in use, none used without a
    template and none written without a user -- which is what lets the column
    be a real foreign key rather than a string that resembles one."""
    ids = {m["message_id"] for m in messages}
    used = {r["message_id"] for r in veto}
    assert len(ids) == 24
    assert used == ids


def test_every_rule_can_render_something(veto, by_id):
    for r in veto:
        assert r["message_id"] in by_id, r["rule_id"]


# --- the posture: flag and defer, never advise -----------------------------

def test_no_template_gives_a_dose(messages):
    """The constraint the whole library exists to respect. A template that
    named an amount would be dosing guidance rendered by a wellness app."""
    import re
    for m in messages:
        body = m["body_template"]
        assert not re.search(r"\b\d+\s*(mg|mcg|µg|g|IU|units?)\b", body, re.I), (
            f"{m['message_id']} names a dose: {body}")


def test_the_critical_templates_are_the_seven_expected(messages):
    critical = {m["message_id"] for m in messages if m["severity"] == "CRITICAL"}
    assert len(critical) == 7
    assert "MSG-CRITICAL-AVOID" in critical
    assert "MSG-CRITICAL-PAUSE" in critical


def test_six_of_the_seven_critical_templates_hand_off_to_a_professional(by_id):
    """Prescriber or pharmacist, in the body or the call to action."""
    from sahacore.data.build_veto_messages import REFERS_TO, CRITICAL_WITHOUT_REFERRAL

    referring = 0
    for m in by_id.values():
        if m["severity"] != "CRITICAL":
            continue
        text = f"{m['body_template']} {m['cta'] or ''}".lower()
        if any(who in text for who in REFERS_TO):
            referring += 1
    assert referring == 7 - len(CRITICAL_WITHOUT_REFERRAL) == 6


def test_the_one_critical_template_that_refers_the_reader_to_nobody(by_id, veto):
    """A finding, pinned rather than tolerated.

    MSG-CRITICAL-STABLE reads: "Safety first — with {medication}, keeping
    your {nutrient} intake steady day to day helps things stay consistent —
    aim for a similar amount rather than big swings." Its CTA is "Learn
    more". No prescriber, no pharmacist.

    Two CRITICAL rules render it: VETO-DN-0265, insulin x carbohydrate
    intake, and VETO-DN-0267, sulfonylureas x carbohydrate intake. Both
    rules' OWN action column reads "STABLE PATTERN — discuss with
    prescriber". The rule mandates a referral and the message drops it -- on
    two interactions where a carbohydrate swing is a hypoglycaemia risk.

    This build does not rewrite it. Regulated wording is not an engineering
    decision. It is reported, here and in docs/parameter-gaps.md.
    """
    from sahacore.data.build_veto_messages import CRITICAL_WITHOUT_REFERRAL

    assert CRITICAL_WITHOUT_REFERRAL == {"MSG-CRITICAL-STABLE"}
    m = by_id["MSG-CRITICAL-STABLE"]
    assert m["severity"] == "CRITICAL"
    assert "prescriber" not in f"{m['body_template']} {m['cta']}".lower()

    renders = [r for r in veto if r["message_id"] == "MSG-CRITICAL-STABLE"]
    assert {r["rule_id"] for r in renders} == {"VETO-DN-0265", "VETO-DN-0267"}
    for r in renders:
        assert r["severity"] == "CRITICAL"
        assert "discuss with prescriber" in r["action"].lower()


def test_the_builder_refuses_a_new_referral_less_critical_template(messages):
    """One known exception; a second must stop the build rather than join it."""
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    victim = next(r for r in rows
                  if r["severity"] == "CRITICAL" and r["message_id"] != "MSG-CRITICAL-STABLE")
    victim["body_template"] = "Safety first — something happened."
    victim["cta"] = "Learn more"
    with pytest.raises(SystemExit, match="naming no professional"):
        check(rows)


def test_the_builder_refuses_a_template_no_rule_uses(messages):
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    rows[0]["message_id"] = "MSG-UNUSED-TEMPLATE"
    with pytest.raises(SystemExit, match="do not exist|no VETO rule uses"):
        check(rows)
