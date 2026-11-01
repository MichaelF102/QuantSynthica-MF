from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FundSummary(BaseModel):
    id: int
    name: str
    symbol: str | None
    amc: str
    category: str
    asset_tier: str
    plan_type: str
    option_type: str
    is_insurer_fund: bool
    is_discontinued: bool
    quarantined: bool
    price: float | None
    change_pct: float | None
    ytd_return: float | None
    return_3m: float | None
    return_1y: float | None
    return_3y: float | None
    return_5y: float | None
    net_assets: float | None


class FundList(BaseModel):
    items: list[FundSummary]
    total: int
    page: int
    page_size: int
    ingestion_run_id: int | None


class SiblingScheme(BaseModel):
    id: int
    name: str
    plan_type: str
    option_type: str
    idcw_mode: str | None
    idcw_freq: str | None


class FundDetail(FundSummary):
    base_fund: str | None
    family_id: int | None
    idcw_mode: str | None
    idcw_freq: str | None
    n_share_classes: int | None
    avg_50d: float | None
    avg_200d: float | None
    low_52w: float | None
    high_52w: float | None
    initial_investment: float | None
    market_cap_value: float | None
    price_change_52w_pct: float | None
    external_ids: dict[str, str]
    siblings: list[SiblingScheme]
    features: dict[str, Any]
    quality_issues: list[dict[str, Any]]
    ingestion_run_id: int
    data_asof: datetime | None
    nav_metrics: dict[str, Any] | None = None


class DataQualitySummary(BaseModel):
    ingestion_run_id: int | None
    status: str | None
    file_name: str | None
    file_sha256: str | None
    rows_read: int | None
    rows_quarantined: int | None
    summary: dict[str, Any] | None
    issues_by_rule: dict[str, dict[str, int]]
    note: str
