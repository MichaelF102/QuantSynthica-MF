// Typed client for the FastAPI backend. All figures shown in the UI come from here.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type FundSummary = {
  id: number;
  name: string;
  symbol: string | null;
  amc: string;
  category: string;
  asset_tier: string;
  plan_type: string;
  option_type: string;
  is_insurer_fund: boolean;
  is_discontinued: boolean;
  quarantined: boolean;
  price: number | null;
  change_pct: number | null;
  ytd_return: number | null;
  return_3m: number | null;
  return_1y: number | null;
  return_3y: number | null;
  return_5y: number | null;
  net_assets: number | null;
};

export type FundList = {
  items: FundSummary[];
  total: number;
  page: number;
  page_size: number;
  ingestion_run_id: number | null;
};

export type SiblingScheme = {
  id: number;
  name: string;
  plan_type: string;
  option_type: string;
  idcw_mode: string | null;
  idcw_freq: string | null;
};

export type FundDetail = FundSummary & {
  base_fund: string | null;
  family_id: number | null;
  idcw_mode: string | null;
  idcw_freq: string | null;
  n_share_classes: number | null;
  avg_50d: number | null;
  avg_200d: number | null;
  low_52w: number | null;
  high_52w: number | null;
  initial_investment: number | null;
  market_cap_value: number | null;
  price_change_52w_pct: number | null;
  external_ids: Record<string, string>;
  siblings: SiblingScheme[];
  features: Record<string, number | null>;
  quality_issues: { rule: string; severity: string; detail: Record<string, unknown> }[];
  ingestion_run_id: number;
  data_asof: string | null;
  nav_metrics: { as_of: string; ret_1y: number | null; ret_3y: number | null; ret_5y: number | null; methodology_version: string } | null;
};

export type Horizon = "ytd" | "3m" | "1y" | "3y" | "5y";

export type Overview = {
  ingestion_run_id: number;
  universe: { description: string; include_insurer: boolean };
  counts: {
    schemes_total: number; schemes_in_universe: number; insurer_funds: number; discontinued: number;
    quarantined: number; families: number; amcs: number; categories: number;
  };
  tiers: { tier: string; schemes: number }[];
  returns_1y: { mean: number | null; median: number | null; n: number };
  aum: { total_rupees: number; families_with_aum: number; families_total: number; coverage: number | null; note: string };
  categories: {
    category: string; asset_tier: string; schemes: number; low_sample: boolean;
    median_returns: Record<Horizon, number | null>;
  }[];
  breadth: {
    tier: string; schemes: number; positive_return_share: Record<Horizon, number | null>;
    observations: Record<Horizon, number>; above_50d_avg: number | null; above_200d_avg: number | null;
  }[];
  amc_leaderboard: {
    min_schemes: number; amcs_ranked: number; amcs_in_universe: number;
    rows: { amc: string; schemes_with_3y: number; median_3y_category_percentile: number; families: number; categories: number }[];
  };
  top_performers: { horizon: Horizon; note: string; rows: { id: number; name: string; amc: string; category: string; ret: number; net_assets: number | null }[] };
  top_by_aum: { rows: { id: number; name: string; amc: string; category: string; net_assets: number; return_1y: number | null }[] };
  snapshot_note: string;
};

export type FieldDef = { key: string; label: string; kind: "number" | "category" | "bool"; group: string; unit: string; ops: string[] };
export type FilterOptions = Record<"amcs" | "categories" | "asset_tiers" | "plan_types" | "option_types", { value: string; count: number }[]>;

export type Condition = { field: string; op: string; value?: number | string | boolean | (number | string)[] | null };
export type Group = { op: "and" | "or"; items: (Condition | Group)[] };
export type ScreenRequest = {
  filter: Group; sort: string; order: "asc" | "desc"; page: number; page_size: number; include_quarantined?: boolean;
};
export type ScreenRow = FundSummary & { cat_pct_1y: number | null; cat_pct_3y: number | null; cat_pct_5y: number | null; price_vs_200d: number | null; sharpe_3y: number | null; vol_3y: number | null; max_dd_3y: number | null; nav_ret_3y: number | null; quant_score: number | null };
export type ScreenResult = { items: ScreenRow[]; total: number; page: number; page_size: number; ingestion_run_id: number | null };

export type CompareFund = FundSummary & {
  avg_50d: number | null; avg_200d: number | null; low_52w: number | null; high_52w: number | null;
  initial_investment: number | null; metrics: Record<string, number | null>;
};
export type CompareResult = { funds: CompareFund[]; warnings: string[]; ingestion_run_id: number };

