from typing import Literal

from pydantic import BaseModel


class NodeOut(BaseModel):
    id: str
    label: str
    type: Literal["bank", "bdc"]
    size_metric: float  


class EdgeOut(BaseModel):
    source: str  # bank rssd_id
    target: str  # bdc cik
    exposure_usd: float
    is_observed: bool


class NetworkResponse(BaseModel):
    quarter: str
    nodes: list[NodeOut]
    edges: list[EdgeOut]