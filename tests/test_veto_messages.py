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


def test_all_seven_critical_templates_hand_off_to_a_professional(by_id):
    """Prescriber or pharmacist, in the body or the call to action. Six
    arrive that way from the workbook; the seventh is the authorised
    override below."""
    from sahacore.data.build_veto_messages import REFERS_TO

    critical = [m for m in by_id.values() if m["severity"] == "CRITICAL"]
    assert len(critical) == 7
    for m in critical:
        text = f"{m['body_template']} {m['cta'] or ''}".lower()
        assert any(who in text for who in REFERS_TO), m["message_id"]


# --- the one authorised change to a regulated message ----------------------

def test_the_critical_template_that_referred_the_reader_to_nobody(by_id, veto):
    """THE FINDING, AND THE DECISION THAT CLOSED IT.

    MSG-CRITICAL-STABLE read, in the workbook: "Safety first — with
    {medication}, keeping your {nutrient} intake steady day to day helps
    things stay consistent — aim for a similar amount rather than big
    swings." CTA "Learn more". No prescriber, no pharmacist -- the only
    CRITICAL template that named nobody.

    Two CRITICAL rules render it: VETO-DN-0265, insulin x carbohydrate
    intake, and VETO-DN-0267, sulfonylureas x carbohydrate intake. Both
    rules' OWN action column reads "STABLE PATTERN — discuss with
    prescriber". The rule mandated a referral and the message dropped it --
    on two interactions where a carbohydrate swing is a hypoglycaemia risk.

    Reported to Dr Ali Charanek on 2026-09-10 and answered on 2026-09-11:
    "Use the hardest safety rule that include consulting health provider in
    the mes[sage]". So one sentence is appended -- and the workbook's own
    text travels beside it, because a regulated message that differs from its
    source has to be able to say so.
    """
    from sahacore.data.build_veto_messages import (
        AUTHORISED_OVERRIDES, DECIDED_BY, DECIDED_ON)

    m = by_id["MSG-CRITICAL-STABLE"]
    assert m["severity"] == "CRITICAL"
    assert "prescriber" in m["body_template"].lower()

    # The rules that made this necessary, unchanged.
    renders = [r for r in veto if r["message_id"] == "MSG-CRITICAL-STABLE"]
    assert {r["rule_id"] for r in renders} == {"VETO-DN-0265", "VETO-DN-0267"}
    for r in renders:
        assert r["severity"] == "CRITICAL"
        assert "discuss with prescriber" in r["action"].lower()

    # The change is an APPEND: not one word of the workbook's clinical
    # wording is altered, which is the difference between carrying out a
    # decision and rewriting a regulated message.
    override = AUTHORISED_OVERRIDES["MSG-CRITICAL-STABLE"]
    assert m["source_body_template"] + override["append"] == m["body_template"]
    assert "prescriber" not in m["source_body_template"].lower()

    # And it is attributed, because an unattributed edit to safety wording is
    # indistinguishable from a transcription error.
    assert m["overridden_field"] == "body_template"
    assert m["overridden_by"] == DECIDED_BY == "Dr Ali Charanek"
    assert m["overridden_on"] == DECIDED_ON
    assert "VETO-DN-0265" in m["override_reason"]


def test_the_appended_sentence_is_borrowed_rather_than_written(by_id):
    """It is MSG-CRITICAL-AVOID's own closing sentence, so the referral
    arrives in language this library already uses rather than in wording
    composed here.

    The one difference is the capital Y: in MSG-CRITICAL-AVOID the sentence
    follows an em dash, and here it starts one. That is the whole extent of
    the editing.
    """
    from sahacore.data.build_veto_messages import AUTHORISED_OVERRIDES

    override = AUTHORISED_OVERRIDES["MSG-CRITICAL-STABLE"]
    donor = by_id[override["wording_from"]]
    borrowed = override["append"].strip()

    assert borrowed.lower() in donor["body_template"].lower()
    assert borrowed not in donor["body_template"]   # only the capital differs
    assert borrowed[1:] in donor["body_template"]