export type Coverage = {
  generated_at: string;
  note?: string;
  register: { run_id: number | null; schemes: number; summary: { latest_nav_date?: string; future_dated?: number; records?: number } | null };
  mapping?: {
    schemes_total: number; status_counts: Record<string, number>; insurer_funds: number; non_insurer_schemes: number;
    non_insurer_status_counts: Record<string, number>; by_asset_tier: Record<string, Record<string, number>>;
    accepted_share_non_insurer: number | null; confirmed_share_non_insurer: number | null;
    distinct_official_codes_accepted: number; slot_conflicts: number; note: string;
  };
  families?: {
    non_insurer_families: number; families_with_accepted_mapping: number; families_with_direct_growth: number;
    direct_growth_mapped: number; direct_growth_mapped_with_3y_history: number;
  };
  nav_history?: {
    accepted_schemes: number; with_history: number; failed: number; not_loaded: number; at_least_1y: number; at_least_3y: number;
    at_least_5y: number; at_least_10y: number; observations_total: number; with_quality_issues: number;
  };
  snapshot_date?: { estimate: string | null; votes: number | null; pairs_used: number | null; method: string };
  return_semantics?: Record<string, { funds_compared: number; median_abs_error_vs_cumulative_pp: number; median_abs_error_vs_annualised_pp?: number; closer_to?: string; share_within_1pp_annualised?: number; share_within_1pp_cumulative: number; aligned_to_snapshot: boolean } | string>;
  unmatched_amcs?: string[];
};

export type MetricT = {
  name: string; value: number | null; unit: string; note: string | null; n_obs: number;
  window_start: string | null; window_end: string | null; coverage: number | null;
};
export type Point = [string, number];
export type RiskBlock = {
  years: number; available: boolean; reason?: string; data_issue?: boolean; window_start?: string; window_end?: string;
  cagr?: MetricT; volatility?: MetricT; downside_deviation?: MetricT; sharpe_ratio?: MetricT; sortino_ratio?: MetricT;
  max_drawdown?: MetricT; calmar_ratio?: MetricT; var_95?: MetricT; cvar_95?: MetricT; var_99?: MetricT; cvar_99?: MetricT;
  var_param_95?: MetricT; skewness?: MetricT; excess_kurtosis?: MetricT;
  drawdown_detail?: { peak_date?: string; trough_date?: string; recovery_date?: string | null; drawdown_days?: number; recovery_days?: number | null; current_drawdown?: number };
  benchmark?: Record<string, MetricT | null>;
};
export type RollingSummary = { n: number; median: number | null; p5: number | null; p95: number | null; best: number | null; worst: number | null; pct_positive: number | null; pct_outperform_benchmark?: MetricT };
export type Analytics = {
  scheme_id: number; name: string; category: string; plan_type: string; option_type: string; amfi_code: string | null;
  available: boolean; reason?: string; methodology_version?: string; benchmark_label?: string; risk_free_label?: string | null; peer_count?: number;
  data_window?: { start: string; end: string; observations: number }; data_issues?: { date: string; move_pct: number }[];
  trailing_returns?: Record<string, MetricT>; calendar_returns?: { year: number; return: number; partial: boolean }[];
  windows?: RiskBlock[]; rolling?: Record<string, RollingSummary>; positive_months?: MetricT;
  chart_years?: number | null;
  charts?: {
    available: boolean; reason?: string;
    cumulative?: { fund: Point[]; category_average?: Point[] }; drawdown?: { fund: Point[]; category_average?: Point[] };
    rolling?: Record<string, Point[]>; rolling_volatility_1y?: Point[];
    nav_chart?: { nav: Point[]; dma_50: Point[]; dma_200: Point[] };
  };
};
export type CompareAnalytics = {
  years: number | null; funds: Analytics[];
  chart: { available: boolean; start?: string; end?: string; cumulative?: Record<string, Point[]>; drawdown?: Record<string, Point[]>; rolling_volatility_1y?: Record<string, Point[]> };
  correlation: { ids: number[]; matrix: number[][]; observations?: number };
};

