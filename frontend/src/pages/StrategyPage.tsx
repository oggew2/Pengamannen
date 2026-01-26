import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Box, Flex, Text, Button, HStack, VStack, Skeleton } from '@chakra-ui/react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { useStrategies, useBacktest } from '../api/hooks';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import { AllocationCalculator } from '../components/AllocationCalculator';
import { PortfolioTracker } from '../components/PortfolioTracker';
import type { StrategyMeta } from '../types';

const STRATEGY_INFO: Record<string, { description: string; rules: string[] }> = {
  sammansatt_momentum: {
    description: 'Selects the top 10 stocks by momentum (3m, 6m, 12m average returns) filtered by Piotroski F-Score quality gate.',
    rules: ['Ranks stocks by composite momentum score', 'Filters by F-Score ≥ 5', 'Equal-weighted 10 stock portfolio', 'Rebalances quarterly (Mar, Jun, Sep, Dec)']
  },
  trendande_varde: {
    description: 'Combines 6 value metrics (P/E, P/B, P/S, EV/EBITDA, P/FCF, Dividend Yield) with momentum trend filter.',
    rules: ['6-factor value composite score', 'Top 10% by value → rank by momentum', 'Equal-weighted 10 stock portfolio', 'Rebalances annually (March)']
  },
  trendande_utdelning: {
    description: 'Focuses on high dividend yield stocks with positive price momentum to avoid value traps.',
    rules: ['Ranks by dividend yield', 'Top 10% by yield → rank by momentum', 'Equal-weighted 10 stock portfolio', 'Rebalances annually (March)']
  },
  trendande_kvalitet: {
    description: 'Selects high-quality companies using 4-factor ROI (ROE, ROA, ROIC, FCFROE) with momentum filter.',
    rules: ['4-factor quality composite (ROE, ROA, ROIC, FCFROE)', 'Top 10% by quality → rank by momentum', 'Equal-weighted 10 stock portfolio', 'Rebalances annually (March)']
  }
};

