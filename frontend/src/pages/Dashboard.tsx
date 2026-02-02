import { useState, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Box, Flex, Text, Button, HStack, VStack, Skeleton } from '@chakra-ui/react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useStrategies, useRebalanceDates, queryKeys } from '../api/hooks';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import type { StrategyMeta } from '../types';
import { tokens } from '../theme/tokens';

const STRATEGY_ROUTES: Record<string, string> = {
  sammansatt_momentum: '/strategies/momentum',
};

// Only show momentum strategy
const ALLOWED_STRATEGIES = ['sammansatt_momentum'];

export function Dashboard() {
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [momentumHoldings, setMomentumHoldings] = useState<Array<{ticker: string; shares: number; buyPrice: number}>>([]);
  const queryClient = useQueryClient();
  const { data: strategies = [], isLoading: strategiesLoading, isError: strategiesError } = useStrategies();
  const { data: rebalanceDates = [] } = useRebalanceDates();

  // Load momentum portfolio
  useEffect(() => {
    api.get<{holdings: Array<{ticker: string; shares: number; buyPrice: number}>}>('/user/momentum-portfolio')
      .then(data => setMomentumHoldings(data.holdings || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (strategies.length > 0) {
      strategies.forEach((s: StrategyMeta) => {
        queryClient.prefetchQuery({
          queryKey: queryKeys.strategies.rankings(s.name),
          queryFn: () => api.getStrategyRankings(s.name),
          staleTime: 5 * 60 * 1000,
        });
      });
    }
  }, [strategies, queryClient]);

  const historicalData = useMemo(() => {
    if (!strategies.length) return [];
    const strategy = strategies[0];
    const annualReturn = strategy.backtest_annual_return_pct || 15;
    const dailyReturn = annualReturn / 365 / 100;
    const startValue = 100000;
    const chartData = [];
    for (let i = 0; i < 365 * 3; i += 7) {
      const date = new Date();
      date.setDate(date.getDate() - (365 * 3 - i));
      const volatility = (Math.random() - 0.5) * 0.02;
      const value = startValue * Math.pow(1 + dailyReturn + volatility, i);
      chartData.push({ date: date.toISOString().split('T')[0], value: Math.round(value) });
    }
    return chartData;
  }, [strategies]);

  const filteredData = useMemo(() => {
    if (!historicalData.length) return [];
    const now = new Date();
    const startDate = new Date();
    switch (selectedPeriod) {
      case '6M': startDate.setMonth(now.getMonth() - 6); break;
      case '1Y': startDate.setFullYear(now.getFullYear() - 1); break;
      case '3Y': startDate.setFullYear(now.getFullYear() - 3); break;
      case 'ALL': return historicalData;
      default: startDate.setFullYear(now.getFullYear() - 1);
    }
    return historicalData.filter(d => d.date >= startDate.toISOString().split('T')[0]);
  }, [historicalData, selectedPeriod]);

  // Calculate real portfolio value from holdings
  const realPortfolioValue = useMemo(() => {
    if (!momentumHoldings.length) return null;
    return momentumHoldings.reduce((sum, h) => sum + (h.shares * h.buyPrice), 0);
  }, [momentumHoldings]);

  const portfolioValue = realPortfolioValue || (filteredData.length > 0 ? filteredData[filteredData.length - 1].value : 100000);
  const startValue = filteredData.length > 0 ? filteredData[0].value : 90000;
  const ytdReturn = realPortfolioValue ? 0 : ((portfolioValue - startValue) / startValue) * 100; // Show 0% for real portfolio (no historical data yet)

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);
  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;

  const loading = strategiesLoading;

  if (strategiesError) {
    return (
      <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="8px" p="16px">
        <Text color="red.400" fontWeight="semibold">Failed to load data</Text>
        <Button mt="12px" size="sm" colorScheme="red" variant="outline" onClick={() => queryClient.invalidateQueries()}>Retry</Button>
      </Box>
    );
  }

  if (loading) {
    return (
      <VStack gap="24px" align="stretch">
        <Skeleton height="200px" borderRadius="lg" />
        <HStack gap="16px">{[1,2,3,4].map(i => <Skeleton key={i} height="80px" flex="1" borderRadius="lg" />)}</HStack>
        <Skeleton height="100px" borderRadius="lg" />
      </VStack>
    );
  }

  const nextRebalance = rebalanceDates[0];
  const daysUntil = nextRebalance ? Math.ceil((new Date(nextRebalance.next_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)) : null;

  return (
    <VStack gap="24px" align="stretch">
      <DataIntegrityBanner />
      <AlertsBanner />

      {/* Hero: Portfolio Value */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Flex justify="space-between" align="start" mb="16px" flexWrap="wrap" gap="16px">
          <VStack align="start" gap="4px">
            <Text fontSize="sm" color="fg.muted">{momentumHoldings.length ? 'Portfolio Value' : 'Strategy Simulation'}</Text>
            <Text fontSize="4xl" fontWeight="bold" color="fg" fontFamily={tokens.fonts.mono}>{formatCurrency(portfolioValue)}</Text>
            <Text fontSize="lg" color={ytdReturn >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono}>
              {realPortfolioValue ? `${momentumHoldings.length} innehav` : formatPercent(ytdReturn) + ' YTD'}
            </Text>
          </VStack>
          <HStack gap="4px">
            {['6M', '1Y', '3Y', 'ALL'].map(period => (
              <Button key={period} size="xs" bg={selectedPeriod === period ? 'brand.solid' : 'transparent'} color={selectedPeriod === period ? 'white' : 'fg.muted'} _hover={{ bg: selectedPeriod === period ? 'brand.emphasized' : 'bg.muted' }} onClick={() => setSelectedPeriod(period)}>{period}</Button>
            ))}
          </HStack>
        </Flex>
        {/* Only show chart for simulated data */}
        {!realPortfolioValue && (
          <Box height="180px">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={filteredData}>
                <XAxis dataKey="date" stroke={tokens.colors.text.muted} fontSize={11} tickFormatter={(v) => new Date(v).toLocaleDateString('sv-SE', { month: 'short' })} />
                <YAxis stroke={tokens.colors.text.muted} fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} width={40} />
                <Tooltip contentStyle={{ backgroundColor: tokens.colors.bg.secondary, border: `1px solid ${tokens.colors.border.default}`, borderRadius: '6px', color: tokens.colors.text.primary }} formatter={(value: number | undefined) => value !== undefined ? [formatCurrency(value), 'Value'] : ['', '']} />
                <Line type="monotone" dataKey="value" stroke={tokens.colors.brand.primary} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        )}
        {!momentumHoldings.length && (
          <Text fontSize="xs" color="fg.subtle" mt="8px">
            Simulated performance. <Link to="/strategies/momentum" style={{ color: tokens.colors.brand.primary }}>Import portfolio →</Link>
          </Text>
        )}
      </Box>

      {/* Compact Strategy Row */}
      <HStack gap="12px" overflowX="auto" pb="4px">
        {strategies.filter((s: StrategyMeta) => ALLOWED_STRATEGIES.includes(s.name)).map((strategy: StrategyMeta) => {
          const ytd = strategy.backtest_annual_return_pct || 0;
          return (
            <Link key={strategy.name} to={STRATEGY_ROUTES[strategy.name] || '/'}>
              <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="16px" minW="140px" _hover={{ borderColor: 'brand.fg' }} transition="all 150ms">
                <Text fontSize="sm" fontWeight="medium" color="fg" mb="4px">{strategy.display_name}</Text>
                <Text fontSize="xl" fontWeight="bold" color={ytd >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono}>{formatPercent(ytd)}</Text>
                <Text fontSize="xs" color="fg.muted">{strategy.portfolio_size} aktier</Text>
              </Box>
            </Link>
          );
        })}
      </HStack>

      {/* Kom igång card for new users */}
      {!momentumHoldings.length && (
        <Box bg="brand.solid/10" borderColor="brand.fg" borderWidth="1px" borderRadius="lg" p="20px">
          <Flex justify="space-between" align="center">
            <VStack align="start" gap="4px">
              <Text fontSize="md" fontWeight="semibold" color="fg">Ny här? Kom igång!</Text>
              <Text fontSize="sm" color="fg.muted">Lär dig hur du använder strategierna och importerar din portfölj</Text>
            </VStack>
            <Link to="/getting-started"><Button size="sm" bg="brand.solid" color="white" _hover={{ bg: 'brand.emphasized' }}>Kom igång</Button></Link>
          </Flex>
        </Box>
      )}

      {/* Compact Holdings Preview */}
      {momentumHoldings.length > 0 && (
        <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
          <Flex justify="space-between" align="center" mb="12px">
            <Text fontSize="md" fontWeight="semibold" color="fg">Dina innehav</Text>
            <Link to="/strategies/momentum"><Button size="xs" variant="ghost" color="brand.fg">Visa alla</Button></Link>
          </Flex>
          <VStack align="stretch" gap="8px">
            {momentumHoldings.slice(0, 5).map(h => (
              <Flex key={h.ticker} justify="space-between" align="center">
                <Text fontSize="sm" color="fg" fontFamily={tokens.fonts.mono}>{h.ticker}</Text>
                <Text fontSize="sm" color="fg.muted">{h.shares} st @ {h.buyPrice.toFixed(0)} kr</Text>
              </Flex>
            ))}
            {momentumHoldings.length > 5 && (
              <Text fontSize="xs" color="fg.subtle" textAlign="center">+{momentumHoldings.length - 5} fler innehav</Text>
            )}
          </VStack>
        </Box>
      )}

      {/* Essential Actions */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
        <VStack align="stretch" gap="12px">
          {nextRebalance && daysUntil !== null && (
            <HStack justify="space-between">
              <Text fontSize="sm" color="fg">Nästa rebalansering om {daysUntil} dagar</Text>
              <Link to="/rebalancing"><Button size="xs" variant="ghost" color="brand.fg">Visa</Button></Link>
            </HStack>
          )}
          <HStack justify="space-between">
            <Text fontSize="sm" color="fg">Hantera din strategi</Text>
            <Link to="/rebalancing"><Button size="xs" variant="ghost" color="brand.fg">Min Strategi</Button></Link>
          </HStack>
          <HStack justify="space-between">
            <Text fontSize="sm" color="fg">Utforska strategier</Text>
            <Link to="/strategies/momentum"><Button size="xs" variant="ghost" color="brand.fg">Strategier</Button></Link>
          </HStack>
        </VStack>
      </Box>
    </VStack>
  );
}
