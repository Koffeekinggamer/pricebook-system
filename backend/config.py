"""Paths and defaults."""

from __future__ import annotations

from pathlib import Path

# Project root: parent of backend/
APP_DIR = Path(__file__).resolve().parent.parent
DB_PATH = APP_DIR / "master_pricebook.db"

DEFAULT_MULTIPLIER = 2.7
DEFAULT_PRICE_BASIS = "wholesale"
DEFAULT_SEARCH_LIMIT = 500

# Unique identity for a sellable configuration (dedupe / upsert)
IDENTITY_FIELDS = (
    "vendor",
    "collection",
    "part_number",
    "species",
    "finish_state",
    "option_key",
    "dimensions",
)