export function StrategyPage() {
  const { type } = useParams<{ type: string }>();
  const [rankingsPage, setRankingsPage] = useState(1);

  const apiName = type === 'momentum' ? 'sammansatt_momentum' 
    : type === 'value' ? 'trendande_varde'
    : type === 'dividend' ? 'trendande_utdelning'
    : type === 'quality' ? 'trendande_kvalitet' : '';

  // Use Nordic endpoint for momentum, old endpoint for others
  const isMomentum = type === 'momentum';
  const { data: nordicResponse, isLoading: nordicLoading, isError: nordicError } = useQuery({
    queryKey: ['nordic', 'momentum'],
    queryFn: () => api.getNordicMomentum(),
    enabled: isMomentum,
  });
  
  const stocks = isMomentum ? (nordicResponse?.rankings?.slice(0, 40) || []) : [];
  const computedAt = nordicResponse?.computed_at;
  const rankingsLoading = isMomentum ? nordicLoading : false;
  const rankingsError = isMomentum ? nordicError : false;
  
  const { data: strategies = [] } = useStrategies();
  
  // Backtest params
  const endDate = new Date().toISOString().split('T')[0];
  const startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const { data: backtest } = useBacktest({ strategy_name: apiName, start_date: startDate, end_date: endDate }, !!apiName);

  const strategy = strategies.find((s: StrategyMeta) => s.name === apiName) || null;

  // For momentum, we already have performance data from TradingView - no need to fetch stock details

  // Build chart data from backtest
  const chartData = useMemo(() => {
    if (!backtest?.portfolio_values?.length) return [];
    const startDateObj = new Date(backtest.start_date);
    return backtest.portfolio_values.map((v: number, i: number) => ({ 
      date: new Date(startDateObj.getTime() + i * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], 
      value: ((v / backtest.portfolio_values![0]) - 1) * 100
    }));
  }, [backtest]);

  const backtestResult = backtest ? {
    total_return_pct: backtest.total_return_pct,
    sharpe: backtest.sharpe,
    max_drawdown_pct: backtest.max_drawdown_pct,
  } : null;

  const info = STRATEGY_INFO[apiName];

  if (rankingsError) {
    return (
      <VStack gap="24px" align="stretch">
        <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="8px" p="16px">
          <Text color="red.400" fontWeight="semibold">Failed to load strategy rankings</Text>
          <Text color="fg.muted" fontSize="sm">Please check your connection and try again.</Text>
        </Box>
      </VStack>
    );
  }

  if (rankingsLoading) {
    return (
      <VStack gap="24px" align="stretch">
        <Skeleton height="200px" borderRadius="8px" />
        <Skeleton height="300px" borderRadius="8px" />
        <Skeleton height="400px" borderRadius="8px" />
      </VStack>
    );
  }

  if (!strategy || !info) {
    return <Text color="error.500">Strategy not found</Text>;
  }

  return (
    <VStack gap="24px" align="stretch">
      {/* DataIntegrityBanner only for non-momentum (Avanza data) */}
      {!isMomentum && <DataIntegrityBanner />}
      
      {/* Header */}
      <Box>
        <Link to="/">
          <Text fontSize="sm" color="brand.500" mb="8px">← Back to Dashboard</Text>
        </Link>
        <Text fontSize="2xl" fontWeight="bold" color="fg">{strategy.display_name}</Text>
      </Box>

      {/* Strategy Overview */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="12px">How It Works</Text>
        <Text fontSize="sm" color="fg.muted" mb="16px">{info.description}</Text>
        
        <HStack gap="24px" flexWrap="wrap" mb="16px">
          <VStack align="start" gap="2px">
            <Text fontSize="xs" color="fg.muted">Rebalancing</Text>
            <Text fontSize="sm" color="fg" fontWeight="medium">{strategy.rebalance_frequency}</Text>
          </VStack>
          <VStack align="start" gap="2px">
            <Text fontSize="xs" color="fg.muted">Holdings</Text>
            <Text fontSize="sm" color="fg" fontWeight="medium">{strategy.portfolio_size} stocks</Text>
          </VStack>
          <VStack align="start" gap="2px">
            <Text fontSize="xs" color="fg.muted">1Y Return</Text>
            <Text fontSize="sm" color={backtestResult && backtestResult.total_return_pct >= 0 ? 'success.500' : 'error.500'} fontWeight="medium">
              {backtestResult ? `${backtestResult.total_return_pct >= 0 ? '+' : ''}${backtestResult.total_return_pct.toFixed(1)}%` : '—'}
            </Text>
          </VStack>
          <VStack align="start" gap="2px">
            <Text fontSize="xs" color="fg.muted">Sharpe</Text>
            <Text fontSize="sm" color="fg" fontWeight="medium">
              {backtestResult ? backtestResult.sharpe.toFixed(2) : '—'}
            </Text>
          </VStack>
          <VStack align="start" gap="2px">
            <Text fontSize="xs" color="fg.muted">Max DD</Text>
            <Text fontSize="sm" color="error.500" fontWeight="medium">
              {backtestResult ? `${backtestResult.max_drawdown_pct.toFixed(1)}%` : '—'}
            </Text>
          </VStack>
        </HStack>

        <Text fontSize="sm" fontWeight="semibold" color="fg" mb="8px">Rules</Text>
        <VStack align="start" gap="4px">
          {info.rules.map((rule, i) => (
            <Text key={i} fontSize="xs" color="fg.muted">• {rule}</Text>
          ))}
        </VStack>
      </Box>

      {/* Performance Chart */}
      {chartData.length > 0 && (
        <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="8px" p="24px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Historical Performance</Text>
          <Box height="250px">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
                <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v.toFixed(0)}%`} />
                <Tooltip contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }} />
                <Line type="monotone" dataKey="value" stroke="#00b4d8" strokeWidth={2} dot={false} name="Return" />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        </Box>
      )}

      {/* Current Holdings */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="8px" p="24px">
        <Flex justify="space-between" align="center" mb="16px">
          <HStack gap="8px">
            <Text fontSize="lg" fontWeight="semibold" color="fg">Rankings</Text>
            {computedAt && (
              <Text fontSize="xs" color="fg.muted">
                • {new Date(computedAt).toLocaleString('sv-SE', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </Text>
            )}
            <HStack gap="4px">
              {['1-10', '11-20', '21-30', '31-40'].map((range, idx) => (
                <Button key={range} size="xs" variant={rankingsPage === idx + 1 ? 'solid' : 'outline'} onClick={() => setRankingsPage(idx + 1)}>
                  {range}
                </Button>
              ))}
            </HStack>
          </HStack>
          <Button size="sm" variant="outline" borderColor="brand.500" color="brand.500" onClick={() => {
            const start = (rankingsPage - 1) * 10;
            const csv = ['Rank,Ticker,Name,3M,6M,12M', ...stocks.slice(start, start + 10).map((s: any) => {
              return `${s.rank},${s.ticker},${s.name || ''},${s.perf_3m?.toFixed(1) || ''},${s.perf_6m?.toFixed(1) || ''},${s.perf_12m?.toFixed(1) || ''}`;
            })].join('\n');
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = `${apiName}_${rankingsPage * 10 - 9}-${rankingsPage * 10}.csv`; a.click();
          }}>
            Export CSV
          </Button>
        </Flex>
        
        <Box overflowX="auto">
          <Box as="table" width="100%" fontSize="sm">
            <Box as="thead" bg="border">
              <Box as="tr">
                <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">#</Box>
                <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Ticker</Box>
                <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Name</Box>
                <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">3M</Box>
                <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">6M</Box>
                <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">12M</Box>
              </Box>
            </Box>
            <Box as="tbody">
              {stocks.slice((rankingsPage - 1) * 10, rankingsPage * 10).map((stock: any) => {
                return (
                  <Box as="tr" key={stock.ticker} borderTop="1px solid" borderColor="border">
                    <Box as="td" p="12px" color="fg.muted">{stock.rank}</Box>
                    <Box as="td" p="12px">
                      <Text color="brand.500" fontWeight="medium" fontFamily="mono">{stock.ticker}</Text>
                    </Box>
                    <Box as="td" p="12px" color="fg.muted">{stock.name || '—'}</Box>
                    <Box as="td" p="12px" textAlign="right" color={stock.perf_3m >= 0 ? 'success.500' : 'error.500'} fontFamily="mono">
                      {stock.perf_3m != null ? `${stock.perf_3m >= 0 ? '+' : ''}${stock.perf_3m.toFixed(1)}%` : '—'}
                    </Box>
                    <Box as="td" p="12px" textAlign="right" color={stock.perf_6m >= 0 ? 'success.500' : 'error.500'} fontFamily="mono">
                      {stock.perf_6m != null ? `${stock.perf_6m >= 0 ? '+' : ''}${stock.perf_6m.toFixed(1)}%` : '—'}
                    </Box>
                    <Box as="td" p="12px" textAlign="right" color={stock.perf_12m >= 0 ? 'success.500' : 'error.500'} fontFamily="mono">
                      {stock.perf_12m != null ? `${stock.perf_12m >= 0 ? '+' : ''}${stock.perf_12m.toFixed(1)}%` : '—'}
                    </Box>
                  </Box>
                );
              })}
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Allocation Calculator - only for momentum */}
      {type === 'momentum' && <AllocationCalculator />}
      {type === 'momentum' && <PortfolioTracker />}
    </VStack>
  );
}