export type QuantFactor = { key: string; label: string; weight: number; score: number | null; contribution: number | null };
export type QuantMetric = { key: string; label: string; factor: string; higher_is_better: boolean; raw: number | null; percentile: number | null; z: number | null };
export type QuantScore = {
  available: boolean; reason?: string; scheme_id: number; name: string; as_of?: string; methodology_version?: string; peer_group?: string; peers?: number;
  composite?: number | null; coverage?: number | null; rank_in_group?: number | null; scored?: boolean; not_scored_reason?: string | null;
  factors?: QuantFactor[]; metrics?: QuantMetric[]; caveat?: string;
};
export type QuantScoreList = {
  items: { scheme_id: number; name: string; category: string; plan_type: string; asset_tier: string; peer_group: string; peers: number; composite: number | null;
    coverage: number | null; rank_in_group: number | null; factors: Record<string, number | null> }[];
  total: number; page: number; page_size: number; as_of: string | null; methodology_version: string;
};
export type QuantMethodology = {
  version: string; weights: Record<string, number>; factor_labels: Record<string, string>; unavailable: Record<string, string>; rules: string[];
  metrics: { key: string; factor: string; label: string; higher_is_better: boolean }[]; strategies: Record<string, string>;
};
export type IcRow = { signal: string; horizon_months: number; mean_ic: number; ic_std: number; hit_rate: number; dates: number; independent_dates: number;
  t_stat: number | null; top_minus_bottom_pct: number | null; avg_funds: number; first_date: string; last_date: string };
export type QuantFactors = { generated_at: string; scoring_version: string; first_date: string; last_date: string; dates: number; ic: IcRow[];
  persistence: { months: number; observations: number; share_in_top_quartile_next: number | null; random_expectation: number; note: string }; caveats: string[] };
export type QuantStats = { correlations: { keys: string[]; matrix: number[][]; dates?: number }; metric_correlations: { keys: string[]; matrix: number[][] };
  distributions: { metric: string; n: number; mean: number; std: number; p5: number; median: number; p95: number; skew: number; excess_kurtosis: number }[];
  score_by_tier: { tier: string; scored: number; mean: number; p10: number; median: number; p90: number }[] };
export type ClusterMethod = { method: string; clusters: number; silhouette: number | null; noise_points: number; sizes: Record<string, number>;
  centroids: ({ cluster: number; label: string; size: number } & Record<string, number | string>)[]; assignments: Record<string, number> };
export type ClusterTier = { available: boolean; reason?: string; funds: number; features?: string[]; notes?: string[]; names?: Record<string, string>;
  pca?: { explained_variance: number[]; loadings: Record<string, number[]>; points: Record<string, number[]> }; methods?: ClusterMethod[] };
export type RegimeStat = { regime: string; days: number; share: number; annualised_return: number; annualised_vol: number; avg_duration_days: number; episodes: number };
export type Regimes = {
  generated_at: string; proxy: string; start: string; end: string; index: [string, number][];
  current: { trend: string | null; volatility: string | null; hmm: string | null };
  trend: { stats: RegimeStat[]; transitions: { states: string[]; matrix: number[][] }; timeline: { regime: string; start: string; end: string }[]; rule: string };
  volatility: { stats: RegimeStat[]; timeline: { regime: string; start: string; end: string }[]; rule: string };
  hmm: { available?: boolean; reason?: string; stats?: RegimeStat[]; transitions?: { states: string[]; matrix: number[][] }; timeline?: { regime: string; start: string; end: string }[];
    train_end?: string; note?: string; current_probabilities?: Record<string, number> };
  gmm: { stats: RegimeStat[]; hindsight: boolean; note: string };
};
export type BacktestSeg = { available: boolean; reason?: string; start?: string; end?: string; cagr?: number | null; volatility?: number; sharpe?: number | null; max_drawdown?: number };
export type BacktestResult = {
  available: boolean; reason?: string; id?: number; strategy_description?: string; backtest_version?: string; scoring_version?: string;
  period?: { start: string; end: string; years: number }; oos_start?: string; warnings: string[];
  full?: { strategy: BacktestSeg; benchmark: BacktestSeg }; in_sample?: { strategy: BacktestSeg; benchmark: BacktestSeg }; out_of_sample?: { strategy: BacktestSeg; benchmark: BacktestSeg };
  excess?: { cagr_difference_pp: number | null; months: number; monthly_excess_mean_pct: number; t_stat: number | null; annualised_excess_ci95_pp: [number, number] | null; win_rate_pct: number; note: string };
  costs?: { transaction_pct_of_start_value: number; exit_loads_pct_of_start_value: number; avg_annual_turnover_pct: number; avg_holdings: number };
  trades?: { signal: string; execution: string; holdings: number; turnover_pct: number; cost_pct_of_value: number }[]; rebalances?: number;
  curves?: { strategy: [string, number][]; benchmark: [string, number][] }; universe?: { tier: string | null; category: string | null; plan: string; funds: number };
};
export type BacktestRequest = {
  strategy: string; top_n: number; rebalance_months: number; cost_pct: number; exit_load_pct: number; delay_days: number;
  start?: string; end?: string; oos_start?: string; universe: { tier?: string | null; category?: string | null; plan: string };
};

