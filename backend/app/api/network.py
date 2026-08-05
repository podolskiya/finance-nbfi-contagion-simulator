import pandas as pd
from fastapi import APIRouter, HTTPException

from app.models.network import EdgeOut, NetworkResponse, NodeOut
from app.services.data_loader import get_available_quarters, get_bdc_financials, get_network

router = APIRouter(prefix="/api", tags=["network"])


@router.get("/quarters")
def list_quarters() -> list[str]:
    return get_available_quarters()


@router.get("/network", response_model=NetworkResponse)
def get_network_for_quarter(quarter: str, top_banks: int | None = None, top_bdcs: int | None = None):
    """
    top_banks / top_bdcs: if given, limits the response to the top N banks
    (by total exposure) and top N BDCs (by assets), keeping only edges
    between the selected nodes - for rendering a manageable subgraph rather
    than the full ~695 bank x ~193 BDC x ~130K edge network in a browser.
    Omit both for the full dataset (used for data export, not graph display).
    """
    network = get_network()
    bdcs = get_bdc_financials()

    net_q = network[network["quarter_end"] == quarter]
    if net_q.empty:
        available = get_available_quarters()
        raise HTTPException(status_code=404, detail=f"No network data for quarter '{quarter}'. Available: {available}")

    bdcs_q = bdcs[bdcs["quarter_end"] == quarter].drop_duplicates("cik").set_index("cik")

    bank_exposure_totals = net_q.groupby("rssd_id")["estimated_exposure_usd"].sum()
    bank_names = net_q.drop_duplicates("rssd_id").set_index("rssd_id")["bank_name"]

    if top_banks is not None:
        bank_exposure_totals = bank_exposure_totals.sort_values(ascending=False).head(top_banks)

    nodes = []
    for rssd_id, total in bank_exposure_totals.items():
        nodes.append(NodeOut(id=rssd_id, label=bank_names.get(rssd_id, ""), type="bank", size_metric=float(total)))

    bdc_asset_totals = {}
    for cik in net_q["bdc_cik"].unique():
        assets = 0.0
        if cik in bdcs_q.index and not pd.isna(bdcs_q.loc[cik, "assets"]):
            assets = float(bdcs_q.loc[cik, "assets"])
        bdc_asset_totals[cik] = assets

    bdc_ids_in_network = list(bdc_asset_totals.keys())
    if top_bdcs is not None:
        bdc_ids_in_network = sorted(bdc_asset_totals, key=bdc_asset_totals.get, reverse=True)[:top_bdcs]

    for cik in bdc_ids_in_network:
        name = net_q[net_q["bdc_cik"] == cik]["bdc_name"].iloc[0]
        nodes.append(NodeOut(id=cik, label=name, type="bdc", size_metric=bdc_asset_totals[cik]))

    selected_bank_ids = set(bank_exposure_totals.index)
    selected_bdc_ids = set(bdc_ids_in_network)

    edges = [
        EdgeOut(
            source=row["rssd_id"], target=row["bdc_cik"],
            exposure_usd=float(row["estimated_exposure_usd"]), is_observed=bool(row["is_observed_edge"]),
        )
        for _, row in net_q.iterrows()
        if row["rssd_id"] in selected_bank_ids and row["bdc_cik"] in selected_bdc_ids
    ]

    return NetworkResponse(quarter=quarter, nodes=nodes, edges=edges)