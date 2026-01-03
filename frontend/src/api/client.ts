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
  getPortfolio: () => fetchJson<PortfolioResponse>('/portfolio/sverige'),
  getRebalanceDates: () => fetchJson<RebalanceDate[]>('/portfolio/rebalance-dates'),
  getStock: (ticker: string) => fetchJson<StockDetail>(`/stocks/${encodeURIComponent(ticker)}`),
  getStockPrices: (ticker: string, days?: number) => fetchJson<{prices: Array<{date: string; close: number}>}>(`/stocks/${encodeURIComponent(ticker)}/prices${days ? `?days=${days}` : ''}`),
  
  // Rebalancing
  getRebalanceTrades: (strategy: string, portfolioValue: number, currentHoldings?: Array<{ticker: string; shares: number; value: number}>) => 
    postJson<RebalanceTradesResponse>(`/rebalance/trades?strategy=${encodeURIComponent(strategy)}&portfolio_value=${portfolioValue}`, currentHoldings || []),
  
  // Backtesting
  runBacktest: (req: BacktestRequest) => postJson<BacktestResult>('/backtesting/run', req),
};

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