export type PFund = { scheme_id: number; name: string; category: string; plan: string; tier: string };
export type PortfolioFundRow = PFund & { weight_pct: number };
export type PortfolioAnalysis = {
  version: string; funds: PortfolioFundRow[]; rebalance: string; history: { start: string; end: string; observations: number; note: string };
  analytics: Analytics; charts: NonNullable<Analytics["charts"]>;
  allocation: { by_category: { name: string; weight_pct: number }[]; by_tier: { name: string; weight_pct: number }[]; by_plan: { name: string; weight_pct: number }[] };
  risk?: { risk_contribution_pct: number[]; diversification_ratio: number | null; effective_number_of_funds: number; herfindahl: number;
    window: { start: string; end: string; observations: number }; correlation: { codes: number[]; matrix: number[][] };
    stats: { expected_return: number; volatility: number; sharpe: number } };
  warnings: string[];
};
export type OptimizeRequest = {
  scheme_ids: number[]; method: string; lookback_years: number; shrink: number;
  limits: { min_weight_pct?: number; max_weight_pct?: number; max_funds?: number; category_max_pct?: number };
  risk_free_pct?: number; views?: { scheme_id: number; annual_return_pct: number }[];
};
export type PStats = { expected_return: number; volatility: number; sharpe: number };
export type OptimizeResult = {
  version: string; method: string; method_label: string; funds: PortfolioFundRow[]; stats: PStats; equal_weight_stats: PStats;
  risk: { risk_contribution_pct: number[]; diversification_ratio: number | null; effective_number_of_funds: number };
  assumptions: { lookback_years: number; estimation_window: { start: string; end: string; observations: number }; mean_return_shrinkage: number; risk_free_pct: number;
    covariance: string; covariance_shrinkage_intensity: number; condition_number: number };
  frontier?: PStats[]; assets: { scheme_id: number; name: string; expected_return: number; volatility: number }[]; daily_cvar_95_pct?: number;
  holdout: { available: boolean; reason?: string; fit_end?: string; holdout_start?: string; holdout_end?: string; observations?: number; note?: string;
    optimised?: { return: number; volatility: number; sharpe: number | null }; equal_weight?: { return: number; volatility: number; sharpe: number | null } };
  warnings: string[];
};
export type SimResult = Record<string, unknown> & { kind?: string; label: string; available?: boolean; reason?: string; note?: string; target: { type: string; name?: string; funds?: number } };
export type RebalanceResult = {
  total_value: number; threshold_pct: number; rebalance_triggered: boolean; max_drift_pct: number; estimated_fees: number; note: string;
  weights: { scheme_id: number; name: string; current_pct: number; target_pct: number; drift_pct: number }[];
  trades: { scheme_id: number; name: string; action: "buy" | "sell"; amount: number; cost: number; exit_load: number }[];
};
export type StressResult = {
  market_proxy: string; history: { start: string; end: string };
  historical_episodes: { peak: string; trough: string; fall_pct: number; days: number; portfolio_change_pct: number | null; available: boolean; reason: string | null;
    funds: { scheme_id: number; name: string; change_pct: number | null }[] }[];
  hypothetical: { available: boolean; reason?: string; beta?: number; r_squared?: number; scenarios?: { market_shock_pct: number; portfolio_change_pct: number }[]; note?: string };
  notes: string[];
};

export type AmcRow = {
  amc_id: number; amc: string; funds: number; scored_funds: number; categories: number; eligible: boolean; reason: string | null; rank: number | null;
  median_score_percentile: number | null; median_return_percentile: number | null; median_sharpe_percentile: number | null;
  share_above_median: number | null; share_top_quartile: number | null; share_bottom_quartile: number | null;
  concentration_hhi: number; largest_category: string; largest_category_share: number;
};
export type AmcRanking = { version: string; amcs: AmcRow[]; eligible: number; method: string[] };
export type AmcDetail = {
  version: string; summary: AmcRow; note: string;
  categories: { category: string; funds: number; median_score_percentile: number | null; best_percentile: number | null }[];
  funds: { scheme_id: number; name: string; category: string; composite: number | null; p_score: number | null; ret_3y: number | null }[];
};

