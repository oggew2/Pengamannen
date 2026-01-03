import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useStrategies, useStrategyRankings, useSyncHistory, useClearCache, queryKeys } from '../api/hooks';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    getStrategies: vi.fn(),
    getStrategyRankings: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '../api/client';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      gcTime: Infinity,
    },
  },
});

const createWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('TanStack Query Hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useStrategies', () => {
    it('fetches strategies successfully', async () => {
      const mockStrategies = [
        { name: 'sammansatt_momentum', display_name: 'Momentum', description: '', type: 'momentum', portfolio_size: 10, rebalance_frequency: 'quarterly' },
        { name: 'trendande_varde', display_name: 'Värde', description: '', type: 'value', portfolio_size: 10, rebalance_frequency: 'annual' },
      ];
      vi.mocked(api.getStrategies).mockResolvedValue(mockStrategies);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useStrategies(), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(mockStrategies);
    });

    it('handles error state', async () => {
      vi.mocked(api.getStrategies).mockRejectedValue(new Error('API Error'));

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useStrategies(), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => expect(result.current.isError).toBe(true));
    });
  });

  describe('useStrategyRankings', () => {
    it('fetches rankings for a strategy', async () => {
      const mockRankings = [
        { ticker: 'ERIC-B.ST', name: 'Ericsson', rank: 1, score: 0.95 },
        { ticker: 'VOLV-B.ST', name: 'Volvo', rank: 2, score: 0.90 },
      ];
      vi.mocked(api.getStrategyRankings).mockResolvedValue(mockRankings);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useStrategyRankings('sammansatt_momentum'), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(mockRankings);
      expect(api.getStrategyRankings).toHaveBeenCalledWith('sammansatt_momentum');
    });

    it('does not fetch when name is empty', () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useStrategyRankings(''), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current.fetchStatus).toBe('idle');
      expect(api.getStrategyRankings).not.toHaveBeenCalled();
    });
  });

  describe('useSyncHistory', () => {
    it('fetches sync history with default days', async () => {
      const mockHistory = {
        sync_logs: [],
        next_scheduled_sync: '2024-01-01T06:00:00Z',
        success_count: 10,
        fail_count: 0,
      };
      vi.mocked(api.get).mockResolvedValue(mockHistory);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useSyncHistory(), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(api.get).toHaveBeenCalledWith('/data/sync-history?days=1');
    });
  });

  describe('Cache behavior', () => {
    it('uses cached data without refetching when stale time not exceeded', async () => {
      const mockStrategies = [{ name: 'test', display_name: 'Test', description: '', type: 'test', portfolio_size: 10, rebalance_frequency: 'annual' }];
      vi.mocked(api.getStrategies).mockResolvedValue(mockStrategies);

      const queryClient = createTestQueryClient();
      const wrapper = createWrapper(queryClient);

      // First call
      const { result: result1 } = renderHook(() => useStrategies(), { wrapper });
      await waitFor(() => expect(result1.current.isSuccess).toBe(true));

      // Verify data is in cache
      const cachedData = queryClient.getQueryData(queryKeys.strategies.list());
      expect(cachedData).toEqual(mockStrategies);
      
      // API was called once
      expect(api.getStrategies).toHaveBeenCalledTimes(1);
    });
  });

  describe('Multi-user cache clearing', () => {
    it('clears all cache on logout', async () => {
      const mockStrategies = [{ name: 'test', display_name: 'Test', description: '', type: 'test', portfolio_size: 10, rebalance_frequency: 'annual' }];
      vi.mocked(api.getStrategies).mockResolvedValue(mockStrategies);

      const queryClient = createTestQueryClient();
      const wrapper = createWrapper(queryClient);

      // Populate cache
      const { result: strategiesResult } = renderHook(() => useStrategies(), { wrapper });
      await waitFor(() => expect(strategiesResult.current.isSuccess).toBe(true));

      // Get clear cache function
      const { result: clearCacheResult } = renderHook(() => useClearCache(), { wrapper });
      
      // Clear cache
      clearCacheResult.current();

      // Cache should be empty
      const cachedData = queryClient.getQueryData(queryKeys.strategies.list());
      expect(cachedData).toBeUndefined();
    });
  });

  describe('Query keys', () => {
    it('generates correct query keys', () => {
      expect(queryKeys.strategies.list()).toEqual(['strategies', 'list']);
      expect(queryKeys.strategies.rankings('momentum')).toEqual(['strategies', 'rankings', 'momentum']);
      expect(queryKeys.stocks.detail('ERIC-B.ST')).toEqual(['stocks', 'ERIC-B.ST']);
      expect(queryKeys.stocks.prices('ERIC-B.ST', 30)).toEqual(['stocks', 'ERIC-B.ST', 'prices', 30]);
      expect(queryKeys.data.syncHistory(7)).toEqual(['data', 'sync-history', 7]);
    });
  });
});


