-- The onboarding questionnaire: 12 steps, every field, every answer option.
--
-- Source: v39sEng2.xlsx, sheet 'O·Step-by-Step Questions'.
-- '01_IMPORT_MANIFEST' order 70, role ONBOARDING, import YES, backend Yes.
--
-- The sheet calls itself "Exact questions and answer options from SahaPlusAI
-- Figma UI", so this is the contract for what Layer 0 is actually given. Its
-- 'Maps To' column names the variable each answer becomes and which O-module
-- consumes it -- which makes it the authority for what a user input IS.
--
-- IT IS MANIFEST ORDER 70, BEFORE O1 AT 71. Four O-modules were built before
-- it. Nothing failed, because each O-sheet names its own inputs in a
-- Variables column; what was missing was any way to CHECK them against what
-- the UI collects. sahacore.data.onboarding_symbols carried a hand-written
-- DECLARED_INPUTS set for exactly that reason.
--
-- ANSWER OPTIONS ARE STORED TWICE, AND DELIBERATELY. The raw cell is kept
-- verbatim in answer_options_text, and the split choices in a child table
-- when the cell lists choices at all. Many cells describe a control rather
-- than an enumeration -- 'Numeric entry', 'Slider 0-8+ hours', 'Multi-select
-- checkboxes', 'Checkbox (Yes/No)' -- and inventing options for those would
-- be inventing the UI, so is_choice records which is which and the child
-- table stays empty for the rest.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_step_question_step (
    step_number INTEGER PRIMARY KEY,
    source_row  INTEGER NOT NULL UNIQUE,
    title       TEXT NOT NULL,

    CONSTRAINT onboarding_step_question_step_is_one_of_twelve
        CHECK (step_number BETWEEN 1 AND 12)
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_step_question (
    source_row          INTEGER PRIMARY KEY,
    step_number         INTEGER NOT NULL
        REFERENCES engine_internal.onboarding_step_question_step(step_number),
    category            TEXT NOT NULL,
    question            TEXT NOT NULL,

    -- The Answer Options cell verbatim, whether or not it lists choices.
    answer_options_text TEXT NOT NULL,
    is_choice           BOOLEAN NOT NULL,

    -- 'SSB_serv' from 'SSB_serv → O5, O11'.
    variable            TEXT NOT NULL,

    -- Step 8 marks its reverse-scored PSS-10 items here as well as in the
    -- question text. That is the workbook's THIRD statement of the set; the
    -- other two are on 'O·O4 Stress Index'.
    reverse_scored      BOOLEAN NOT NULL,

    required            TEXT NOT NULL,

    CONSTRAINT onboarding_step_question_required_is_known
        CHECK (required IN ('Mandatory', 'Optional', 'Conditional'))
);

-- Where one answer goes. A question may feed several modules: 'sex → O1, O5'.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_step_question_target (
    source_row INTEGER NOT NULL
        REFERENCES engine_internal.onboarding_step_question(source_row),
    target     TEXT NOT NULL,

    PRIMARY KEY (source_row, target)
);

-- The listed choices, in the order the UI offers them. Empty for a question
-- whose Answer Options cell describes a control rather than an enumeration.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_step_question_option (
    source_row       INTEGER NOT NULL
        REFERENCES engine_internal.onboarding_step_question(source_row),
    ordinal_position INTEGER NOT NULL,
    option           TEXT NOT NULL,

    PRIMARY KEY (source_row, ordinal_position),
    CONSTRAINT onboarding_step_question_option_position_is_positive
        CHECK (ordinal_position >= 1)
);
