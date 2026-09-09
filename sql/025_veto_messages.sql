-- The 24 message templates the VETO library renders.
--
-- Source: v39sEng2.xlsx, sheet 'MERGE·VETO FDA Messages' -- "24 templates.
-- Upload to veto_messages." '01_IMPORT_MANIFEST' order 175, role REGISTRY.
--
-- WHAT THIS CLOSES. engine_internal.veto_drug_nutrient has carried a
-- message_id on all 339 rules since migration 014, pointing at nothing. The
-- correspondence is exact -- 24 templates, 24 distinct ids in use, none used
-- without a template and none written without a user -- so the column
-- becomes a foreign key rather than a string that resembles one.
--
-- The templates are what a person actually reads when an interaction fires.
-- The wording is regulated and is transcribed verbatim: none of them gives a
-- dose, and all but one hand off to a prescriber or pharmacist.

CREATE TABLE IF NOT EXISTS engine_internal.veto_message (
    message_id    TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,

    severity      TEXT NOT NULL,
    action        TEXT NOT NULL,
    title         TEXT NOT NULL,
    -- Contains {nutrient} and {medication} placeholders. Verbatim.
    body_template TEXT NOT NULL,
    cta           TEXT,

    CONSTRAINT veto_message_id_is_canonical CHECK (message_id ~ '^MSG-[A-Z]+-[A-Z]+$'),
    CONSTRAINT veto_message_severity_is_known CHECK (
        severity IN ('CRITICAL', 'HIGH', 'MODERATE', 'LOW')
    ),
    CONSTRAINT veto_message_action_is_known CHECK (
        action IN ('AVOID', 'MONITOR', 'NOTE', 'PAUSE', 'SEPARATE', 'STABLE', 'SUPPORT')
    )
);

COMMENT ON TABLE engine_internal.veto_message IS
    'The 24 templates engine_internal.veto_drug_nutrient.message_id points '
    'at. Regulated wording, transcribed verbatim -- no template gives a dose.';

-- The reference the VETO library has been carrying unresolved.
ALTER TABLE engine_internal.veto_drug_nutrient
    DROP CONSTRAINT IF EXISTS veto_drug_nutrient_message_id_fkey;
ALTER TABLE engine_internal.veto_drug_nutrient
    ADD CONSTRAINT veto_drug_nutrient_message_id_fkey
    FOREIGN KEY (message_id) REFERENCES engine_internal.veto_message (message_id);

-- Each rule with the message a person would actually see. Layer H renders
-- from this; nothing downstream should be composing safety wording itself.
CREATE OR REPLACE VIEW engine_internal.veto_rule_message AS
    SELECT v.rule_id,
           v.drug_or_class,
           v.nutrient_or_food,
           v.severity,
           v.bandit_action,
           m.action,
           m.title,
           m.body_template,
           m.cta
    FROM engine_internal.veto_drug_nutrient v
    JOIN engine_internal.veto_message m ON m.message_id = v.message_id
    ORDER BY v.rule_id;

-- CRITICAL templates that name no prescriber, pharmacist, clinician or
-- doctor. One row today, and it is a finding rather than a tolerance:
-- MSG-CRITICAL-STABLE renders VETO-DN-0265 (insulin x carbohydrate) and
-- VETO-DN-0267 (sulfonylureas x carbohydrate), whose own action column reads
-- "STABLE PATTERN — discuss with prescriber". The rule mandates a referral;
-- the message drops it. See docs/parameter-gaps.md.
CREATE OR REPLACE VIEW engine_internal.critical_message_without_referral AS
    SELECT m.message_id,
           m.body_template,
           m.cta,
           count(v.rule_id) AS rules_rendering_it
    FROM engine_internal.veto_message m
    LEFT JOIN engine_internal.veto_drug_nutrient v ON v.message_id = m.message_id
    WHERE m.severity = 'CRITICAL'
      AND lower(coalesce(m.body_template, '') || ' ' || coalesce(m.cta, ''))
          !~ 'prescriber|pharmacist|clinician|doctor'
    GROUP BY m.message_id, m.body_template, m.cta;
