"""
Phase 3: Network Construction.

Reconstructs the full bilateral bank-BDC exposure matrix, per quarter, from:
  - Row marginals: each bank's NDFI-sector Call Report exposure, rescaled to
    represent bank-to-BDC-specific lending (see calibration note below).
  - Column marginals: each BDC's LongTermDebt, rescaled to match the same
    total (the standard precondition for RAS/IPF - see README's "key data
    reality" section for why these two raw marginals can't be used directly).
  - A seed/prior matrix built from the 381 real observed edges extracted
    from BDC credit-facility filings (extract_named_lenders.py /
    build_lender_edges.py), weighted by how many times each relationship
    was mentioned.

Calibration: Berrospide, Cai, Lewis-Hayre & Zikes (Federal Reserve FEDS
Notes, May 2025) estimate banks' committed lending to private credit
vehicles at ~$95B as of 2024-Q4, using confidential FR Y-14Q supervisory
data - the most rigorously-scoped external estimate available for exactly
what this project models.

KNOWN LIMITATION: this is a single point-in-time estimate, applied
uniformly across all 4 of our quarters (2025-Q2 through 2026-Q1) for
simplicity, even though the true total almost certainly grew over that
window - consistent with the ~30% growth we observed in Wells Fargo's own
NDFI lending alone across the same period. A more refined version could
scale the calibration total per quarter using observed aggregate NDFI
growth; this version does not, and that's a deliberate simplification,
not an oversight.

Algorithm: RAS / iterative proportional fitting (IPF) - alternately
rescale rows then columns to match target marginals, starting from a
non-uniform prior that heavily weights observed real edges while still
leaving small nonzero mass everywhere (a bank-BDC pair we didn't find in
text-mining isn't necessarily impossible, just unobserved).

Usage:
    python -m app.network_construction.reconstruct_network
"""
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data_pipeline" / "processed"

BANK_NDFI_PATH = PROCESSED_DIR / "bank_ndfi_exposure_combined.csv"
BDC_FINANCIALS_PATH = PROCESSED_DIR / "bdc_financials.csv"
EDGES_PATH = PROCESSED_DIR / "bank_bdc_lender_edges.csv"
OUT_PATH = PROCESSED_DIR / "reconstructed_network.csv"

CALIBRATION_TOTAL_USD = 95_000_000_000  # Berrospide et al. 2025, 2024-Q4
SEED_BOOST = 50  # how much more prior weight an observed edge gets per mention
BASE_PRIOR = 1.0  # baseline weight for every unobserved pair - never exactly zero
MAX_ITER = 2000
CONVERGENCE_TOL = 1e-6


def load_data():
    banks = pd.read_csv(BANK_NDFI_PATH, dtype={"rssd_id": str}, encoding="utf-8", encoding_errors="replace")
    bdcs = pd.read_csv(BDC_FINANCIALS_PATH, dtype={"cik": str}, encoding="utf-8", encoding_errors="replace")
    edges = pd.read_csv(EDGES_PATH, dtype={"bdc_cik": str, "rssd_id": str}, encoding="utf-8", encoding_errors="replace")
    # Only edges with a real RSSD match are usable as bank-side seeds -
    # foreign-branch edges have no node in our bank-side data yet.
    edges = edges[edges["rssd_id"].notna() & (edges["rssd_id"] != "")]
    return banks, bdcs, edges


def compute_row_marginals(banks_q: pd.DataFrame, calibration_total: float) -> pd.Series:
    total_ndfi = banks_q["ndfi_loans_total_usd"].sum()
    return (banks_q.set_index("rssd_id")["ndfi_loans_total_usd"] / total_ndfi) * calibration_total


def compute_col_marginals(bdcs_q: pd.DataFrame, calibration_total: float) -> pd.Series:
    # Some BDCs may have missing/zero debt for a given quarter - treat as 0.
    debt = bdcs_q.set_index("cik")["longtermdebt"].fillna(0).clip(lower=0)
    total_debt = debt.sum()
    if total_debt == 0:
        return debt  # degenerate case, all zero
    return (debt / total_debt) * calibration_total


def build_prior_matrix(bank_ids: list[str], bdc_ids: list[str], edges: pd.DataFrame) -> np.ndarray:
    bank_idx = {b: i for i, b in enumerate(bank_ids)}
    bdc_idx = {c: j for j, c in enumerate(bdc_ids)}

    prior = np.full((len(bank_ids), len(bdc_ids)), BASE_PRIOR)

    for _, edge in edges.iterrows():
        i = bank_idx.get(edge["rssd_id"])
        j = bdc_idx.get(edge["bdc_cik"])
        if i is not None and j is not None:
            prior[i, j] = BASE_PRIOR + edge["mention_count"] * SEED_BOOST

    return prior


