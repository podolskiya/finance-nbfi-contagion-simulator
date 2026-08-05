"""
Loads the processed pipeline outputs (reconstructed network, BDC
financials, bank capital) into memory once and caches them, rather than
re-reading multi-megabyte CSVs on every API request.

Reuses the exact same file paths and loading conventions (dtype=str for
IDs, utf-8 with encoding_errors="replace") already validated in
eisenberg_noe.py and debtrank.py - this is a thin caching wrapper around
those, not a reimplementation.
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data_pipeline" / "processed"

NETWORK_PATH = PROCESSED_DIR / "reconstructed_network.csv"
BDC_FINANCIALS_PATH = PROCESSED_DIR / "bdc_financials.csv"
BANK_CAPITAL_PATH = PROCESSED_DIR / "bank_capital_combined.csv"


@lru_cache(maxsize=1)
def get_network() -> pd.DataFrame:
    return pd.read_csv(NETWORK_PATH, dtype={"rssd_id": str, "bdc_cik": str}, encoding="utf-8", encoding_errors="replace")


@lru_cache(maxsize=1)
def get_bdc_financials() -> pd.DataFrame:
    return pd.read_csv(BDC_FINANCIALS_PATH, dtype={"cik": str}, encoding="utf-8", encoding_errors="replace")


@lru_cache(maxsize=1)
def get_bank_capital() -> pd.DataFrame:
    if not BANK_CAPITAL_PATH.exists():
        return pd.DataFrame(columns=["rssd_id", "total_equity_capital_usd", "quarter_end"])
    return pd.read_csv(BANK_CAPITAL_PATH, dtype={"rssd_id": str}, encoding="utf-8", encoding_errors="replace")


def get_available_quarters() -> list[str]:
    network = get_network()
    return sorted(network["quarter_end"].unique(), reverse=True)


def clear_cache():
    """Used by tests to force a reload after swapping in different data files."""
    get_network.cache_clear()
    get_bdc_financials.cache_clear()
    get_bank_capital.cache_clear()