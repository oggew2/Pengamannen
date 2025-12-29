export interface StrategyMeta {
  name: string;
  display_name: string;
  description: string;
  type: string;
  portfolio_size: number;
  rebalance_frequency: string;
  backtest_annual_return_pct?: number;
  backtest_sharpe?: number;
  backtest_max_drawdown_pct?: number;
}

export interface RankedStock {
  ticker: string;
  name: string | null;
  rank: number;
  score: number;
}

export interface PortfolioHolding {
  ticker: string;
  name: string | null;
  weight: number;
  strategy: string;
}

export interface PortfolioResponse {
  holdings: PortfolioHolding[];
  as_of_date: string;
  next_rebalance_date: string | null;
}

export interface RebalanceDate {
  strategy_name: string;
  next_date: string;
}

export interface StockDetail {
  ticker: string;
  name: string | null;
  market_cap: number | null;
  sector: string | null;
  industry: string | null;
  pe: number | null;
  pb: number | null;
  ps: number | null;
  pfcf: number | null;
  ev_ebitda: number | null;
  roe: number | null;
  roa: number | null;
  roic: number | null;
  fcfroe: number | null;
  dividend_yield: number | null;
  payout_ratio: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_12m: number | null;
}

export interface BacktestRequest {
  strategy_name: string;
  start_date: string;
  end_date: string;
}

export interface BacktestResult {
  strategy_name: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  sharpe: number;
  max_drawdown_pct: number;
  portfolio_values?: number[];
}

export interface CombinerRequest {
  strategies: string[];
  weights?: number[];
}

export interface SavedCombination {
  name: string;
  weights: Record<string, number>;
  createdAt: string;
}
