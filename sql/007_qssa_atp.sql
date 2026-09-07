-- QSSA molecular layer, ATP branch: mitochondrial electron-transport-chain
-- Michaelis-Menten parameters. Source: v39sEng2.xlsx, sheet 'P1 QSSA
-- ATP-GSH-NAD', rows 13-18 -- each complex individually literature-cited
-- (Hirst 2013, Quinlan 2012, Degli Esposti & Lenaz 1982, Orii & Miki 1982,
-- Reynafarje & Pedersen 1996), all marked verified in the source.

CREATE TABLE IF NOT EXISTS qssa_atp_complexes (
    complex_id      TEXT PRIMARY KEY CHECK (complex_id IN ('I', 'II', 'III', 'IV', 'V')),
    name            TEXT NOT NULL,
    substrate       TEXT NOT NULL,
    km_um           DOUBLE PRECISION NOT NULL CHECK (km_um > 0),
    vmax_relative   DOUBLE PRECISION NOT NULL CHECK (vmax_relative > 0),
    source          TEXT NOT NULL
);
