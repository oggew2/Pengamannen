import type { StrategyMeta, RankedStock, PortfolioResponse, RebalanceDate, StockDetail, BacktestRequest, BacktestResult } from '../types';

const BASE_URL = '/v1';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    credentials: 'include',  // Include httpOnly cookies
    headers: { ...options?.headers }
  });
  if (!res.ok) {
    throw new ApiError(res.status, `API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return fetchJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

export const api = {
  get: <T>(url: string) => fetchJson<T>(url),
  post: <T>(url: string, body: unknown) => postJson<T>(url, body),
  
  getStrategies: () => fetchJson<StrategyMeta[]>('/strategies'),
  getStrategyRankings: (name: string) => fetchJson<RankedStock[]>(`/strategies/${name}`),
  getStrategyTop10: (name: string) => fetchJson<RankedStock[]>(`/strategies/${name}/top10`),
  getNordicMomentum: () => fetchJson<{ rankings: RankedStock[]; computed_at?: string }>('/strategies/nordic/momentum'),
  getPortfolio: () => fetchJson<PortfolioResponse>('/portfolio/sverige'),
  getRebalanceDates: () => fetchJson<RebalanceDate[]>('/portfolio/rebalance-dates'),
  getStock: (ticker: string) => fetchJson<StockDetail>(`/stocks/${encodeURIComponent(ticker)}`),
  getStockPrices: (ticker: string, days?: number) => fetchJson<{prices: Array<{date: string; close: number}>}>(`/stocks/${encodeURIComponent(ticker)}/prices${days ? `?days=${days}` : ''}`),
  
  // Rebalancing
  getRebalanceTrades: (strategy: string, portfolioValue: number, currentHoldings?: Array<{ticker: string; shares: number; value: number}>) => 
    postJson<RebalanceTradesResponse>(`/rebalance/trades?strategy=${encodeURIComponent(strategy)}&portfolio_value=${portfolioValue}`, currentHoldings || []),
  
  // Backtesting
  runBacktest: (req: BacktestRequest) => postJson<BacktestResult>('/backtesting/run', req),
  
  // Nordic allocation
  calculateAllocation: (amount: number, excludedTickers?: string[], forceIncludeTickers?: string[]) => 
    postJson<AllocationResponse>('/strategies/nordic/momentum/allocate', { amount, excluded_tickers: excludedTickers || [], force_include_tickers: forceIncludeTickers || [] }),
  
  // Nordic rebalance (banding mode)
  calculateRebalance: (holdings: { ticker: string; shares: number }[], newInvestment: number) =>
    postJson<RebalanceResponse>('/strategies/nordic/momentum/rebalance', { holdings, new_investment: newInvestment }),
};

// Allocation types
export interface AllocationStock {
  rank: number;
  ticker: string;
  name: string;
  price: number;
  shares: number;
  target_amount: number;
  actual_amount: number;
  target_weight: number;
  actual_weight: number;
  deviation: number;
  too_expensive: boolean;
  included: boolean;
}

export interface AllocationResponse {
  investment_amount: number;
  target_per_stock: number;
  allocations: AllocationStock[];
  summary: {
    total_invested: number;
    cash_remaining: number;
    utilization: number;
    stocks_included: number;
    stocks_skipped: number;
    max_deviation: number;
    commission_start?: number;
    commission_mini?: number;
    commission_small?: number;
  };
  warnings: string[];
  substitutes?: Array<{ rank: number; ticker: string; name: string; price: number }>;
  optimal_amounts?: Array<{ amount: number; max_deviation: number }>;
}

// Rebalance (banding) types
export interface RebalanceHolding {
  ticker: string;
  shares: number;
  price: number;
  value: number;
  rank: number | null;
}

export interface RebalanceSell extends RebalanceHolding {
  reason: 'not_in_universe' | 'below_threshold';
}

export interface RebalanceBuy {
  ticker: string;
  name: string;
  rank: number;
  price: number;
  shares: number;
  value: number;
}

export interface RebalanceResponse {
  mode: 'banding';
  current_holdings_count: number;
  hold: RebalanceHolding[];
  sell: RebalanceSell[];
  buy: RebalanceBuy[];
  final_portfolio: Array<RebalanceHolding & { action: 'HOLD' | 'BUY'; weight: number }>;
  summary: {
    stocks_held: number;
    stocks_sold: number;
    stocks_bought: number;
    sell_proceeds: number;
    new_investment: number;
    total_cash_used: number;
    cash_remaining: number;
    final_portfolio_value: number;
    final_stock_count: number;
  };
}

// Rebalancing types
export interface RebalanceTrade {
  ticker: string;
  action: 'BUY' | 'SELL';
  shares: number;
  amount_sek: number;
  price: number | null;
  isin: string | null;
}

export interface RebalanceTradesResponse {
  strategy: string;
  portfolio_value: number;
  target_stocks: string[];
  trades: RebalanceTrade[];
  total_buys: number;
  total_sells: number;
  costs: {
    courtage: number;
    spread_estimate: number;
    total: number;
    percentage: number;
  };
}
