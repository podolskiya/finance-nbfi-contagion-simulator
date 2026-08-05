"""
DebtRank for the bank-BDC network.

Extends eisenberg_noe.py's direct, first-order loss calculation with real
multi-hop cascade dynamics, via the "common lender" channel described in
that module: a bank distressed by one BDC's losses can propagate reduced
capacity to ALL its other BDC borrowers, which can in turn distress banks
never directly connected to the original shock.

Two impact matrices (both directions needed - this is what makes
multi-hop dynamics possible in an otherwise bipartite, one-directional
lending network):
  - BDC -> Bank: exposure(bank,bdc) / bank's total equity capital.
    How much of the bank's OWN capital is at risk from this BDC.
  - Bank -> BDC: exposure(bank,bdc) / bdc's total bank debt in our network.
    How much of the BDC's funding depends on this one bank.

Algorithm: the standard DebtRank formulation (Battiston et al., 2012).
Each node has distress level h in [0,1] and status Undistressed /
Distressed / Inactive. A node propagates its current distress level to
its neighbors exactly once - in the single round where it's Distressed -
then becomes Inactive and stops propagating (though its own h can still
be pushed up further by other still-active neighbors). This prevents
infinite bouncing and matches the published algorithm exactly.

KNOWN SCOPE LIMIT: same as eisenberg_noe.py - bank distress here means
"capital impairment," not confirmed default; and see that module's note
on regulatory-ratio vs balance-sheet insolvency.

Usage:
    python -m app.services.debtrank --quarter 2026-03-31 --shock-bdc 1287750 --shock-level 1.0
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data_pipeline" / "processed"
NETWORK_PATH = PROCESSED_DIR / "reconstructed_network.csv"
BDC_FINANCIALS_PATH = PROCESSED_DIR / "bdc_financials.csv"
BANK_CAPITAL_PATH = PROCESSED_DIR / "bank_capital_combined.csv"

MAX_ROUNDS = 100


def load_data():
    network = pd.read_csv(NETWORK_PATH, dtype={"rssd_id": str, "bdc_cik": str}, encoding="utf-8", encoding_errors="replace")
    bdcs = pd.read_csv(BDC_FINANCIALS_PATH, dtype={"cik": str}, encoding="utf-8", encoding_errors="replace")
    capital = pd.read_csv(BANK_CAPITAL_PATH, dtype={"rssd_id": str}, encoding="utf-8", encoding_errors="replace")
    return network, bdcs, capital


def build_impact_matrix(network: pd.DataFrame, bdcs: pd.DataFrame, capital: pd.DataFrame, quarter_end: str):
    """
    Returns (node_ids, node_labels, node_type, W) where:
      node_ids: list of ids (rssd_id for banks, cik for BDCs), banks first
      node_labels: display names, same order
      node_type: 'bank' or 'bdc', same order
      W: (N,N) impact matrix, W[i,j] = impact of node i's distress on node j
    """
    net_q = network[network["quarter_end"] == quarter_end].copy()
    bdcs_q = bdcs[bdcs["quarter_end"] == quarter_end].drop_duplicates("cik").set_index("cik")
    capital_q = capital[capital["quarter_end"] == quarter_end].drop_duplicates("rssd_id").set_index("rssd_id")["total_equity_capital_usd"]

    bank_ids = sorted(net_q["rssd_id"].unique())
    bdc_ids = sorted(net_q["bdc_cik"].unique())

    bank_name_lookup = net_q.drop_duplicates("rssd_id").set_index("rssd_id")["bank_name"].to_dict()
    bdc_name_lookup = bdcs_q["name"].to_dict()

    n_banks, n_bdcs = len(bank_ids), len(bdc_ids)
    n = n_banks + n_bdcs
    bank_idx = {b: i for i, b in enumerate(bank_ids)}
    bdc_idx = {c: n_banks + j for j, c in enumerate(bdc_ids)}

    node_ids = bank_ids + bdc_ids
    node_labels = [bank_name_lookup.get(b, "") for b in bank_ids] + [bdc_name_lookup.get(c, "") for c in bdc_ids]
    node_type = ["bank"] * n_banks + ["bdc"] * n_bdcs

    W = np.zeros((n, n))

    bdc_total_bank_debt = net_q.groupby("bdc_cik")["estimated_exposure_usd"].sum()

    for _, edge in net_q.iterrows():
        bank_id, bdc_id = edge["rssd_id"], edge["bdc_cik"]
        exposure = edge["estimated_exposure_usd"]
        i, j = bank_idx[bank_id], bdc_idx[bdc_id]

        bank_cap = capital_q.get(bank_id)
        if bank_cap and bank_cap > 0:
            W[j, i] = min(1.0, exposure / bank_cap)  # BDC -> Bank impact

        bdc_debt_total = bdc_total_bank_debt.get(bdc_id)
        if bdc_debt_total and bdc_debt_total > 0:
            W[i, j] = min(1.0, exposure / bdc_debt_total)  # Bank -> BDC impact

    return node_ids, node_labels, node_type, W


def run_debtrank(node_ids: list, W: np.ndarray, initial_shocks: dict, max_rounds: int = MAX_ROUNDS):
    """
    initial_shocks: {node_id: shock_level in (0,1]}

    Returns (h_final, status_final, rounds_used, h_history) where h_history
    is a list of h arrays, one per round, for inspecting propagation.
    """
    n = len(node_ids)
    id_to_pos = {node_id: i for i, node_id in enumerate(node_ids)}

    h = np.zeros(n)
    status = np.array(["U"] * n, dtype=object)

    for node_id, level in initial_shocks.items():
        if node_id in id_to_pos:
            pos = id_to_pos[node_id]
            h[pos] = min(1.0, level)
            status[pos] = "D"

    h_history = [h.copy()]

    for round_num in range(1, max_rounds + 1):
        distressed = np.where(status == "D")[0]
        if len(distressed) == 0:
            break

        h_prev = h.copy()
        status_prev = status.copy()

        for j in range(n):
            if status_prev[j] == "I":
                continue
            incoming = sum(W[i, j] * h_prev[i] for i in distressed)
            if incoming > 0:
                h[j] = min(1.0, h_prev[j] + incoming)

        for i in range(n):
            if status_prev[i] == "D":
                status[i] = "I"
            elif h[i] > h_prev[i] and status_prev[i] == "U":
                status[i] = "D"

        h_history.append(h.copy())

        if round_num == max_rounds:
            print(f"WARNING: DebtRank did not settle within {max_rounds} rounds - results may be incomplete.")

    return h, status, len(h_history) - 1, h_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--shock-bdc", required=True, help="BDC CIK to shock")
    parser.add_argument("--shock-level", type=float, default=1.0, help="Initial distress level, 0-1 (1.0 = full default)")
    args = parser.parse_args()
    shock_bdc = args.shock_bdc.zfill(10)

    network, bdcs, capital = load_data()
    node_ids, node_labels, node_type, W = build_impact_matrix(network, bdcs, capital, args.quarter)

    if shock_bdc not in node_ids:
        print(f"BDC {shock_bdc} not found in the network for {args.quarter}.")
        return

    h_final, status_final, rounds, _ = run_debtrank(node_ids, W, {shock_bdc: args.shock_level})

    print(f"DebtRank settled after {rounds} round(s).\n")

    results = pd.DataFrame({
        "node_id": node_ids, "label": node_labels, "type": node_type,
        "final_distress": h_final, "status": status_final,
    })
    affected = results[(results["final_distress"] > 0) & (results["node_id"] != shock_bdc)].sort_values("final_distress", ascending=False)

    print(f"Shocked node: {results[results['node_id']==shock_bdc]['label'].iloc[0]} (distress level {args.shock_level})\n")

    affected_banks = affected[affected["type"] == "bank"]
    affected_bdcs = affected[affected["type"] == "bdc"]

    print(f"Banks affected ({len(affected_banks)}), top 15:")
    print(affected_banks.head(15)[["label", "final_distress"]].to_string(index=False))

    print(f"\nOTHER BDCs affected via shared lenders ({len(affected_bdcs)}), top 15:")
    if affected_bdcs.empty:
        print("  (none - distress didn't propagate to any other BDCs)")
    else:
        print(affected_bdcs.head(15)[["label", "final_distress"]].to_string(index=False))


if __name__ == "__main__":
    main()