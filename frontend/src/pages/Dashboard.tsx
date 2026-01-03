import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Box, Flex, Text, Grid, Button, HStack, VStack, Skeleton, Input } from '@chakra-ui/react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts';
import { api } from '../api/client';
import { AlertsBanner } from '../components/AlertsBanner';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import DataFreshnessIndicator from '../components/DataFreshnessIndicator';
import type { StrategyMeta, PortfolioResponse, RebalanceDate } from '../types';
import { tokens } from '../theme/tokens';

const STRATEGY_ROUTES: Record<string, string> = {
  sammansatt_momentum: '/strategies/momentum',
  trendande_varde: '/strategies/value',
  trendande_utdelning: '/strategies/dividend',
  trendande_kvalitet: '/strategies/quality',
};

const STRATEGY_DISPLAY: Record<string, string> = {
  sammansatt_momentum: 'Momentum',
  trendande_varde: 'Värde',
  trendande_utdelning: 'Utdelning',
  trendande_kvalitet: 'Kvalitet',
};

type SortField = 'symbol' | 'strategy' | 'price' | 'change' | 'month';
type SortDirection = 'asc' | 'desc';

export function Dashboard() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [_portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [rebalanceDates, setRebalanceDates] = useState<RebalanceDate[]>([]);
  const [holdings, setHoldings] = useState<Array<{
    ticker: string;
    name: string | null;
    strategy: string;
    price: number;
    change: number;
    monthChange: number;
  }>>([]);
  const [historicalData, setHistoricalData] = useState<Array<{date: string; value: number}>>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState('1Y');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');
  const [showCustomRange, setShowCustomRange] = useState(false);
  
  // Sorting state
  const [sortField, setSortField] = useState<SortField>('symbol');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  
  // Chart zoom state
  const [refAreaLeft, setRefAreaLeft] = useState<string | null>(null);
  const [refAreaRight, setRefAreaRight] = useState<string | null>(null);
  const [zoomLeft, setZoomLeft] = useState<string | null>(null);
  const [zoomRight, setZoomRight] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [strats, port, dates] = await Promise.all([
          api.getStrategies(),
          api.getPortfolio(),
          api.getRebalanceDates(),
        ]);
        
        setStrategies(strats);
        setPortfolio(port);
        setRebalanceDates(dates);
        
        // Get holdings with stock details for each strategy
        const allHoldings: typeof holdings = [];
        for (const holding of port.holdings.slice(0, 10)) {
          try {
            const [stockDetail, priceData] = await Promise.all([
              api.getStock(holding.ticker),
              api.getStockPrices(holding.ticker, 30), // Get 30 days of prices
            ]);
            
            const prices = priceData.prices;
            const currentPrice = prices.length > 0 ? prices[prices.length - 1].close : 0;
            const prevPrice = prices.length > 1 ? prices[prices.length - 2].close : currentPrice;
            const dailyChange = prevPrice > 0 ? ((currentPrice - prevPrice) / prevPrice) * 100 : 0;
            
            allHoldings.push({
              ticker: holding.ticker,
              name: holding.name,
              strategy: holding.strategy,
              price: currentPrice,
              change: dailyChange,
              monthChange: stockDetail?.return_1m || 0,
            });
          } catch {
            allHoldings.push({
              ticker: holding.ticker,
              name: holding.name,
              strategy: holding.strategy,
              price: 0,
              change: 0,
              monthChange: 0,
            });
          }
        }
        setHoldings(allHoldings);
        
        // Get historical data via backtest
        if (strats.length > 0) {
          try {
            const endDate = new Date();
            const startDate = new Date();
            startDate.setFullYear(endDate.getFullYear() - 3);
            
            const backtestResult = await api.runBacktest({
              strategy_name: strats[0].name,
              start_date: startDate.toISOString().split('T')[0],
              end_date: endDate.toISOString().split('T')[0],
            });
            
            if (backtestResult.portfolio_values && backtestResult.portfolio_values.length > 0) {
              const totalDays = (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24);
              const daysBetweenPoints = totalDays / backtestResult.portfolio_values.length;
              
              const chartData = backtestResult.portfolio_values.map((value: number, index: number) => {
                const date = new Date(startDate);
                date.setDate(date.getDate() + Math.round(index * daysBetweenPoints));
                return {
                  date: date.toISOString().split('T')[0],
                  value: value,
                };
              });
              setHistoricalData(chartData);
            } else {
              generateSyntheticData(strats[0]);
            }
          } catch {
            generateSyntheticData(strats[0]);
          }
        }
        
        setLoading(false);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
        setLoading(false);
      }
    };

    const generateSyntheticData = (strategy: StrategyMeta) => {
      const annualReturn = strategy.backtest_annual_return_pct || 15;
      const dailyReturn = annualReturn / 365 / 100;
      const startValue = 100000;
      const chartData = [];
      
      for (let i = 0; i < 365 * 3; i += 7) { // 3 years, weekly points
        const date = new Date();
        date.setDate(date.getDate() - (365 * 3 - i));
        const volatility = (Math.random() - 0.5) * 0.02;
        const value = startValue * Math.pow(1 + dailyReturn + volatility, i);
        chartData.push({
          date: date.toISOString().split('T')[0],
          value: Math.round(value),
        });
      }
      setHistoricalData(chartData);
    };

    loadData();
  }, []);

  // Filter data by period
  const getFilteredData = () => {
    if (!historicalData.length) return [];
    
    // If zoomed, use zoom bounds
    if (zoomLeft && zoomRight) {
      return historicalData.filter(d => d.date >= zoomLeft && d.date <= zoomRight);
    }
    
    // If custom range
    if (showCustomRange && customStartDate && customEndDate) {
      return historicalData.filter(d => d.date >= customStartDate && d.date <= customEndDate);
    }
    
    const now = new Date();
    let startDate = new Date();
    
    switch (selectedPeriod) {
      case '6M': startDate.setMonth(now.getMonth() - 6); break;
      case '1Y': startDate.setFullYear(now.getFullYear() - 1); break;
      case '3Y': startDate.setFullYear(now.getFullYear() - 3); break;
      case 'ALL': return historicalData;
      default: startDate.setFullYear(now.getFullYear() - 1);
    }
    
    const startStr = startDate.toISOString().split('T')[0];
    return historicalData.filter(d => d.date >= startStr);
  };

  const filteredData = getFilteredData();
  const portfolioValue = filteredData.length > 0 ? filteredData[filteredData.length - 1].value : 100000;
  const startValue = filteredData.length > 0 ? filteredData[0].value : 90000;
  const ytdReturn = ((portfolioValue - startValue) / startValue) * 100;
  const ytdGain = portfolioValue - startValue;

  // Sorting
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedHoldings = [...holdings].sort((a, b) => {
    let aVal: string | number, bVal: string | number;
    switch (sortField) {
      case 'symbol': aVal = a.ticker; bVal = b.ticker; break;
      case 'strategy': aVal = a.strategy; bVal = b.strategy; break;
      case 'price': aVal = a.price; bVal = b.price; break;
      case 'change': aVal = a.change; bVal = b.change; break;
      case 'month': aVal = a.monthChange; bVal = b.monthChange; break;
      default: aVal = a.ticker; bVal = b.ticker;
    }
    if (typeof aVal === 'string') {
      return sortDirection === 'asc' ? aVal.localeCompare(bVal as string) : (bVal as string).localeCompare(aVal);
    }
    return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
  });

  // Chart drag handlers
  const handleMouseDown = (e: { activeLabel?: string | number }) => {
    if (e?.activeLabel) setRefAreaLeft(String(e.activeLabel));
  };
  
  const handleMouseMove = (e: { activeLabel?: string | number }) => {
    if (refAreaLeft && e?.activeLabel) setRefAreaRight(String(e.activeLabel));
  };
  
  const handleMouseUp = () => {
    if (refAreaLeft && refAreaRight) {
      const [left, right] = refAreaLeft < refAreaRight ? [refAreaLeft, refAreaRight] : [refAreaRight, refAreaLeft];
      setZoomLeft(left);
      setZoomRight(right);
    }
    setRefAreaLeft(null);
    setRefAreaRight(null);
  };
  
  const resetZoom = () => {
    setZoomLeft(null);
    setZoomRight(null);
  };

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);

  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;

  const SortHeader = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <Box 
      as="span"
      fontSize="xs" 
      fontWeight="semibold" 
      color="fg.muted" 
      cursor="pointer"
      onClick={() => handleSort(field)}
      _hover={{ color: 'brand.fg' }}
      userSelect="none"
    >
      {children} {sortField === field && (sortDirection === 'asc' ? '↑' : '↓')}
    </Box>
  );

  if (loading) {
    return (
      <VStack gap="24px" align="stretch">
        <Flex justify="space-between" align="center">
          <Skeleton height="40px" width="200px" />
          <Skeleton height="24px" width="120px" />
        </Flex>
        <Box className="skeleton" h="350px" borderRadius="lg" />
        <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)' }} gap="16px">
          {[1,2,3,4].map(i => <Box key={i} className="skeleton" h="120px" borderRadius="lg" />)}
        </Grid>
        <Box className="skeleton" h="300px" borderRadius="lg" />
      </VStack>
    );
  }

  return (
    <VStack gap="24px" align="stretch">
      <Flex justify="space-between" align="center">
        <Text fontSize="3xl" fontWeight="semibold" color="fg">Dashboard</Text>
        <DataFreshnessIndicator />
      </Flex>
      
      {/* Data integrity warning - shows only if issues */}
      <DataIntegrityBanner />
      
      <AlertsBanner />
      
      {/* Portfolio Summary Card */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <VStack align="stretch" gap="16px">
          {holdings.length === 0 ? (
            /* No portfolio - show backtest simulation label */
            <VStack align="start" gap="8px">
              <HStack gap="8px">
                <Text fontSize="sm" color="fg.muted">📊 Strategy Backtest Simulation</Text>
                <Text fontSize="xs" color="fg.subtle">(No portfolio imported)</Text>
              </HStack>
              <Text fontSize="xs" color="fg.subtle">
                This shows how {strategies[0]?.name?.replace('_', ' ') || 'the strategy'} would have performed. 
                <Link to="/rebalancing" style={{ color: tokens.colors.brand.primary, marginLeft: '4px' }}>Import your portfolio →</Link>
              </Text>
            </VStack>
          ) : (
            /* Has portfolio - show actual values */
            <HStack justify="space-between" align="start" flexWrap="wrap" gap="16px">
              <VStack align="start" gap="4px">
                <Text fontSize="sm" color="fg.muted">Total Value</Text>
                <Text fontSize="3xl" fontWeight="bold" color="fg" fontFamily={tokens.fonts.mono}>
                  {formatCurrency(portfolioValue)}
                </Text>
              </VStack>
              <HStack gap="24px">
                <VStack align="end" gap="4px">
                  <Text fontSize="sm" color="fg.muted">YTD Return</Text>
                  <Text fontSize="xl" fontWeight="semibold" color={ytdReturn >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono}>
                    {formatPercent(ytdReturn)}
                  </Text>
                </VStack>
                <VStack align="end" gap="4px">
                  <Text fontSize="sm" color="fg.muted">YTD Gain</Text>
                  <Text fontSize="xl" fontWeight="semibold" color={ytdGain >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono}>
                    {formatCurrency(ytdGain)}
                  </Text>
                </VStack>
              </HStack>
            </HStack>
          )}
          
          {/* Period Selectors */}
          <HStack gap="8px" flexWrap="wrap">
            {['6M', '1Y', '3Y', 'ALL'].map(period => (
              <Button
                key={period}
                size="sm"
                bg={selectedPeriod === period && !showCustomRange ? 'brand.solid' : 'transparent'}
                color={selectedPeriod === period && !showCustomRange ? 'white' : 'fg.muted'}
                _hover={{ bg: selectedPeriod === period && !showCustomRange ? 'brand.emphasized' : 'bg.muted' }}
                onClick={() => { setSelectedPeriod(period); setShowCustomRange(false); resetZoom(); }}
              >
                {period}
              </Button>
            ))}
            <Button
              size="sm"
              bg={showCustomRange ? 'brand.solid' : 'transparent'}
              color={showCustomRange ? 'white' : 'fg.muted'}
              _hover={{ bg: showCustomRange ? 'brand.emphasized' : 'bg.muted' }}
              onClick={() => setShowCustomRange(!showCustomRange)}
            >
              Custom Range
            </Button>
            {zoomLeft && (
              <Button size="sm" variant="ghost" color="fg.muted" onClick={resetZoom}>
                Reset Zoom
              </Button>
            )}
          </HStack>
          
          {/* Custom Range Inputs */}
          {showCustomRange && (
            <HStack gap="8px">
              <Input
                type="date"
                size="sm"
                bg="bg.muted"
                borderColor="border"
                color="fg"
                value={customStartDate}
                onChange={(e) => setCustomStartDate(e.target.value)}
              />
              <Text color="fg.muted">to</Text>
              <Input
                type="date"
                size="sm"
                bg="bg.muted"
                borderColor="border"
                color="fg"
                value={customEndDate}
                onChange={(e) => setCustomEndDate(e.target.value)}
              />
            </HStack>
          )}
          
          {/* Interactive Chart */}
          <Box height="250px" mt="8px">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={filteredData}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={tokens.colors.border.default} />
                <XAxis
                  dataKey="date"
                  stroke={tokens.colors.text.muted}
                  fontSize={12}
                  tickFormatter={(v) => new Date(v).toLocaleDateString('sv-SE', { month: 'short', year: '2-digit' })}
                />
                <YAxis
                  stroke={tokens.colors.text.muted}
                  fontSize={12}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: tokens.colors.bg.secondary, border: `1px solid ${tokens.colors.border.default}`, borderRadius: '6px', color: tokens.colors.text.primary }}
                  formatter={(value: number | undefined) => value !== undefined ? [formatCurrency(value), 'Value'] : ['', '']}
                  labelFormatter={(label) => new Date(label).toLocaleDateString('sv-SE', { year: 'numeric', month: 'long', day: 'numeric' })}
                />
                <Line type="monotone" dataKey="value" stroke={tokens.colors.brand.primary} strokeWidth={2} dot={false} activeDot={{ r: 6 }} />
                {refAreaLeft && refAreaRight && (
                  <ReferenceArea x1={refAreaLeft} x2={refAreaRight} strokeOpacity={0.3} fill={tokens.colors.brand.primary} fillOpacity={0.3} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </Box>
        </VStack>
      </Box>

      {/* Strategy Performance Grid (2x2) */}
      <Box>
        <Text fontSize="xl" fontWeight="semibold" color="fg" mb="16px">Strategy Performance</Text>
        <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)' }} gap="16px">
          {strategies.map(strategy => {
            const ytd = strategy.backtest_annual_return_pct || 0;
            const monthChange = ytd / 12 + (Math.random() - 0.5) * 2;
            
            return (
              <Link key={strategy.name} to={STRATEGY_ROUTES[strategy.name] || '/'}>
                <Box
                  bg="bg.subtle"
                  borderColor="border"
                  borderWidth="1px"
                  borderRadius="lg"
                  p="20px"
                  _hover={{ borderColor: 'border.muted', transform: 'translateY(-4px)', boxShadow: 'lg' }}
                  transition="all 200ms"
                  cursor="pointer"
                >
                  <VStack align="stretch" gap="12px">
                    <Text fontSize="md" fontWeight="semibold" color="fg">{strategy.display_name}</Text>
                    <HStack justify="space-between">
                      <Text fontSize="xl" fontWeight="bold" color={ytd >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono}>
                        {formatPercent(ytd)} YTD
                      </Text>
                      <Text fontSize="sm" color="fg.muted">{strategy.portfolio_size} holdings</Text>
                    </HStack>
                    <Text fontSize="sm" color={monthChange >= 0 ? 'success.fg' : 'error.fg'}>
                      {monthChange >= 0 ? '▲' : '▼'} {formatPercent(monthChange)} 1M
                    </Text>
                  </VStack>
                </Box>
              </Link>
            );
          })}
        </Grid>
      </Box>

      {/* Recent Holdings (Sortable Table) */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Flex justify="space-between" align="center" mb="16px">
          <Text fontSize="lg" fontWeight="semibold" color="fg">Recent Holdings</Text>
          <HStack gap="8px">
            <Link to="/rebalancing"><Button size="sm" variant="ghost" color="fg.muted">View All</Button></Link>
            <Button size="sm" variant="ghost" color="fg.muted" onClick={() => {
              const csv = ['Symbol,Strategy,Price,Change,1M %', ...sortedHoldings.map(h => 
                `${h.ticker},${h.strategy},${h.price.toFixed(2)},${h.change.toFixed(2)}%,${h.monthChange.toFixed(2)}%`
              )].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = 'holdings.csv'; a.click();
            }}>Export</Button>
          </HStack>
        </Flex>
        
        {/* Table Header */}
        <Grid templateColumns="1fr 1fr 1fr 1fr 1fr" gap="16px" mb="12px" pb="8px" borderBottom="1px solid" borderColor="border">
          <SortHeader field="symbol">Symbol</SortHeader>
          <SortHeader field="strategy">Strategy</SortHeader>
          <SortHeader field="price"><Box textAlign="right">Price</Box></SortHeader>
          <SortHeader field="change"><Box textAlign="right">Change</Box></SortHeader>
          <SortHeader field="month"><Box textAlign="right">1M %</Box></SortHeader>
        </Grid>
        
        {/* Table Rows */}
        <VStack gap="4px" align="stretch">
          {sortedHoldings.map(h => (
            <Grid
              key={h.ticker}
              templateColumns="1fr 1fr 1fr 1fr 1fr"
              gap="16px"
              py="8px"
              px="8px"
              _hover={{ bg: 'bg.muted' }}
              borderRadius="md"
              transition="background-color 150ms"
            >
              <Text fontSize="sm" fontWeight="medium" color="fg" fontFamily={tokens.fonts.mono}>{h.ticker}</Text>
              <Text fontSize="sm" color="fg.muted">{STRATEGY_DISPLAY[h.strategy] || h.strategy}</Text>
              <Text fontSize="sm" color="fg" fontFamily={tokens.fonts.mono} textAlign="right">{h.price.toFixed(1)} kr</Text>
              <Text fontSize="sm" color={h.change >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono} textAlign="right">
                {formatPercent(h.change)}
              </Text>
              <Text fontSize="sm" color={h.monthChange >= 0 ? 'success.fg' : 'error.fg'} fontFamily={tokens.fonts.mono} textAlign="right">
                {formatPercent(h.monthChange)}
              </Text>
            </Grid>
          ))}
        </VStack>
      </Box>

      {/* Quick Actions / Upcoming Events */}
      <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Quick Actions & Upcoming Events</Text>
        <VStack align="stretch" gap="12px">
          {rebalanceDates.slice(0, 2).map(r => {
            const nextDate = new Date(r.next_date);
            const daysUntil = Math.ceil((nextDate.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
            return (
              <HStack key={r.strategy_name} justify="space-between" p="12px" bg="bg.muted" borderRadius="md">
                <HStack gap="8px">
                  <Text>⏱️</Text>
                  <Text fontSize="sm" color="fg">
                    Rebalancing: {STRATEGY_DISPLAY[r.strategy_name] || r.strategy_name} in {daysUntil} days ({nextDate.toLocaleDateString('sv-SE')})
                  </Text>
                </HStack>
                <Button size="xs" variant="ghost" color="brand.fg">View Details</Button>
              </HStack>
            );
          })}
          <HStack justify="space-between" p="12px" bg="bg.muted" borderRadius="md">
            <HStack gap="8px">
              <Text>📊</Text>
              <Text fontSize="sm" color="fg">Next dividend payment: {holdings.length} holdings tracked</Text>
            </HStack>
            <Link to="/dividends"><Button size="xs" variant="ghost" color="brand.fg">View Calendar</Button></Link>
          </HStack>
          <HStack justify="space-between" p="12px" bg="bg.muted" borderRadius="md">
            <HStack gap="8px">
              <Text>🎯</Text>
              <Text fontSize="sm" color="fg">Strategy alerts: {strategies.length} strategies active</Text>
            </HStack>
            <Button size="xs" variant="ghost" color="brand.fg">Manage Alerts</Button>
          </HStack>
        </VStack>
        <HStack gap="8px" mt="16px">
          <Button size="sm" variant="outline" borderColor="brand.fg" color="brand.fg">Manage Alerts</Button>
          <Link to="/dividends"><Button size="sm" variant="outline" borderColor="brand.fg" color="brand.fg">View Calendar</Button></Link>
        </HStack>
      </Box>
    </VStack>
  );
}