export type PlatformStats = {
  funds: number | null; fund_houses: number | null; categories: number | null; funds_with_nav_history: number | null; funds_scored: number | null;
  nav_observations: number | null; history_from: string | null; history_to: string | null; strategies_tested: number; score_version: string;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(new URL(path, BASE), {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), cache: "no-store",
  });
  if (!res.ok) {
    let detail = `API ${res.status}`;
    try { const j = await res.json(); if (typeof j.detail === "string") detail = j.detail; else if (j.detail?.[0]?.msg) detail = j.detail[0].msg; } catch {}
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(path, BASE);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `API ${res.status} for ${url.pathname}`);
  return res.json() as Promise<T>;
}

export const api = {
  funds: (params: Record<string, string | number | undefined>) => get<FundList>("/api/v1/funds", params),
  fund: (id: number) => get<FundDetail>(`/api/v1/funds/${id}`),
  overview: (horizon: Horizon = "1y", includeInsurer = false) =>
    get<Overview>("/api/v1/overview", { horizon, include_insurer: String(includeInsurer) }),
  analytics: (id: number, years: string) => get<Analytics>(`/api/v1/analytics/${id}`, { years }),
  analyticsCompare: (ids: number[], years: string) => get<CompareAnalytics>("/api/v1/analytics/compare", { ids: ids.join(","), years }),
  quantMethodology: () => get<QuantMethodology>("/api/v1/quant/methodology"),
  quantScores: (p: Record<string, string | number | undefined>) => get<QuantScoreList>("/api/v1/quant/scores", p),
  quantScore: (id: number) => get<QuantScore>(`/api/v1/quant/scores/${id}`),
  quantGroups: () => get<{ group: string; funds: number; scored: number }[]>("/api/v1/quant/groups"),
  quantFactors: () => get<QuantFactors>("/api/v1/quant/factors"),
  quantStats: () => get<QuantStats>("/api/v1/quant/statistics"),
  quantClusters: () => get<{ clusters: Record<string, ClusterTier>; note: string }>("/api/v1/quant/clusters"),
  quantRegimes: () => get<Regimes>("/api/v1/quant/regimes"),
  submitBacktest: (req: BacktestRequest) => post<{ id: number; status: string }>("/api/v1/quant/backtests", req),
  job: (id: number) => get<{ id: number; status: string; error: string | null }>(`/api/v1/jobs/${id}`),
  backtest: (id: number) => get<BacktestResult>(`/api/v1/quant/backtests/${id}`),
  portfolioFunds: (q: string) => get<PFund[]>("/api/v1/portfolio/funds", { q }),
  portfolioFundsByIds: (ids: number[]) => get<PFund[]>("/api/v1/portfolio/funds", { ids: ids.join(",") }),
  analyzePortfolio: (holdings: { scheme_id: number; weight: number }[], years: string, rebalance = "M") =>
    post<PortfolioAnalysis>("/api/v1/portfolio/analyze", { holdings, years, rebalance }),
  optimize: (req: OptimizeRequest) => post<OptimizeResult>("/api/v1/portfolio/optimize", req),
  simulate: (req: Record<string, unknown>) => post<SimResult>("/api/v1/portfolio/simulate", req),
  rebalance: (req: Record<string, unknown>) => post<RebalanceResult>("/api/v1/portfolio/rebalance", req),
  stress: (holdings: { scheme_id: number; weight: number }[]) => post<StressResult>("/api/v1/portfolio/stress", { holdings }),
  amcs: () => get<AmcRanking>("/api/v1/amcs"),
  amc: (id: number) => get<AmcDetail>(`/api/v1/amcs/${id}`),
  platformStats: () => get<PlatformStats>("/api/v1/platform-stats"),
  coverage: () => get<Coverage>("/api/v1/data-coverage"),
  fields: () => get<FieldDef[]>("/api/v1/screener/fields"),
  filterOptions: () => get<FilterOptions>("/api/v1/filters/options"),
  screen: (req: ScreenRequest) => post<ScreenResult>("/api/v1/screener", req),
  compare: (ids: number[]) => get<CompareResult>("/api/v1/compare", { ids: ids.join(",") }),
  exportCsv: async (req: ScreenRequest): Promise<{ blob: Blob; truncated: boolean }> => {
    const res = await fetch(new URL("/api/v1/screener/export", BASE), {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(req),
    });
    if (!res.ok) throw new ApiError(res.status, `Export failed (${res.status})`);
    return { blob: await res.blob(), truncated: res.headers.get("x-truncated") === "true" };
  },
};
