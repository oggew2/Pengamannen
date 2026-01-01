import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Box,
  Flex,
  Text,
  Button,
  HStack,
  VStack,
  Skeleton,
  Input,
} from '@chakra-ui/react';
import { api, RebalanceTrade, RebalanceTradesResponse } from '../api/client';
import { DataIntegrityBanner } from '../components/DataIntegrityBanner';
import type { StrategyMeta, RebalanceDate, PortfolioResponse } from '../types';

const STRATEGY_DISPLAY: Record<string, string> = {
  sammansatt_momentum: 'Sammansatt Momentum',
  trendande_varde: 'Trendande Värde',
  trendande_utdelning: 'Trendande Utdelning',
  trendande_kvalitet: 'Trendande Kvalitet',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export default function RebalancingPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [rebalanceDates, setRebalanceDates] = useState<RebalanceDate[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [trades, setTrades] = useState<RebalanceTrade[]>([]);
  const [costs, setCosts] = useState<RebalanceTradesResponse['costs'] | null>(null);
  const [strategyTargets, setStrategyTargets] = useState<Record<string, string[]>>({});
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [portfolioValue, setPortfolioValue] = useState<number>(100000);
  const [loading, setLoading] = useState(true);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [checkedTrades, setCheckedTrades] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<'all' | 'quarterly' | 'annual'>('all');
  const [reminderEmail, setReminderEmail] = useState('');
  const [showReminderInput, setShowReminderInput] = useState(false);

  const sendReminder = async () => {
    if (!reminderEmail || !selectedStrategy) return;
    try {
      await api.sendRebalanceReminder(reminderEmail, selectedStrategy);
      setShowReminderInput(false);
      setReminderEmail('');
    } catch (e) { console.error('Failed to send reminder:', e); }
  };

  useEffect(() => {
    const loadData = async () => {
      try {
        const [strats, dates, port] = await Promise.all([
          api.getStrategies(),
          api.getRebalanceDates(),
          api.getPortfolio(),
        ]);
        setStrategies(strats);
        setRebalanceDates(dates);
        setPortfolio(port);
        if (strats.length > 0) setSelectedStrategy(strats[0].name);
        
        // Fetch target stocks for each strategy
        const targets: Record<string, string[]> = {};
        await Promise.all(strats.map(async (s) => {
          try {
            const rankings = await api.getStrategyTop10(s.name);
            targets[s.name] = rankings.slice(0, 10).map(r => r.ticker.replace('.ST', ''));
          } catch { targets[s.name] = []; }
        }));
        setStrategyTargets(targets);
        
        setLoading(false);
      } catch (error) {
        console.error('Failed to load rebalancing data:', error);
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const loadTrades = async () => {
    if (!selectedStrategy) return;
    setTradesLoading(true);
    try {
      const currentHoldings = portfolio?.holdings
        .filter(h => h.strategy === selectedStrategy)
        .map(h => ({ ticker: h.ticker, shares: 0, value: h.weight * portfolioValue })) || [];
      
      const result = await api.getRebalanceTrades(selectedStrategy, portfolioValue, currentHoldings);
      setTrades(result.trades || []);
      setCosts(result.costs || null);
      setCheckedTrades(new Set());
    } catch (error) {
      console.error('Failed to load trades:', error);
      setTrades([]);
      setCosts(null);
    }
    setTradesLoading(false);
  };

  useEffect(() => {
    if (selectedStrategy && portfolioValue > 0) {
      loadTrades();
    }
  }, [selectedStrategy, portfolioValue]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const toggleTrade = (ticker: string) => {
    const newChecked = new Set(checkedTrades);
    if (newChecked.has(ticker)) {
      newChecked.delete(ticker);
    } else {
      newChecked.add(ticker);
    }
    setCheckedTrades(newChecked);
  };

  const exportTrades = () => {
    const csv = ['Ticker,Action,Shares,Amount (SEK),Price,ISIN', 
      ...trades.map(t => `${t.ticker},${t.action},${t.shares},${t.amount_sek.toFixed(2)},${t.price || 'N/A'},${t.isin || 'N/A'}`)
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'rebalance_trades.csv'; a.click();
  };

  // Get next rebalance info
  const nextRebalance = rebalanceDates.length > 0 
    ? rebalanceDates.reduce((a, b) => new Date(a.next_date) < new Date(b.next_date) ? a : b)
    : null;
  
  const daysUntilNext = nextRebalance 
    ? Math.ceil((new Date(nextRebalance.next_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : 0;

  // Filter strategies by type
  const filteredDates = rebalanceDates.filter(d => {
    if (filterType === 'all') return true;
    const strategy = strategies.find(s => s.name === d.strategy_name);
    if (filterType === 'quarterly') return strategy?.rebalance_frequency === 'quarterly';
    if (filterType === 'annual') return strategy?.rebalance_frequency === 'annual';
    return true;
  });

  // Calculate costs from API or fallback
  const sellTrades = trades.filter(t => t.action === 'SELL');
  const buyTrades = trades.filter(t => t.action === 'BUY');
  const totalSell = sellTrades.reduce((sum, t) => sum + t.amount_sek, 0);
  const totalBuy = buyTrades.reduce((sum, t) => sum + t.amount_sek, 0);
  const totalCost = costs?.total || 0;
  const costPercentage = costs?.percentage || 0;

  const formatCurrency = (value: number) => 
    new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(value);

  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

  if (loading) {
    return (
      <VStack gap="24px" align="stretch">
        <Skeleton height="40px" width="250px" />
        <Skeleton height="150px" borderRadius="8px" />
        <Skeleton height="200px" borderRadius="8px" />
        <Skeleton height="300px" borderRadius="8px" />
        <Skeleton height="200px" borderRadius="8px" />
      </VStack>
    );
  }

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="3xl" fontWeight="semibold" color="gray.50">Rebalancing</Text>

      {/* Critical: Data integrity check before trading */}
      <DataIntegrityBanner />

      {/* Rebalancing Calendar */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="24px">
        <VStack align="stretch" gap="16px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50">Rebalancing Calendar</Text>
          
          {nextRebalance && (
            <HStack justify="space-between" align="center">
              <VStack align="start" gap="4px">
                <Text fontSize="sm" color="gray.200">Next: {STRATEGY_DISPLAY[nextRebalance.strategy_name] || nextRebalance.strategy_name}</Text>
                <HStack gap="16px">
                  <HStack gap="8px">
                    <Text fontSize="lg">📅</Text>
                    <Text fontSize="xl" fontWeight="bold" color="gray.50">
                      {new Date(nextRebalance.next_date).toLocaleDateString('sv-SE')}
                    </Text>
                  </HStack>
                  <HStack gap="8px">
                    <Text fontSize="lg">⏱️</Text>
                    <Text fontSize="xl" fontWeight="bold" color={daysUntilNext <= 7 ? 'warning.500' : 'gray.50'}>
                      {daysUntilNext} days away
                    </Text>
                  </HStack>
                </HStack>
              </VStack>
            </HStack>
          )}

          {/* Filter buttons */}
          <HStack gap="8px">
            {(['all', 'quarterly', 'annual'] as const).map(type => (
              <Button
                key={type}
                size="sm"
                bg={filterType === type ? 'brand.500' : 'transparent'}
                color={filterType === type ? 'white' : 'gray.200'}
                _hover={{ bg: filterType === type ? 'brand.600' : 'gray.600' }}
                onClick={() => setFilterType(type)}
                textTransform="capitalize"
              >
                {type === 'all' ? 'All' : type}
              </Button>
            ))}
          </HStack>

          {/* Month calendar */}
          <HStack gap="8px" overflowX="auto" py="8px">
            {MONTHS.map((month, idx) => {
              const hasRebalance = filteredDates.some(d => new Date(d.next_date).getMonth() === idx);
              const isCurrentMonth = new Date().getMonth() === idx;
              return (
                <Box
                  key={month}
                  px="12px"
                  py="8px"
                  borderRadius="6px"
                  bg={hasRebalance ? 'brand.500' : isCurrentMonth ? 'gray.600' : 'transparent'}
                  color={hasRebalance ? 'white' : 'gray.200'}
                  fontWeight={hasRebalance || isCurrentMonth ? 'semibold' : 'normal'}
                  fontSize="sm"
                  minW="50px"
                  textAlign="center"
                >
                  {month}
                </Box>
              );
            })}
          </HStack>
        </VStack>
      </Box>

      {/* Changes Overview */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Changes Overview</Text>
        <VStack align="stretch" gap="12px">
          {strategies.map(strategy => {
            const rebalanceDate = rebalanceDates.find(d => d.strategy_name === strategy.name);
            const daysUntil = rebalanceDate 
              ? Math.ceil((new Date(rebalanceDate.next_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
              : null;
            const targets = strategyTargets[strategy.name] || [];
            const currentHoldings = portfolio?.holdings.filter(h => h.strategy === strategy.name).map(h => h.ticker.replace('.ST', '')) || [];
            const toKeep = targets.filter(t => currentHoldings.includes(t));
            const toBuy = targets.filter(t => !currentHoldings.includes(t));
            const toSell = currentHoldings.filter(t => !targets.includes(t));
            const changeCount = toBuy.length + toSell.length;
            
            return (
              <Box key={strategy.name} p="12px" bg="gray.600" borderRadius="6px">
                <HStack justify="space-between" align="start" mb={targets.length > 0 ? '8px' : '0'}>
                  <VStack align="start" gap="2px">
                    <Text fontSize="sm" fontWeight="semibold" color="gray.50">
                      {strategy.display_name}: {changeCount > 0 ? `${changeCount} changes` : 'No changes'}
                    </Text>
                    <Text fontSize="xs" color="gray.200">
                      {strategy.rebalance_frequency} • {strategy.portfolio_size} holdings
                    </Text>
                  </VStack>
                  {daysUntil !== null && (
                    <Text fontSize="xs" color={daysUntil <= 7 ? 'warning.500' : 'gray.200'}>
                      {daysUntil} days
                    </Text>
                  )}
                </HStack>
                {targets.length > 0 && (
                  <HStack gap="6px" flexWrap="wrap">
                    {toKeep.slice(0, 3).map(t => (
                      <Text key={t} fontSize="xs" color="gray.200">✓ {t}</Text>
                    ))}
                    {toSell.slice(0, 2).map(t => (
                      <Text key={t} fontSize="xs" color="error.400">• {t} (sell)</Text>
                    ))}
                    {toBuy.slice(0, 2).map(t => (
                      <Text key={t} fontSize="xs" color="success.400">• {t} (buy)</Text>
                    ))}
                  </HStack>
                )}
              </Box>
            );
          })}
        </VStack>
      </Box>

      {/* Actions Required */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="24px">
        <Flex justify="space-between" align="center" mb="16px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50">Actions Required</Text>
          <HStack gap="8px">
            <Button size="sm" variant="ghost" color="gray.200" onClick={exportTrades}>Export List</Button>
          </HStack>
        </Flex>

        {/* Strategy and value selector */}
        <HStack gap="16px" mb="16px">
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.200">Strategy</Text>
            <HStack gap="8px">
              {strategies.map(s => (
                <Button
                  key={s.name}
                  size="sm"
                  bg={selectedStrategy === s.name ? 'brand.500' : 'gray.600'}
                  color={selectedStrategy === s.name ? 'white' : 'gray.200'}
                  _hover={{ bg: selectedStrategy === s.name ? 'brand.600' : 'gray.500' }}
                  onClick={() => setSelectedStrategy(s.name)}
                >
                  {STRATEGY_DISPLAY[s.name]?.split(' ')[0] || s.name}
                </Button>
              ))}
            </HStack>
          </VStack>
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.200">Portfolio Value (SEK)</Text>
            <Input
              type="number"
              size="sm"
              bg="gray.600"
              borderColor="gray.500"
              color="gray.100"
              width="150px"
              value={portfolioValue}
              onChange={(e) => setPortfolioValue(Number(e.target.value))}
            />
          </VStack>
        </HStack>

        {tradesLoading ? (
          <VStack gap="8px">
            <Skeleton height="40px" width="100%" />
            <Skeleton height="40px" width="100%" />
            <Skeleton height="40px" width="100%" />
          </VStack>
        ) : (
          <>
            {/* SELL section */}
            {sellTrades.length > 0 && (
              <Box mb="16px">
                <Text fontSize="sm" fontWeight="semibold" color="error.500" mb="8px">
                  SELL ({sellTrades.length} stocks)
                </Text>
                <VStack gap="4px" align="stretch">
                  {sellTrades.map(trade => (
                    <HStack key={trade.ticker} justify="space-between" p="8px" bg="gray.600" borderRadius="4px">
                      <HStack gap="12px">
                        <Box
                          as="button"
                          w="16px"
                          h="16px"
                          borderRadius="3px"
                          border="2px solid"
                          borderColor={checkedTrades.has(trade.ticker) ? 'error.500' : 'gray.400'}
                          bg={checkedTrades.has(trade.ticker) ? 'error.500' : 'transparent'}
                          onClick={() => toggleTrade(trade.ticker)}
                          cursor="pointer"
                        >
                          {checkedTrades.has(trade.ticker) && <Text fontSize="10px" color="white" lineHeight="12px">✓</Text>}
                        </Box>
                        <Text fontSize="sm" fontWeight="medium" color="gray.100" fontFamily="mono">
                          {trade.ticker}
                        </Text>
                        <Text fontSize="sm" color="gray.200">
                          ({trade.price ? `${trade.price.toFixed(2)} kr` : 'N/A'})
                        </Text>
                      </HStack>
                      <Button
                        size="xs"
                        variant="ghost"
                        color="brand.500"
                        onClick={() => copyToClipboard(trade.isin || trade.ticker)}
                      >
                        Copy ISIN
                      </Button>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            )}

            {/* BUY section */}
            {buyTrades.length > 0 && (
              <Box>
                <Text fontSize="sm" fontWeight="semibold" color="success.500" mb="8px">
                  BUY ({buyTrades.length} stocks)
                </Text>
                <VStack gap="4px" align="stretch">
                  {buyTrades.map(trade => (
                    <HStack key={trade.ticker} justify="space-between" p="8px" bg="gray.600" borderRadius="4px">
                      <HStack gap="12px">
                        <Box
                          as="button"
                          w="16px"
                          h="16px"
                          borderRadius="3px"
                          border="2px solid"
                          borderColor={checkedTrades.has(trade.ticker) ? 'success.500' : 'gray.400'}
                          bg={checkedTrades.has(trade.ticker) ? 'success.500' : 'transparent'}
                          onClick={() => toggleTrade(trade.ticker)}
                          cursor="pointer"
                        >
                          {checkedTrades.has(trade.ticker) && <Text fontSize="10px" color="white" lineHeight="12px">✓</Text>}
                        </Box>
                        <Text fontSize="sm" fontWeight="medium" color="gray.100" fontFamily="mono">
                          {trade.ticker}
                        </Text>
                        <Text fontSize="sm" color="gray.200">
                          ({trade.price ? `${trade.price.toFixed(2)} kr` : 'N/A'})
                        </Text>
                      </HStack>
                      <Button
                        size="xs"
                        variant="ghost"
                        color="brand.500"
                        onClick={() => copyToClipboard(trade.isin || trade.ticker)}
                      >
                        Copy ISIN
                      </Button>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            )}

            {trades.length === 0 && (
              <Text fontSize="sm" color="gray.200" textAlign="center" py="16px">
                No trades required for current selection
              </Text>
            )}
          </>
        )}
      </Box>

      {/* Cost Analysis */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Cost Analysis</Text>
        
        <VStack align="stretch" gap="12px">
          <HStack justify="space-between">
            <HStack gap="8px">
              <Text fontSize="lg">💰</Text>
              <Text fontSize="sm" color="gray.100">Est. Trading Cost:</Text>
            </HStack>
            <Text fontSize="sm" fontWeight="semibold" color="gray.50" fontFamily="mono">
              ~{formatPercent(costPercentage)} ({formatCurrency(totalCost)})
            </Text>
          </HStack>

          <Box pl="32px">
            <VStack align="stretch" gap="4px">
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">• Spread estimate:</Text>
                <Text fontSize="xs" color="gray.200" fontFamily="mono">{formatCurrency(costs?.spread_estimate || 0)}</Text>
              </HStack>
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">• Courtage (Avanza 0.069%):</Text>
                <Text fontSize="xs" color="gray.200" fontFamily="mono">{formatCurrency(costs?.courtage || 0)}</Text>
              </HStack>
            </VStack>
          </Box>

          <Box borderTop="1px solid" borderColor="gray.600" pt="12px" mt="8px">
            <HStack gap="8px" mb="8px">
              <Text fontSize="lg">💡</Text>
              <Text fontSize="sm" color="gray.100">Best Broker Today:</Text>
            </HStack>
            <VStack align="stretch" gap="4px" pl="32px">
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">Avanza:</Text>
                <Text fontSize="xs" color="success.500" fontFamily="mono">0.069% courtage</Text>
              </HStack>
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">Nordnet:</Text>
                <Text fontSize="xs" color="gray.200" fontFamily="mono">0.15% courtage</Text>
              </HStack>
            </VStack>
          </Box>

          <Box borderTop="1px solid" borderColor="gray.600" pt="12px" mt="8px">
            <HStack gap="8px" mb="8px">
              <Text fontSize="lg">📊</Text>
              <Text fontSize="sm" color="gray.100">Trade Summary:</Text>
            </HStack>
            <VStack align="stretch" gap="4px" pl="32px">
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">Total to sell:</Text>
                <Text fontSize="xs" color="error.500" fontFamily="mono">{formatCurrency(totalSell)}</Text>
              </HStack>
              <HStack justify="space-between">
                <Text fontSize="xs" color="gray.200">Total to buy:</Text>
                <Text fontSize="xs" color="success.500" fontFamily="mono">{formatCurrency(totalBuy)}</Text>
              </HStack>
              <HStack justify="space-between" mt="4px">
                <Text fontSize="xs" color="gray.200">Annual cost (4 rebalances):</Text>
                <Text fontSize="xs" color="gray.200" fontFamily="mono">~{formatPercent(costPercentage * 4)}</Text>
              </HStack>
            </VStack>
          </Box>
        </VStack>

        <HStack gap="8px" mt="16px" flexWrap="wrap">
          {showReminderInput ? (
            <HStack gap="8px">
              <Input
                size="sm"
                placeholder="your@email.com"
                value={reminderEmail}
                onChange={(e) => setReminderEmail(e.target.value)}
                bg="gray.600"
                borderColor="gray.500"
                width="180px"
              />
              <Button size="sm" bg="brand.500" color="white" onClick={sendReminder}>Send</Button>
              <Button size="sm" variant="ghost" color="gray.200" onClick={() => setShowReminderInput(false)}>Cancel</Button>
            </HStack>
          ) : (
            <Button size="sm" variant="outline" borderColor="brand.500" color="brand.500" onClick={() => setShowReminderInput(true)}>
              Set Reminder
            </Button>
          )}
          <Link to="/backtesting">
            <Button size="sm" variant="outline" borderColor="brand.500" color="brand.500">
              Simulate in Backtest
            </Button>
          </Link>
        </HStack>
      </Box>
    </VStack>
  );
}
