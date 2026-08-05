"""
Eisenberg-Noe style clearing for the bank-BDC network.

Our network is bipartite (banks lend to BDCs; BDCs don't lend to banks or
to each other, banks don't lend to each other) - so unlike classic
Eisenberg-Noe (designed for closed interbank systems with obligation
cycles), this collapses to a direct, single-pass calculation rather than
an iterative fixed point: a shocked BDC's asset loss determines its
recovery rate, and its lending banks take losses proportional to their
share of that BDC's reconstructed bank debt.

Loss allocation assumption: when a BDC can't fully pay its debts, we
assume pari passu treatment - every creditor (bank or otherwise) takes the
same proportional haircut, rather than assuming banks have senior/
subordinated status relative to bondholders. This is a standard,
defensible default absent specific seniority information, not a claim
about actual legal priority.

Bank-side capital: Total Equity Capital (Schedule RC, item 28, MDRM 3210)
is now collected (parse_bank_capital.py) and used here to compute each
bank's loss as a percentage of its own capital base - not just a dollar
loss amount. A loss exceeding 100% of a bank's total equity capital is
flagged as technical insolvency (is_insolvent below) - an unambiguous,
defensible threshold using data we actually have.

REMAINING SCOPE LIMIT: this is balance-sheet insolvency (total equity
wiped out), not regulatory capital adequacy. Real supervisory action
("well capitalized" / "undercapitalized" / prompt corrective action)
triggers off capital RATIOS - Tier 1 capital divided by risk-weighted or
average total assets - well before a bank's equity actually hits zero.
Tier 1 capital involves specific regulatory deductions (goodwill,
certain deferred tax assets, AOCI treatment) that are a meaningfully
more complex, error-prone pull than the simple Schedule RC total equity
figure used here. Not attempted in this version rather than risk getting
the netting wrong - a defensible simplification, not an oversight.

Multi-hop cascading (one bank's distress affecting its OTHER BDC
borrowers) is handled separately in the DebtRank module, via the
shared-lender channel - not by iterating this function.

Usage:
    python -m app.services.eisenberg_noe --quarter 2026-03-31 --shock-bdc 0001287750 --shock-fraction 0.4
"""
import argparse
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data_pipeline" / "processed"
NETWORK_PATH = PROCESSED_DIR / "reconstructed_network.csv"
BDC_FINANCIALS_PATH = PROCESSED_DIR / "bdc_financials.csv"
BANK_CAPITAL_PATH = PROCESSED_DIR / "bank_capital_combined.csv"


def load_data():
    network = pd.read_csv(NETWORK_PATH, dtype={"rssd_id": str, "bdc_cik": str}, encoding="utf-8", encoding_errors="replace")
    bdcs = pd.read_csv(BDC_FINANCIALS_PATH, dtype={"cik": str}, encoding="utf-8", encoding_errors="replace")
    return network, bdcs


def load_bank_capital(quarter_end: str) -> pd.Series:
    """Returns {rssd_id: total_equity_capital_usd} for the given quarter.
    Returns an empty Series (not an error) if the capital file doesn't
    exist yet - loss-as-%-of-capital simply won't be computed in that case,
    everything else still works."""
    if not BANK_CAPITAL_PATH.exists():
        return pd.Series(dtype=float)
    capital = pd.read_csv(BANK_CAPITAL_PATH, dtype={"rssd_id": str}, encoding="utf-8", encoding_errors="replace")
    capital_q = capital[capital["quarter_end"] == quarter_end].drop_duplicates("rssd_id")
    return capital_q.set_index("rssd_id")["total_equity_capital_usd"]


