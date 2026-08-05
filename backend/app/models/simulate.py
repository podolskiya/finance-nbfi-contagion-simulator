from typing import Literal

from pydantic import BaseModel, Field


class ShockRequest(BaseModel):
    quarter: str = Field(..., examples=["2026-03-31"])
    shock_bdc_cik: str = Field(..., description="CIK of the BDC to shock")
    shock_fraction: float = Field(..., ge=0, le=1, description="Fraction of BDC assets lost, for Eisenberg-Noe clearing")
    shock_level: float | None = Field(
        None, ge=0, le=1,
        description="DebtRank initial distress level (0-1). Defaults to shock_fraction if not given.",
    )
    algorithm: Literal["eisenberg_noe", "debtrank", "both"] = "both"


class BdcShockSummary(BaseModel):
    bdc_cik: str
    bdc_name: str
    assets_pre_shock: float
    assets_post_shock: float
    liabilities: float
    recovery_rate: float
    is_distressed: bool


class BankLossOut(BaseModel):
    rssd_id: str
    bank_name: str
    total_exposure_usd: float
    total_loss_usd: float
    loss_pct_of_capital: float | None = None
    severity: str | None = None
    is_insolvent: bool | None = None


class EisenbergNoeResult(BaseModel):
    shocked_bdc: BdcShockSummary
    affected_banks: list[BankLossOut]
    insolvent_bank_count: int
    total_loss_usd: float


class DebtRankNodeOut(BaseModel):
    node_id: str
    label: str
    type: Literal["bank", "bdc"]
    final_distress: float


class DebtRankResult(BaseModel):
    rounds_used: int
    affected_banks: list[DebtRankNodeOut]
    affected_bdcs: list[DebtRankNodeOut]


class SimulateResponse(BaseModel):
    quarter: str
    shocked_bdc_cik: str
    eisenberg_noe: EisenbergNoeResult | None = None
    debtrank: DebtRankResult | None = None