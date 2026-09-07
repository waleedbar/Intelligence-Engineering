-- Layer C's damage.py (equation C1) uses nutrients.s_hi_log / s_lo_log as
-- the divisor "scale" in the log-ratio deviation r_hi,i / r_lo,i. A zero
-- value would divide by zero; a negative value would flip the deviation's
-- sign (an excess deviation would read as a deficiency, or vice versa).
-- All 81 real nutrients use 0.25 for both fields (source: 'P1 Nutrients
-- 81') -- this migration encodes that invariant as a database guarantee
-- rather than trusting every future registry update to preserve it,
-- matching every other numeric CHECK constraint already on this table.

ALTER TABLE nutrients
    ADD CONSTRAINT s_hi_log_is_positive CHECK (s_hi_log > 0),
    ADD CONSTRAINT s_lo_log_is_positive CHECK (s_lo_log > 0);
