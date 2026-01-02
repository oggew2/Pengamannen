import type { StrategyMeta, RankedStock, PortfolioResponse, RebalanceDate, StockDetail, BacktestRequest, BacktestResult, CombinerRequest } from '../types';

const BASE_URL = '/v1';

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('authToken');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    ...options,
    headers: { ...getAuthHeaders(), ...options?.headers }
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
  
  getStrategies: () => fetchJson<StrategyMeta[]>('/v1/strategies'),
  getStrategyRankings: (name: string) => fetchJson<RankedStock[]>(`/v1/strategies/${name}`),
  getStrategyTop10: (name: string) => fetchJson<RankedStock[]>(`/v1/strategies/${name}/top10`),
  getPortfolio: () => fetchJson<PortfolioResponse>('/v1/portfolio/sverige'),
  getRebalanceDates: () => fetchJson<RebalanceDate[]>('/v1/portfolio/rebalance-dates'),
  getStock: (ticker: string) => fetchJson<StockDetail>(`/v1/stocks/${encodeURIComponent(ticker)}`),
  getStockPrices: (ticker: string, days?: number) => fetchJson<{prices: Array<{date: string; close: number}>}>(`/v1/stocks/${encodeURIComponent(ticker)}/prices${days ? `?days=${days}` : ''}`),
  
  // Data integrity - CRITICAL for trading
  getDataIntegrity: () => fetchJson<DataIntegrityResponse>('/v1/data/integrity/quick'),
  getDataIntegrityFull: () => fetchJson<DataIntegrityFullResponse>('/v1/data/integrity'),
  validateStrategy: (name: string) => fetchJson<StrategyValidation>(`/v1/strategies/${name}/validate`),
  
  // Rebalancing endpoints
  getRebalanceTrades: (strategy: string, portfolioValue: number, currentHoldings?: Array<{ticker: string; shares: number; value: number}>) => 
    postJson<RebalanceTradesResponse>(`/v1/rebalance/trades?strategy=${encodeURIComponent(strategy)}&portfolio_value=${portfolioValue}`, currentHoldings || []),
  sendRebalanceReminder: (email: string, strategy: string) =>
    postJson<{message: string}>(`/v1/notifications/rebalance-reminder?email=${encodeURIComponent(email)}&strategy=${encodeURIComponent(strategy)}`, {}),
  
  // Other endpoints
  combinePortfolio: (req: CombinerRequest) => postJson<PortfolioResponse>('/v1/portfolio/combiner', req),
  runBacktest: (req: BacktestRequest) => postJson<BacktestResult>('/v1/backtesting/run', req),
  getBacktestResults: (strategy: string) => fetchJson<BacktestResult[]>(`/v1/backtesting/results/${strategy}`),
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

// Data integrity types
export interface DataIntegrityResponse {
  safe_to_trade: boolean;
  status: 'OK' | 'WARNING' | 'CRITICAL';
  recommendation: string;
  critical_issues: Array<{ type: string; message: string }>;
  warning_count: number;
}

export interface DataIntegrityFullResponse {
  status: 'OK' | 'WARNING' | 'CRITICAL';
  recommendation: string;
  safe_to_trade: boolean;
  checked_at: string;
  checks: Record<string, { status: string; message: string }>;
  issues: Array<{ type: string; message: string }>;
  warnings: Array<{ type: string; message: string }>;
}

export interface StrategyValidation {
  strategy: string;
  safe_to_trade: boolean;
  message: string;
  issues: Array<{ type: string; message: string }>;
  checked_at: string;
}
