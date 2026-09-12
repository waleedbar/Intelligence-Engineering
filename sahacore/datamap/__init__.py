"""The P1 DataMap input/output contract, as typed models.

Contract M1 asks for the DataMap "implemented as Pydantic models and Postgres
DDL". The DDL is sql/019_datamap.sql; this package is the other half.
"""
from sahacore.datamap.models import (
    CONTRACT_ROW_COUNT,
    DataMap,
    EngineVariable,
    Layer,
    MALFORMED_AT_SOURCE,
    OnboardingField,
    Priority,
    SECTIONS,
    SHEET_TITLE_ROW_COUNT,
    shortfall,
)

__all__ = [
    "CONTRACT_ROW_COUNT",
    "DataMap",
    "EngineVariable",
    "Layer",
    "MALFORMED_AT_SOURCE",
    "OnboardingField",
    "Priority",
    "SECTIONS",
    "SHEET_TITLE_ROW_COUNT",
    "shortfall",
]
