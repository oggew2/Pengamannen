import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from './client';
import type { BacktestRequest } from '../types';

// Query Keys - factory pattern for type safety
export const queryKeys = {
  strategies: {
    all: ['strategies'] as const,
    list: () => [...queryKeys.strategies.all, 'list'] as const,
    rankings: (name: string) => [...queryKeys.strategies.all, 'rankings', name] as const,
  },
  stocks: {
    all: ['stocks'] as const,
    detail: (ticker: string) => [...queryKeys.stocks.all, ticker] as const,
    prices: (ticker: string, days?: number) => [...queryKeys.stocks.all, ticker, 'prices', days] as const,
  },
  portfolio: {
    all: ['portfolio'] as const,
    holdings: () => [...queryKeys.portfolio.all, 'holdings'] as const,
    rebalanceDates: () => [...queryKeys.portfolio.all, 'rebalance-dates'] as const,
  },
  data: {
    syncHistory: (days: number) => ['data', 'sync-history', days] as const,
    status: () => ['data', 'status'] as const,
  },
  backtest: {
    run: (params: BacktestRequest) => ['backtest', params.strategy_name, params.start_date, params.end_date] as const,
  },
  dividends: {
    upcoming: (days: number) => ['dividends', 'upcoming', days] as const,
  },
  alerts: {
    all: ['alerts'] as const,
  },
};

// Hooks
export function useStrategies() {
  return useQuery({
    queryKey: queryKeys.strategies.list(),
    queryFn: api.getStrategies,
  });
}

export function useStrategyRankings<T = Awaited<ReturnType<typeof api.getStrategyRankings>>>(
  name: string,
  options?: { select?: (data: Awaited<ReturnType<typeof api.getStrategyRankings>>) => T }
) {
  return useQuery({
    queryKey: queryKeys.strategies.rankings(name),
    queryFn: () => api.getStrategyRankings(name),
    enabled: !!name,
    select: options?.select,
  });
}

export function useStock(ticker: string) {
  return useQuery({
    queryKey: queryKeys.stocks.detail(ticker),
    queryFn: () => api.getStock(ticker),
    enabled: !!ticker,
  });
}

export function useStockPrices(ticker: string, days?: number) {
  return useQuery({
    queryKey: queryKeys.stocks.prices(ticker, days),
    queryFn: () => api.getStockPrices(ticker, days),
    enabled: !!ticker,
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: queryKeys.portfolio.holdings(),
    queryFn: api.getPortfolio,
  });
}

export function useRebalanceDates() {
  return useQuery({
    queryKey: queryKeys.portfolio.rebalanceDates(),
    queryFn: api.getRebalanceDates,
  });
}

export interface SyncHistoryResponse {
  sync_logs: Array<{
    id: number;
    sync_type: string;
    status: string;
    started_at: string;
    completed_at: string | null;
    duration_seconds: number | null;
    stocks_updated: number | null;
    prices_updated: number | null;
    error_message: string | null;
  }>;
  next_scheduled_sync: string | null;
  success_count: number;
  fail_count: number;
}

export function useSyncHistory(days = 1) {
  return useQuery({
    queryKey: queryKeys.data.syncHistory(days),
    queryFn: () => api.get<SyncHistoryResponse>(`/data/sync-history?days=${days}`),
    staleTime: 60 * 1000, // 1 min - sync status can be checked more frequently
  });
}

export function useBacktest(params: BacktestRequest, enabled = true) {
  return useQuery({
    queryKey: queryKeys.backtest.run(params),
    queryFn: () => api.runBacktest(params),
    enabled,
    staleTime: 30 * 60 * 1000, // 30 min - backtests are expensive
    gcTime: 60 * 60 * 1000,    // 1 hour
  });
}

export interface DividendEvent {
  ticker: string;
  name: string | null;
  ex_date: string;
  amount: number;
  currency: string;
}

export function useDividends(daysAhead = 90) {
  return useQuery({
    queryKey: queryKeys.dividends.upcoming(daysAhead),
    queryFn: () => api.get<DividendEvent[]>(`/dividends/upcoming?days_ahead=${daysAhead}`),
  });
}

export interface Alert {
  id: number;
  type: string;
  message: string;
  created_at: string;
  resolved: boolean;
}

export function useAlerts() {
  return useQuery({
    queryKey: queryKeys.alerts.all,
    queryFn: () => api.get<Alert[]>('/alerts'),
  });
}

// Multi-user support: clear cache on logout
export function useClearCache() {
  const queryClient = useQueryClient();
  return () => queryClient.clear();
}

// Mutation hooks for data operations
export function useSyncData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post('/data/sync-now?region=sweden&market_cap=large&method=avanza', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.data.status() });
      queryClient.invalidateQueries({ queryKey: queryKeys.strategies.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.stocks.all });
    },
  });
}

export interface ScanResult {
  new_stocks_found: number;
  new_stocks: Array<{ ticker: string; name: string }>;
}

export function useScanStocks() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ threads, ranges }: { threads: number; ranges?: Array<{ start: number; end: number }> }) =>
      api.post<ScanResult>(`/data/stocks/scan?threads=${threads}`, { ranges }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.stocks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.data.status() });
    },
  });
}

export function useSyncPrices() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (years: number) =>
      api.post<{ stocks_synced: number; years: number }>(`/data/sync-prices-extended?threads=3&years=${years}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.stocks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.data.status() });
    },
  });
}
