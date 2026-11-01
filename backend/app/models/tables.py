"""Relational schema for Phase 1.

Identity model (docs/decisions/002-identity-model.md):
  AMC -> FundFamily (base_fund) -> Scheme (share class: plan + option) -> ExternalId (Yahoo symbol, later AMFI/ISIN)
Plan/option live on Scheme as constrained strings with an explicit 'Unspecified'.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

JsonType = JSON().with_variant(JSONB(), "postgresql")


class AMC(Base):
    __tablename__ = "amcs"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    is_insurer: Mapped[bool] = mapped_column(Boolean, default=False)


class FundCategory(Base):
    __tablename__ = "fund_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class FundFamily(Base):
    """A fund and all its share classes (CSV `base_fund`)."""

    __tablename__ = "fund_families"
    __table_args__ = (UniqueConstraint("base_fund", "amc_id", name="uq_family_base_amc"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    base_fund: Mapped[str] = mapped_column(String(300))
    amc_id: Mapped[int] = mapped_column(ForeignKey("amcs.id"))
    amc: Mapped[AMC] = relationship()


class Scheme(Base):
    __tablename__ = "schemes"
    __table_args__ = (
        CheckConstraint("plan_type in ('Direct','Regular','Institutional','Unspecified')", name="ck_plan_type"),
        CheckConstraint("option_type in ('Growth','IDCW','Unspecified')", name="ck_option_type"),
        UniqueConstraint("name", "amc_id", name="uq_scheme_name_amc"),
        Index("ix_schemes_category", "category_id"),
        Index("ix_schemes_family", "family_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    family_id: Mapped[int | None] = mapped_column(ForeignKey("fund_families.id"))
    amc_id: Mapped[int] = mapped_column(ForeignKey("amcs.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("fund_categories.id"))
    asset_tier: Mapped[str] = mapped_column(String(20))
    plan_type: Mapped[str] = mapped_column(String(20))
    option_type: Mapped[str] = mapped_column(String(20))
    idcw_mode: Mapped[str | None] = mapped_column(String(20))
    idcw_freq: Mapped[str | None] = mapped_column(String(20))
    is_insurer_fund: Mapped[bool] = mapped_column(Boolean, default=False)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False)
    n_share_classes: Mapped[int | None] = mapped_column(Integer)

    amc: Mapped[AMC] = relationship()
    category: Mapped[FundCategory] = relationship()
    family: Mapped[FundFamily | None] = relationship()
    external_ids: Mapped[list[ExternalId]] = relationship(back_populates="scheme")


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(300))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_asof: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # unknown for the CSV
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|succeeded|failed|skipped
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    schemes_inserted: Mapped[int] = mapped_column(Integer, default=0)
    schemes_updated: Mapped[int] = mapped_column(Integer, default=0)
    schemes_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    snapshots_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_quarantined: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    error: Mapped[str | None] = mapped_column(String(2000))


class ExternalId(Base):
    __tablename__ = "external_ids"
    __table_args__ = (UniqueConstraint("id_type", "value", "source", name="uq_external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), index=True)
    id_type: Mapped[str] = mapped_column(String(30))  # yahoo_symbol | amfi_code | isin
    value: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(50))
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    scheme: Mapped[Scheme] = relationship(back_populates="external_ids")


class FundSnapshot(Base):
    """One observation per scheme per ingestion run. Nulls are preserved, never imputed."""

    __tablename__ = "fund_snapshots"
    __table_args__ = (
        UniqueConstraint("scheme_id", "ingestion_run_id", name="uq_snapshot_scheme_run"),
        Index("ix_snapshots_run", "ingestion_run_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"))
    ingestion_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    source_rank: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    ytd_return: Mapped[float | None] = mapped_column(Float)
    return_3m: Mapped[float | None] = mapped_column(Float)
    return_1y: Mapped[float | None] = mapped_column(Float)
    return_3y: Mapped[float | None] = mapped_column(Float)
    return_5y: Mapped[float | None] = mapped_column(Float)
    net_assets: Mapped[float | None] = mapped_column(Float)
    avg_50d: Mapped[float | None] = mapped_column(Float)
    avg_200d: Mapped[float | None] = mapped_column(Float)
    low_52w: Mapped[float | None] = mapped_column(Float)
    high_52w: Mapped[float | None] = mapped_column(Float)
    initial_investment: Mapped[float | None] = mapped_column(Float)
    market_cap_value: Mapped[float | None] = mapped_column(Float)
    price_change_52w_pct: Mapped[float | None] = mapped_column(Float)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    features: Mapped[dict[str, Any]] = mapped_column(JsonType)  # engineered columns from the CSV
    audit: Mapped[dict[str, Any]] = mapped_column(JsonType)  # e.g. `split` (never a model feature)

    scheme: Mapped[Scheme] = relationship()


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = (Index("ix_dqi_run_rule", "ingestion_run_id", "rule"),)
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    ingestion_run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    scheme_id: Mapped[int | None] = mapped_column(ForeignKey("schemes.id"))
    symbol: Mapped[str | None] = mapped_column(String(60))
    rule: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    detail: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AmfiScheme(Base):
    """Official scheme register row (silver). One per AMFI scheme code; refreshed from the daily NAV file."""

    __tablename__ = "amfi_schemes"
    code: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(400))
    plan: Mapped[str | None] = mapped_column(String(100))
    option: Mapped[str | None] = mapped_column(String(200))
    isin_primary: Mapped[str | None] = mapped_column(String(20))
    isin_reinvest: Mapped[str | None] = mapped_column(String(20))
    amc: Mapped[str | None] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(200))
    latest_nav: Mapped[float | None] = mapped_column(Float)
    latest_nav_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_seen_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class SchemeMapping(Base):
    """Source scheme -> official scheme code. A code may serve several source rows (IDCW payout/reinvest),
    but each (amfi_code, variant) slot is unique among accepted mappings."""

    __tablename__ = "scheme_mappings"
    __table_args__ = (
        Index(
            "uq_mapping_slot", "amfi_code", "variant", unique=True,
            postgresql_where=text("status in ('confirmed','probable','name_only') and amfi_code is not null"),
        ),
        CheckConstraint(
            "status in ('confirmed','probable','name_only','ambiguous','unmapped','not_amfi_scheme')", name="ck_mapping_status"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), unique=True)
    amfi_code: Mapped[str | None] = mapped_column(ForeignKey("amfi_schemes.code"), index=True)
    variant: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    name_score: Mapped[float | None] = mapped_column(Float)
    nav_tier: Mapped[int | None] = mapped_column(Integer)
    nav_diff: Mapped[float | None] = mapped_column(Float)
    evidence_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    method: Mapped[str] = mapped_column(String(80))
    matcher_version: Mapped[str] = mapped_column(String(20))
    alternatives: Mapped[list[Any] | None] = mapped_column(JsonType)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class NavCoverage(Base):
    """Per-scheme summary of the stored NAV time series (the series itself lives in Parquet)."""

    __tablename__ = "nav_coverage"
    amfi_code: Mapped[str] = mapped_column(ForeignKey("amfi_schemes.code"), primary_key=True)
    source: Mapped[str] = mapped_column(String(30))
    first_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    n_obs: Mapped[int] = mapped_column(Integer, default=0)
    n_issues: Mapped[int] = mapped_column(Integer, default=0)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | empty | failed
    error: Mapped[str | None] = mapped_column(String(500))


class SchemeMetric(Base):
    """Batch-computed, NAV-derived metrics per scheme (3Y window unless stated). Recomputed by `pipeline metrics`."""

    __tablename__ = "scheme_metrics"
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), primary_key=True)
    amfi_code: Mapped[str] = mapped_column(String(12))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    methodology_version: Mapped[str] = mapped_column(String(30))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    peer_group: Mapped[str | None] = mapped_column(String(200))
    peer_count: Mapped[int | None] = mapped_column(Integer)
    ret_1y: Mapped[float | None] = mapped_column(Float)
    ret_3y: Mapped[float | None] = mapped_column(Float)
    ret_5y: Mapped[float | None] = mapped_column(Float)
    vol_3y: Mapped[float | None] = mapped_column(Float)
    sharpe_3y: Mapped[float | None] = mapped_column(Float)
    sortino_3y: Mapped[float | None] = mapped_column(Float)
    max_dd_3y: Mapped[float | None] = mapped_column(Float)
    calmar_3y: Mapped[float | None] = mapped_column(Float)
    beta_3y: Mapped[float | None] = mapped_column(Float)
    alpha_3y: Mapped[float | None] = mapped_column(Float)
    te_3y: Mapped[float | None] = mapped_column(Float)
    ir_3y: Mapped[float | None] = mapped_column(Float)
    pctile_ret_3y: Mapped[float | None] = mapped_column(Float)
    pctile_sharpe_3y: Mapped[float | None] = mapped_column(Float)
    pctile_sortino_3y: Mapped[float | None] = mapped_column(Float)
    pctile_max_dd_3y: Mapped[float | None] = mapped_column(Float)
    pctile_vol_3y: Mapped[float | None] = mapped_column(Float)


class FundScore(Base):
    """Latest QuantSynthica Fund Score per scheme (peer-relative, point-in-time as of `as_of`)."""

    __tablename__ = "fund_scores"
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), primary_key=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    methodology_version: Mapped[str] = mapped_column(String(30))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    peer_group: Mapped[str] = mapped_column(String(200), index=True)
    peers: Mapped[int] = mapped_column(Integer)
    composite: Mapped[float | None] = mapped_column(Float, index=True)
    coverage: Mapped[float | None] = mapped_column(Float)
    rank_in_group: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict[str, Any]] = mapped_column(JsonType)  # raw metrics, percentiles, z, factor scores, contributions


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    config_hash: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | succeeded | failed
    request: Mapped[dict[str, Any]] = mapped_column(JsonType)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    """Opaque bearer sessions. Only the SHA-256 of the token is stored, so a database leak cannot be replayed."""

    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserItem(Base):
    """Per-user saved things: watchlists, portfolios, screens, alerts, research notes. Always queried with user_id."""

    __tablename__ = "user_items"
    __table_args__ = (UniqueConstraint("user_id", "kind", "name", name="uq_user_item_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