def run_ras(prior: np.ndarray, row_targets: np.ndarray, col_targets: np.ndarray,
            max_iter: int = MAX_ITER, tol: float = CONVERGENCE_TOL) -> tuple[np.ndarray, int, bool]:
    """
    Standard RAS / iterative proportional fitting. Returns (matrix,
    iterations_used, converged).
    """
    matrix = prior.copy().astype(float)

    for iteration in range(1, max_iter + 1):
        row_sums = matrix.sum(axis=1)
        row_sums[row_sums == 0] = 1  # avoid div-by-zero for all-zero rows
        matrix = matrix * (row_targets / row_sums)[:, np.newaxis]

        col_sums = matrix.sum(axis=0)
        col_sums[col_sums == 0] = 1
        matrix = matrix * (col_targets / col_sums)[np.newaxis, :]

        row_error = np.abs(matrix.sum(axis=1) - row_targets).max()
        col_error = np.abs(matrix.sum(axis=0) - col_targets).max()
        if max(row_error, col_error) < tol * max(row_targets.max(), col_targets.max()):
            return matrix, iteration, True

    return matrix, max_iter, False


def reconstruct_quarter(quarter_end: str, banks: pd.DataFrame, bdcs: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    banks_q = banks[banks["quarter_end"] == quarter_end].drop_duplicates("rssd_id")
    bdcs_q = bdcs[bdcs["quarter_end"] == quarter_end].drop_duplicates("cik")

    if banks_q.empty or bdcs_q.empty:
        print(f"  Skipping {quarter_end}: no data on one side (banks={len(banks_q)}, bdcs={len(bdcs_q)})")
        return pd.DataFrame()

    row_marginals = compute_row_marginals(banks_q, CALIBRATION_TOTAL_USD)
    col_marginals_raw = compute_col_marginals(bdcs_q, CALIBRATION_TOTAL_USD)

    # Standard RAS precondition: row total must equal column total. Row
    # total is fixed at CALIBRATION_TOTAL_USD by construction; rescale
    # columns to match exactly (they may be off slightly due to zero/
    # missing debt values dropped above).
    col_total = col_marginals_raw.sum()
    if col_total == 0:
        print(f"  Skipping {quarter_end}: no usable BDC debt data")
        return pd.DataFrame()
    col_marginals = col_marginals_raw * (CALIBRATION_TOTAL_USD / col_total)

    bank_ids = list(row_marginals.index)
    bdc_ids = list(col_marginals.index)

    quarter_edges = edges[edges["most_recent_filing"] <= quarter_end] if "most_recent_filing" in edges.columns else edges
    prior = build_prior_matrix(bank_ids, bdc_ids, edges)

    matrix, iterations, converged = run_ras(
        prior, row_marginals.values, col_marginals.values
    )

    print(f"  {quarter_end}: RAS {'converged' if converged else 'DID NOT converge'} after {iterations} iterations")

    bank_name_lookup = banks_q.set_index("rssd_id")["bank_name"].to_dict()
    bdc_name_lookup = bdcs_q.set_index("cik")["name"].to_dict()

    records = []
    for i, bank_id in enumerate(bank_ids):
        for j, bdc_id in enumerate(bdc_ids):
            exposure = matrix[i, j]
            if exposure < 1000:  # drop sub-$1000 noise-level allocations
                continue
            records.append({
                "quarter_end": quarter_end,
                "rssd_id": bank_id,
                "bank_name": bank_name_lookup.get(bank_id, ""),
                "bdc_cik": bdc_id,
                "bdc_name": bdc_name_lookup.get(bdc_id, ""),
                "estimated_exposure_usd": exposure,
                "is_observed_edge": prior[i, j] > BASE_PRIOR,
            })

    return pd.DataFrame(records)


def main():
    banks, bdcs, edges = load_data()
    print(f"Loaded {banks['rssd_id'].nunique()} banks, {bdcs['cik'].nunique()} BDCs, {len(edges)} usable observed edges.\n")

    quarters = sorted(set(banks["quarter_end"]) & set(bdcs["quarter_end"]))
    print(f"Reconstructing for quarters: {quarters}\n")

    all_results = []
    for quarter_end in quarters:
        result = reconstruct_quarter(quarter_end, banks, bdcs, edges)
        if not result.empty:
            all_results.append(result)

    if not all_results:
        print("No results produced - check input data.")
        return

    combined = pd.concat(all_results, ignore_index=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_PATH, index=False)

    print(f"\nWrote {len(combined)} bank-BDC-quarter exposure estimates to {OUT_PATH}")

    latest_q = max(quarters)
    ares = combined[(combined["bdc_cik"] == "0001287750") & (combined["quarter_end"] == latest_q)]
    if not ares.empty:
        print(f"\nSanity check - Ares Capital's top reconstructed lenders ({latest_q}):")
        print(ares.sort_values("estimated_exposure_usd", ascending=False).head(8)[
            ["bank_name", "estimated_exposure_usd", "is_observed_edge"]
        ].to_string(index=False))


if __name__ == "__main__":
    main()