def compute_clearing(network: pd.DataFrame, bdcs: pd.DataFrame, quarter_end: str,
                      shocks: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    shocks: {bdc_cik: fraction_of_assets_lost}. BDCs not present in this
    dict are treated as unshocked (0 loss).

    Returns (bdc_results, bank_results):
      bdc_results: one row per BDC - assets pre/post shock, total bank
        debt owed, recovery rate, whether it's distressed (recovery < 1.0).
      bank_results: one row per (bank, BDC) edge - exposure, recovery
        rate, realized payment, and loss.
    """
    net_q = network[network["quarter_end"] == quarter_end].copy()
    bdcs_q = bdcs[bdcs["quarter_end"] == quarter_end].drop_duplicates("cik").set_index("cik")

    # Each BDC's total debt owed to banks IN OUR RECONSTRUCTED NETWORK -
    # this is deliberately smaller than the BDC's total reported
    # liabilities (which also includes bonds, SBA debentures, etc.), by
    # construction from Phase 3's calibration. Kept as a distinct concept.
    bank_debt_by_bdc = net_q.groupby("bdc_cik")["estimated_exposure_usd"].sum()

    bdc_rows = []
    for cik, row in bdcs_q.iterrows():
        assets = row.get("assets")
        liabilities = row.get("liabilities")
        if pd.isna(assets) or pd.isna(liabilities):
            continue

        shock_fraction = shocks.get(cik, 0.0)
        assets_post_shock = assets * (1 - shock_fraction)

        recovery_rate = min(1.0, assets_post_shock / liabilities) if liabilities > 0 else 1.0
        is_distressed = recovery_rate < 1.0

        bdc_rows.append({
            "bdc_cik": cik,
            "bdc_name": row.get("name", ""),
            "assets_pre_shock": assets,
            "assets_post_shock": assets_post_shock,
            "liabilities": liabilities,
            "bank_debt_in_network": bank_debt_by_bdc.get(cik, 0.0),
            "recovery_rate": recovery_rate,
            "is_distressed": is_distressed,
            "shock_fraction_applied": shock_fraction,
        })

    bdc_results = pd.DataFrame(bdc_rows)

    recovery_lookup = bdc_results.set_index("bdc_cik")["recovery_rate"].to_dict()

    bank_rows = []
    for _, edge in net_q.iterrows():
        cik = edge["bdc_cik"]
        recovery_rate = recovery_lookup.get(cik, 1.0)
        exposure = edge["estimated_exposure_usd"]
        realized_payment = exposure * recovery_rate
        loss = exposure - realized_payment

        bank_rows.append({
            "rssd_id": edge["rssd_id"],
            "bank_name": edge["bank_name"],
            "bdc_cik": cik,
            "bdc_name": edge["bdc_name"],
            "exposure_usd": exposure,
            "recovery_rate": recovery_rate,
            "realized_payment_usd": realized_payment,
            "loss_usd": loss,
        })

    bank_results = pd.DataFrame(bank_rows)
    return bdc_results, bank_results


def classify_severity(loss_pct_of_capital: float) -> str:
    """
    Maps loss-as-%-of-own-capital to a severity label. The 100% threshold
    (technical insolvency, total equity wiped out) is unambiguous. The
    intermediate tiers (minor/significant/severe) are a reasonable,
    intuitive proxy given available data, but are NOT the same as crossing
    an actual regulatory "well capitalized" / "undercapitalized" threshold
    - those are ratio-based (Tier 1 capital / risk-weighted assets) and
    would require additional data this project doesn't collect. See the
    module docstring's "REMAINING SCOPE LIMIT" note.
    """
    if pd.isna(loss_pct_of_capital):
        return "unknown (no capital data)"
    if loss_pct_of_capital >= 1.0:
        return "TECHNICALLY INSOLVENT (loss exceeds total equity capital)"
    if loss_pct_of_capital >= 0.15:
        return "severe capital impairment"
    if loss_pct_of_capital >= 0.05:
        return "significant capital impairment"
    if loss_pct_of_capital >= 0.01:
        return "minor capital impairment"
    return "negligible"


def summarize_bank_losses(bank_results: pd.DataFrame, bank_capital: pd.Series = None) -> pd.DataFrame:
    """Aggregates per-edge losses up to total loss per bank, across all its
    BDC exposures. If bank_capital is provided (rssd_id -> total equity
    capital), also computes loss as a percentage of that bank's own capital
    - the actual solvency-relevant metric, not just a dollar amount - plus
    a severity classification including explicit technical insolvency."""
    summary = (
        bank_results.groupby(["rssd_id", "bank_name"])
        .agg(total_exposure_usd=("exposure_usd", "sum"), total_loss_usd=("loss_usd", "sum"))
        .reset_index()
        .sort_values("total_loss_usd", ascending=False)
    )

    if bank_capital is not None and not bank_capital.empty:
        summary["total_equity_capital_usd"] = summary["rssd_id"].map(bank_capital)
        summary["loss_pct_of_capital"] = summary["total_loss_usd"] / summary["total_equity_capital_usd"]
        summary["is_insolvent"] = summary["loss_pct_of_capital"] >= 1.0
        summary["severity"] = summary["loss_pct_of_capital"].apply(classify_severity)

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarter", required=True, help="e.g. 2026-03-31")
    parser.add_argument("--shock-bdc", required=True, help="BDC CIK to shock")
    parser.add_argument("--shock-fraction", type=float, required=True, help="Fraction of assets lost, e.g. 0.4 for 40%%")
    args = parser.parse_args()
    args.shock_bdc = args.shock_bdc.zfill(10)

    network, bdcs = load_data()
    shocks = {args.shock_bdc: args.shock_fraction}

    bdc_results, bank_results = compute_clearing(network, bdcs, args.quarter, shocks)

    shocked = bdc_results[bdc_results["bdc_cik"] == args.shock_bdc]
    if not shocked.empty:
        row = shocked.iloc[0]
        print(f"Shocked BDC: {row['bdc_name']} ({args.shock_bdc})")
        print(f"  Assets: {row['assets_pre_shock']:,.0f} -> {row['assets_post_shock']:,.0f} ({args.shock_fraction:.0%} shock)")
        print(f"  Liabilities: {row['liabilities']:,.0f}")
        print(f"  Recovery rate: {row['recovery_rate']:.1%}")
        print(f"  Distressed: {row['is_distressed']}\n")

    affected_banks = bank_results[(bank_results["bdc_cik"] == args.shock_bdc) & (bank_results["loss_usd"] > 0)]
    if not affected_banks.empty:
        bank_capital = load_bank_capital(args.quarter)
        summary = summarize_bank_losses(affected_banks, bank_capital)

        if bank_capital.empty:
            print("(No bank capital data found - run combine_bank_capital_quarters.py first for loss-as-%-of-capital)")
            display_cols = ["bank_name", "total_exposure_usd", "total_loss_usd"]
        else:
            display_cols = ["bank_name", "total_exposure_usd", "total_loss_usd", "loss_pct_of_capital", "severity"]

            insolvent = summary[summary["is_insolvent"]]
            if not insolvent.empty:
                print(f"*** {len(insolvent)} bank(s) technically insolvent under this shock: ***")
                print(insolvent[["bank_name", "total_loss_usd", "total_equity_capital_usd", "loss_pct_of_capital"]].to_string(index=False))
                print()

        top_n = 20
        print(f"Banks with direct losses from this BDC ({len(summary)} total, showing top {min(top_n, len(summary))} by loss):")
        print(summary.head(top_n)[display_cols].to_string(index=False))
        if len(summary) > top_n:
            remainder_loss = summary.iloc[top_n:]["total_loss_usd"].sum()
            print(f"\n...plus {len(summary) - top_n} more banks with smaller losses (combined: ${remainder_loss:,.0f})")
    else:
        print("No banks took losses (BDC was not distressed, or has no reconstructed lenders).")


if __name__ == "__main__":
    main()