def test_every_other_template_is_the_workbook_verbatim(messages):
    """One override, and it is the only row that differs from its source."""
    overridden = [m for m in messages if m["overridden_field"] is not None]
    assert [m["message_id"] for m in overridden] == ["MSG-CRITICAL-STABLE"]

    for m in messages:
        if m["overridden_field"] is None:
            # Nothing half-recorded: a row either was changed and says
            # everything about it, or was not changed at all.
            assert m["source_body_template"] is None
            assert m["overridden_by"] is None
            assert m["overridden_on"] is None
            assert m["override_reason"] is None


def test_the_moderate_template_that_still_refers_the_reader_to_nobody(by_id, veto):
    """DELIBERATELY NOT OVERRIDDEN, AND STILL REPORTED.

    MSG-MODERATE-STABLE names no professional either. Its single rule --
    VETO-DN-0107, diuretic + ACE inhibitor x potassium -- has the action
    "BALANCE" and mandates no referral. The decision above applies where a
    rule demands one, and this is the case where none does, so the workbook's
    wording stands. Stretching an authorisation past what it authorised is
    how a declared override becomes an undeclared editorial habit.
    """
    from sahacore.data.build_veto_messages import STILL_WITHOUT_REFERRAL, REFERS_TO

    assert STILL_WITHOUT_REFERRAL == {"MSG-MODERATE-STABLE"}
    m = by_id["MSG-MODERATE-STABLE"]
    assert m["severity"] == "MODERATE"
    assert m["overridden_field"] is None
    text = f"{m['body_template']} {m['cta'] or ''}".lower()
    assert not any(who in text for who in REFERS_TO)

    renders = [r for r in veto if r["message_id"] == "MSG-MODERATE-STABLE"]
    assert {r["rule_id"] for r in renders} == {"VETO-DN-0107"}
    assert "balance" in renders[0]["action"].lower()
    assert "discuss with prescriber" not in renders[0]["action"].lower()


def test_the_builder_refuses_a_new_referral_less_critical_template(messages):
    """One authorised exception; a second must stop the build rather than
    quietly join it -- that decision is the clinical owner's."""
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    victim = next(r for r in rows
                  if r["severity"] == "CRITICAL" and r["message_id"] != "MSG-CRITICAL-STABLE")
    victim["body_template"] = "Safety first — something happened."
    victim["cta"] = "Learn more"
    with pytest.raises(SystemExit, match="naming no professional"):
        check(rows)


def test_the_builder_refuses_to_write_rows_the_override_never_reached(messages):
    """check() runs on the rows that get written. If the override layer is
    ever dropped from main(), the transcribed text would ship silently --
    which is the same defect the override exists to close, arriving from the
    other direction."""
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    stale = next(r for r in rows if r["message_id"] == "MSG-CRITICAL-STABLE")
    stale["body_template"] = stale["source_body_template"]
    stale["source_body_template"] = None
    stale["overridden_field"] = None
    with pytest.raises(SystemExit, match="naming no professional"):
        check(rows)


def test_the_builder_refuses_an_override_that_lost_its_attribution(messages):
    """A changed message whose row does not say who changed it is
    indistinguishable from a transcription error."""
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    unsigned = next(r for r in rows if r["message_id"] == "MSG-CRITICAL-STABLE")
    unsigned["overridden_by"] = None
    with pytest.raises(SystemExit, match="no attribution"):
        check(rows)


def test_the_builder_refuses_a_template_no_rule_uses(messages):
    from sahacore.data.build_veto_messages import check

    rows = [dict(m) for m in messages]
    rows[0]["message_id"] = "MSG-UNUSED-TEMPLATE"
    with pytest.raises(SystemExit, match="do not exist|no VETO rule uses"):
        check(rows)
