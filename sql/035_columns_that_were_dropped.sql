-- Three columns of three sheets that earlier extractors never read.
--
-- WHY THIS IS A NEW MIGRATION RATHER THAN AN EDIT. sql/032, 033 and 034 are
-- already applied. sahacore.migrate records a migration by FILENAME, so a
-- database that has run one will never run it again -- editing the file
-- would change what a fresh build creates and leave every existing database
-- silently short of the column. Migrations are append-only for that reason.
--
-- WHAT WAS MISSING AND HOW IT HID. Each extractor verified the header labels
-- it was given and said nothing about the columns it was not, so a sheet
-- with seven columns and an extractor declaring six agreed perfectly:
--
--   'O·O1 Anthropometrics'      Engine Target
--   'O·O2 MVPA Prior'           Engine Target
--   'TVMCD · 15 Pathways Build' Uncertainty treatment, Validation scenario
--   'Action_Space' info table   VOI score, State/output affected,
--                               Safety/VETO, Expiration, Policy class,
--                               Exploration, State uncertainty, Evaluation
--   'Action_Space' phase table  Sample Threshold, Convergence Criterion,
--                               Safety Notes
--
-- Engine Target is the wiring from Layer 0 into the rest of the engine --
-- "Layer C: Z3 Inflammation rate", "Layer B (B1): V_f". Safety/VETO is a
-- safety position. Sample Threshold and Convergence Criterion are what let a
-- rollout phase advance. None of them is decoration.
--
-- sahacore/data/sheet_header.py now refuses a header wider than the labels
-- an extractor declares, and tests/test_extractors_take_whole_tables.py
-- makes using it non-optional.

ALTER TABLE engine_internal.onboarding_o1_equation
    ADD COLUMN IF NOT EXISTS engine_target TEXT;

ALTER TABLE engine_internal.onboarding_o2_equation
    ADD COLUMN IF NOT EXISTS engine_target TEXT;

ALTER TABLE engine_internal.tvmcd_pathway
    ADD COLUMN IF NOT EXISTS uncertainty_treatment TEXT,
    ADD COLUMN IF NOT EXISTS validation_scenario   TEXT;

ALTER TABLE engine_internal.action_space_info
    ADD COLUMN IF NOT EXISTS voi_score                TEXT,
    ADD COLUMN IF NOT EXISTS state_or_output_affected TEXT,
    ADD COLUMN IF NOT EXISTS safety_veto              TEXT,
    ADD COLUMN IF NOT EXISTS expiration               TEXT,
    ADD COLUMN IF NOT EXISTS policy_class             TEXT,
    ADD COLUMN IF NOT EXISTS exploration              TEXT,
    ADD COLUMN IF NOT EXISTS state_uncertainty        TEXT,
    ADD COLUMN IF NOT EXISTS evaluation               TEXT;

ALTER TABLE engine_internal.action_space_phase
    ADD COLUMN IF NOT EXISTS sample_threshold      TEXT,
    ADD COLUMN IF NOT EXISTS convergence_criterion TEXT,
    ADD COLUMN IF NOT EXISTS safety_notes          TEXT;

-- Every information action must state its safety position. The column is
-- filled by the loader from the sheet; this makes an empty one impossible to
-- ship, now that the value is actually being read.
ALTER TABLE engine_internal.action_space_info
    ADD CONSTRAINT action_space_info_states_its_safety_position
    CHECK (safety_veto IS NOT NULL) NOT VALID;
