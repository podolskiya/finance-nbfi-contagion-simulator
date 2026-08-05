from fastapi import APIRouter, HTTPException

from app.models.simulate import (
    BankLossOut,
    BdcShockSummary,
    DebtRankNodeOut,
    DebtRankResult,
    EisenbergNoeResult,
    ShockRequest,
    SimulateResponse,
)
from app.services import debtrank as debtrank_module
from app.services import eisenberg_noe as en_module
from app.services.data_loader import get_available_quarters, get_bank_capital, get_bdc_financials, get_network

router = APIRouter(prefix="/api", tags=["simulate"])


@router.post("/simulate", response_model=SimulateResponse)
def simulate(request: ShockRequest):
    shock_bdc = request.shock_bdc_cik.zfill(10)
    network = get_network()
    bdcs = get_bdc_financials()

    if network[network["quarter_end"] == request.quarter].empty:
        raise HTTPException(status_code=404, detail=f"No data for quarter '{request.quarter}'. Available: {get_available_quarters()}")

    response = SimulateResponse(quarter=request.quarter, shocked_bdc_cik=shock_bdc)

    if request.algorithm in ("eisenberg_noe", "both"):
        response.eisenberg_noe = _run_eisenberg_noe(network, bdcs, request.quarter, shock_bdc, request.shock_fraction)

    if request.algorithm in ("debtrank", "both"):
        shock_level = request.shock_level if request.shock_level is not None else request.shock_fraction
        response.debtrank = _run_debtrank(network, bdcs, request.quarter, shock_bdc, shock_level)

    if response.eisenberg_noe is None and response.debtrank is None:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm '{request.algorithm}'")

    return response


def _run_eisenberg_noe(network, bdcs, quarter: str, shock_bdc: str, shock_fraction: float) -> EisenbergNoeResult:
    bdc_results, bank_results = en_module.compute_clearing(network, bdcs, quarter, {shock_bdc: shock_fraction})

    shocked = bdc_results[bdc_results["bdc_cik"] == shock_bdc]
    if shocked.empty:
        raise HTTPException(status_code=404, detail=f"BDC '{shock_bdc}' not found for quarter '{quarter}'")
    row = shocked.iloc[0]
    bdc_summary = BdcShockSummary(
        bdc_cik=shock_bdc, bdc_name=row["bdc_name"],
        assets_pre_shock=float(row["assets_pre_shock"]), assets_post_shock=float(row["assets_post_shock"]),
        liabilities=float(row["liabilities"]), recovery_rate=float(row["recovery_rate"]),
        is_distressed=bool(row["is_distressed"]),
    )

    affected = bank_results[(bank_results["bdc_cik"] == shock_bdc) & (bank_results["loss_usd"] > 0)]
    bank_capital = get_bank_capital()
    bank_capital_q = bank_capital[bank_capital["quarter_end"] == quarter].drop_duplicates("rssd_id").set_index("rssd_id")["total_equity_capital_usd"]

    summary = en_module.summarize_bank_losses(affected, bank_capital_q)

    affected_out = []
    insolvent_count = 0
    for _, r in summary.iterrows():
        is_insolvent = bool(r["is_insolvent"]) if "is_insolvent" in summary.columns else None
        if is_insolvent:
            insolvent_count += 1
        affected_out.append(BankLossOut(
            rssd_id=r["rssd_id"], bank_name=r["bank_name"],
            total_exposure_usd=float(r["total_exposure_usd"]), total_loss_usd=float(r["total_loss_usd"]),
            loss_pct_of_capital=float(r["loss_pct_of_capital"]) if "loss_pct_of_capital" in summary.columns else None,
            severity=r.get("severity"), is_insolvent=is_insolvent,
        ))

    return EisenbergNoeResult(
        shocked_bdc=bdc_summary, affected_banks=affected_out,
        insolvent_bank_count=insolvent_count, total_loss_usd=float(summary["total_loss_usd"].sum()) if not summary.empty else 0.0,
    )


def _run_debtrank(network, bdcs, quarter: str, shock_bdc: str, shock_level: float) -> DebtRankResult:
    bank_capital = get_bank_capital()
    node_ids, node_labels, node_type, W = debtrank_module.build_impact_matrix(network, bdcs, bank_capital, quarter)

    if shock_bdc not in node_ids:
        raise HTTPException(status_code=404, detail=f"BDC '{shock_bdc}' not found for quarter '{quarter}'")

    h_final, status_final, rounds, _ = debtrank_module.run_debtrank(node_ids, W, {shock_bdc: shock_level})

    affected_banks, affected_bdcs = [], []
    for i, node_id in enumerate(node_ids):
        if node_id == shock_bdc or h_final[i] <= 0:
            continue
        out = DebtRankNodeOut(node_id=node_id, label=node_labels[i], type=node_type[i], final_distress=float(h_final[i]))
        (affected_banks if node_type[i] == "bank" else affected_bdcs).append(out)

    affected_banks.sort(key=lambda x: x.final_distress, reverse=True)
    affected_bdcs.sort(key=lambda x: x.final_distress, reverse=True)

    return DebtRankResult(rounds_used=rounds, affected_banks=affected_banks, affected_bdcs=affected_bdcs)