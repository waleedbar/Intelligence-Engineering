-- An authorised change to a regulated message, recorded as a change.
--
-- MSG-CRITICAL-STABLE named no professional. Both rules that render it --
-- VETO-DN-0265 (insulin x carbohydrate intake) and VETO-DN-0267
-- (sulfonylureas x carbohydrate intake) -- are CRITICAL hypoglycaemia risks
-- whose own action column reads "STABLE PATTERN — discuss with prescriber".
-- The rule mandated a referral and the message dropped it.
--
-- Reported to the sheet's clinical owner, Dr Ali Charanek, on 2026-09-10 and
-- answered on 2026-09-11: "Use the hardest safety rule that include
-- consulting health provider in the mes[sage]". One sentence is appended,
-- borrowed verbatim from MSG-CRITICAL-AVOID; no existing clinical wording is
-- altered and no dosing guidance is added.
--
-- WHY THE COLUMNS RATHER THAN JUST THE NEW TEXT. A regulated message that
-- differs from its source must be able to say so to anyone who asks -- an
-- auditor, the workbook's author, or a later reader of this build who cannot
-- tell transcription from editing by looking. So the row carries the
-- workbook's own text beside the changed one, and who decided the change and
-- when. A row with a NULL overridden_field is a pure transcription.
--
-- Migrations are append-only: 025_veto_messages.sql created this table and is
-- never edited, so the columns arrive here.

ALTER TABLE engine_internal.veto_message
    ADD COLUMN IF NOT EXISTS source_body_template TEXT,
    ADD COLUMN IF NOT EXISTS overridden_field     TEXT,
    ADD COLUMN IF NOT EXISTS overridden_by        TEXT,
    ADD COLUMN IF NOT EXISTS overridden_on        DATE,
    ADD COLUMN IF NOT EXISTS override_reason      TEXT;

COMMENT ON COLUMN engine_internal.veto_message.source_body_template IS
    'The workbook''s own body_template, kept when this build changed it. '
    'NULL means body_template is the workbook''s text unaltered.';
COMMENT ON COLUMN engine_internal.veto_message.overridden_by IS
    'The clinical owner who authorised the change. This build does not '
    'rewrite regulated wording on its own initiative.';

-- All five columns travel together or none of them do. A changed row with no
-- attribution is the exact failure these columns exist to prevent: text that
-- differs from the workbook and cannot say why.
ALTER TABLE engine_internal.veto_message
    DROP CONSTRAINT IF EXISTS veto_message_override_is_complete;
ALTER TABLE engine_internal.veto_message
    ADD CONSTRAINT veto_message_override_is_complete CHECK (
        (overridden_field IS NULL
         AND source_body_template IS NULL
         AND overridden_by IS NULL
         AND overridden_on IS NULL
         AND override_reason IS NULL)
        OR
        (overridden_field IS NOT NULL
         AND source_body_template IS NOT NULL
         AND overridden_by IS NOT NULL
         AND overridden_on IS NOT NULL
         AND override_reason IS NOT NULL)
    );

-- Only body_template has ever been overridden, and a column name that does
-- not exist would make source_body_template meaningless.
ALTER TABLE engine_internal.veto_message
    DROP CONSTRAINT IF EXISTS veto_message_override_field_is_known;
ALTER TABLE engine_internal.veto_message
    ADD CONSTRAINT veto_message_override_field_is_known CHECK (
        overridden_field IS NULL OR overridden_field = 'body_template'
    );

-- An override that changes nothing is a no-op that looks like a decision.
ALTER TABLE engine_internal.veto_message
    DROP CONSTRAINT IF EXISTS veto_message_override_actually_changed_it;
ALTER TABLE engine_internal.veto_message
    ADD CONSTRAINT veto_message_override_actually_changed_it CHECK (
        source_body_template IS NULL OR source_body_template <> body_template
    );

-- What a person reads, and what the workbook says, side by side. One row
-- today. Empty is the healthy state: it means the workbook needs no help.
CREATE OR REPLACE VIEW engine_internal.veto_message_override AS
    SELECT message_id,
           severity,
           overridden_field,
           source_body_template AS workbook_text,
           body_template        AS rendered_text,
           overridden_by,
           overridden_on,
           override_reason
    FROM engine_internal.veto_message
    WHERE overridden_field IS NOT NULL
    ORDER BY message_id;

-- 025 created this view when MSG-CRITICAL-STABLE was in it. It is now empty
-- of CRITICAL rows and holds MSG-MODERATE-STABLE, which is MODERATE and
-- whose only rule -- VETO-DN-0107, diuretic + ACE inhibitor x potassium --
-- has the action "BALANCE" and mandates no referral. So the view is widened
-- past CRITICAL rather than dropped: the question "which messages name
-- nobody" stays answerable, and its answer stops being empty-by-definition.
DROP VIEW IF EXISTS engine_internal.critical_message_without_referral;
CREATE VIEW engine_internal.message_without_referral AS
    SELECT m.message_id,
           m.severity,
           m.body_template,
           m.cta,
           count(v.rule_id) AS rules_rendering_it
    FROM engine_internal.veto_message m
    LEFT JOIN engine_internal.veto_drug_nutrient v ON v.message_id = m.message_id
    WHERE lower(coalesce(m.body_template, '') || ' ' || coalesce(m.cta, ''))
          !~ 'prescriber|pharmacist|clinician|doctor'
    GROUP BY m.message_id, m.severity, m.body_template, m.cta
    ORDER BY m.message_id;

COMMENT ON VIEW engine_internal.message_without_referral IS
    'Templates naming no prescriber, pharmacist, clinician or doctor. No '
    'CRITICAL row may appear here -- that is a release-blocking finding.';