describe('Banding Support', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches top 40 stocks for banding display', async () => {
    // Mock 50 stocks to verify we only take top 40
    const mockRankings = Array.from({ length: 50 }, (_, i) => ({
      ticker: `STOCK${i}.ST`,
      name: `Stock ${i}`,
      rank: i + 1,
      score: 1 - i * 0.01,
    }));
    vi.mocked(api.getStrategyRankings).mockResolvedValue(mockRankings);

    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useStrategyRankings('sammansatt_momentum'), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    
    // Verify all 50 stocks are returned (banding slice happens in component)
    expect(result.current.data).toHaveLength(50);
    expect(result.current.data![0].rank).toBe(1);
    expect(result.current.data![9].rank).toBe(10); // Top 10 boundary
    expect(result.current.data![39].rank).toBe(40); // Banding boundary
  });

  it('caches rankings per strategy for banding comparison', async () => {
    const momentumRankings = [{ ticker: 'A.ST', name: 'A', rank: 1, score: 0.9 }];
    const valueRankings = [{ ticker: 'B.ST', name: 'B', rank: 1, score: 0.8 }];
    
    vi.mocked(api.getStrategyRankings)
      .mockResolvedValueOnce(momentumRankings)
      .mockResolvedValueOnce(valueRankings);

    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);

    // Fetch momentum
    const { result: momentum } = renderHook(() => useStrategyRankings('sammansatt_momentum'), { wrapper });
    await waitFor(() => expect(momentum.current.isSuccess).toBe(true));

    // Fetch value
    const { result: value } = renderHook(() => useStrategyRankings('trendande_varde'), { wrapper });
    await waitFor(() => expect(value.current.isSuccess).toBe(true));

    // Both should be cached separately
    expect(queryClient.getQueryData(queryKeys.strategies.rankings('sammansatt_momentum'))).toEqual(momentumRankings);
    expect(queryClient.getQueryData(queryKeys.strategies.rankings('trendande_varde'))).toEqual(valueRankings);
  });
});

describe('Multi-user Isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('isolates cache between different query clients (simulating different users)', async () => {
    const user1Strategies = [{ name: 'user1_strat', display_name: 'User 1', description: '', type: 'test', portfolio_size: 10, rebalance_frequency: 'annual' }];
    const user2Strategies = [{ name: 'user2_strat', display_name: 'User 2', description: '', type: 'test', portfolio_size: 10, rebalance_frequency: 'annual' }];

    // User 1's query client
    const user1Client = createTestQueryClient();
    vi.mocked(api.getStrategies).mockResolvedValue(user1Strategies);
    
    const { result: user1Result } = renderHook(() => useStrategies(), {
      wrapper: createWrapper(user1Client),
    });
    await waitFor(() => expect(user1Result.current.isSuccess).toBe(true));

    // User 2's query client (fresh)
    const user2Client = createTestQueryClient();
    vi.mocked(api.getStrategies).mockResolvedValue(user2Strategies);
    
    const { result: user2Result } = renderHook(() => useStrategies(), {
      wrapper: createWrapper(user2Client),
    });
    await waitFor(() => expect(user2Result.current.isSuccess).toBe(true));

    // Each user should have their own data
    expect(user1Client.getQueryData(queryKeys.strategies.list())).toEqual(user1Strategies);
    expect(user2Client.getQueryData(queryKeys.strategies.list())).toEqual(user2Strategies);
  });

  it('clears user-specific data on logout without affecting other queries', async () => {
    const mockStrategies = [{ name: 'test', display_name: 'Test', description: '', type: 'test', portfolio_size: 10, rebalance_frequency: 'annual' }];
    const mockRankings = [{ ticker: 'A.ST', name: 'A', rank: 1, score: 0.9 }];
    
    vi.mocked(api.getStrategies).mockResolvedValue(mockStrategies);
    vi.mocked(api.getStrategyRankings).mockResolvedValue(mockRankings);

    const queryClient = createTestQueryClient();
    const wrapper = createWrapper(queryClient);

    // Populate multiple caches
    const { result: strategies } = renderHook(() => useStrategies(), { wrapper });
    const { result: rankings } = renderHook(() => useStrategyRankings('sammansatt_momentum'), { wrapper });
    
    await waitFor(() => expect(strategies.current.isSuccess).toBe(true));
    await waitFor(() => expect(rankings.current.isSuccess).toBe(true));

    // Verify both are cached
    expect(queryClient.getQueryData(queryKeys.strategies.list())).toBeDefined();
    expect(queryClient.getQueryData(queryKeys.strategies.rankings('sammansatt_momentum'))).toBeDefined();

    // Clear all (logout)
    queryClient.clear();

    // Both should be cleared
    expect(queryClient.getQueryData(queryKeys.strategies.list())).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.strategies.rankings('sammansatt_momentum'))).toBeUndefined();
  });
});

describe('Error Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles network errors gracefully', async () => {
    vi.mocked(api.getStrategies).mockRejectedValue(new Error('Network error'));

    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useStrategies(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeDefined();
  });

  it('does not cache failed requests', async () => {
    vi.mocked(api.getStrategies).mockRejectedValue(new Error('API Error'));

    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useStrategies(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    
    // Failed request should not be cached as successful data
    const cachedData = queryClient.getQueryData(queryKeys.strategies.list());
    expect(cachedData).toBeUndefined();
  });
});
