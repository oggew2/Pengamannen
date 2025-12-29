import type { StrategyMeta, RankedStock, PortfolioResponse, RebalanceDate, StockDetail, BacktestRequest, BacktestResult, CombinerRequest } from '../types';

const BASE_URL = import.meta.env.DEV ? '/api' : '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, options);
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
  getStrategies: () => fetchJson<StrategyMeta[]>('/strategies'),
  getStrategyRankings: (name: string) => fetchJson<RankedStock[]>(`/strategies/${name}`),
  getStrategyTop10: (name: string) => fetchJson<RankedStock[]>(`/strategies/${name}/top10`),
  getPortfolio: () => fetchJson<PortfolioResponse>('/portfolio/sverige'),
  getRebalanceDates: () => fetchJson<RebalanceDate[]>('/portfolio/rebalance-dates'),
  getStock: (ticker: string) => fetchJson<StockDetail>(`/stocks/${ticker}`),
  
  // New endpoints
  combinePortfolio: (req: CombinerRequest) => postJson<PortfolioResponse>('/portfolio/combiner', req),
  runBacktest: (req: BacktestRequest) => postJson<BacktestResult>('/backtesting/run', req),
  getBacktestResults: (strategy: string) => fetchJson<BacktestResult[]>(`/backtesting/results/${strategy}`),
};
