import { useState, useEffect, useMemo } from 'react';
import { Box, Text, VStack, HStack, Flex, SimpleGrid } from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';

const STRATEGIES = [
  { key: 'sammansatt_momentum', label: 'Momentum', color: '#4299E1', rebalance: 'quarterly' },
  { key: 'trendande_varde', label: 'Värde', color: '#48BB78', rebalance: 'annual' },
  { key: 'trendande_utdelning', label: 'Utdelning', color: '#9F7AEA', rebalance: 'annual' },
  { key: 'trendande_kvalitet', label: 'Kvalitet', color: '#ED8936', rebalance: 'annual' },
];

// Data is considered fresh if updated within last 3 days
const FRESH_THRESHOLD_DAYS = 3;

type Action = {
  type: 'SELL_NOW' | 'SELL_SOON' | 'BUY' | 'HOLD';
  ticker: string;
  name: string;
  strategy: string;
  strategyColor: string;
  value: number;
  reason: string;
  rank?: number;
  dataAgeDays?: number;
};

type Holding = { ticker: string; shares: number; avgPrice?: number };

export default function MinStrategiPage() {
  const [selected, setSelected] = useState<string[]>(() => {
    const saved = localStorage.getItem('selectedStrategies');
    return saved ? JSON.parse(saved) : ['sammansatt_momentum'];
  });
  const [strategyData, setStrategyData] = useState<Record<string, any[]>>({});
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [rebalanceDates, setRebalanceDates] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ SELL_NOW: true, BUY: true });

  // Load holdings from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('myHoldings');
    if (saved) setHoldings(JSON.parse(saved));
  }, []);

  // Persist selection
  useEffect(() => {
    localStorage.setItem('selectedStrategies', JSON.stringify(selected));
  }, [selected]);

  // Fetch strategy data
  useEffect(() => {
    selected.forEach(key => {
      if (!strategyData[key]) {
        api.getStrategyRankings(key).then(data => {
          setStrategyData(prev => ({ ...prev, [key]: data }));
        });
      }
    });
  }, [selected]);

  // Fetch rebalance dates
  useEffect(() => {
    api.getRebalanceDates().then(setRebalanceDates).catch(() => {});
  }, []);

  // Fetch prices for holdings
  useEffect(() => {
    holdings.forEach(h => {
      if (!prices[h.ticker]) {
        api.getStockPrices(h.ticker, 1).then(data => {
          if (data.prices?.[0]) setPrices(prev => ({ ...prev, [h.ticker]: data.prices[0].close }));
        }).catch(() => {});
      }
    });
  }, [holdings]);

  // Generate actions
  const actions = useMemo(() => {
    const result: Action[] = [];
    const targetTickers = new Set<string>();
    const holdingMap = new Map(holdings.map(h => [h.ticker, h]));

    // Collect all target stocks from selected strategies
    selected.forEach(key => {
      const stocks = strategyData[key] || [];
      const strategyInfo = STRATEGIES.find(s => s.key === key)!;
      stocks.slice(0, 10).forEach((stock, i) => {
        targetTickers.add(stock.ticker);
        const holding = holdingMap.get(stock.ticker);
        if (holding) {
          result.push({
            type: 'HOLD',
            ticker: stock.ticker,
            name: stock.name,
            strategy: strategyInfo.label,
            strategyColor: strategyInfo.color,
            value: holding.shares * (prices[stock.ticker] || holding.avgPrice || 0),
            reason: `Rank #${i + 1} - behåll`,
            rank: i + 1,
            dataAgeDays: stock.data_age_days,
          });
        } else {
          result.push({
            type: 'BUY',
            ticker: stock.ticker,
            name: stock.name,
            strategy: strategyInfo.label,
            strategyColor: strategyInfo.color,
            value: 0,
            reason: `Ny i ${strategyInfo.label}`,
            rank: i + 1,
            dataAgeDays: stock.data_age_days,
          });
        }
      });
    });

    // Find stocks to sell (in holdings but not in targets)
    holdings.forEach(h => {
      if (!targetTickers.has(h.ticker)) {
        result.push({
          type: 'SELL_NOW',
          ticker: h.ticker,
          name: h.ticker,
          strategy: '-',
          strategyColor: '#718096',
          value: h.shares * (prices[h.ticker] || h.avgPrice || 0),
          reason: 'Inte i vald strategi',
        });
      }
    });

    return result;
  }, [selected, strategyData, holdings, prices]);

  // Calculate freshness stats
  const freshnessStats = useMemo(() => {
    const allStocks = actions.filter(a => a.dataAgeDays !== undefined);
    const fresh = allStocks.filter(a => (a.dataAgeDays || 0) <= FRESH_THRESHOLD_DAYS);
    return { fresh: fresh.length, total: allStocks.length };
  }, [actions]);

  const grouped = useMemo(() => ({
    SELL_NOW: actions.filter(a => a.type === 'SELL_NOW'),
    SELL_SOON: actions.filter(a => a.type === 'SELL_SOON'),
    BUY: actions.filter(a => a.type === 'BUY'),
    HOLD: actions.filter(a => a.type === 'HOLD'),
  }), [actions]);

  const toggleStrategy = (key: string) => {
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const nextRebalance = rebalanceDates.find(r => selected.includes(r.strategy_name));
  const daysUntil = nextRebalance ? Math.ceil((new Date(nextRebalance.next_date).getTime() - Date.now()) / 86400000) : null;

  const portfolioValue = holdings.reduce((sum, h) => sum + h.shares * (prices[h.ticker] || h.avgPrice || 0), 0);

  return (
    <VStack gap="24px" align="stretch">
      <Flex justify="space-between" align="flex-start" flexWrap="wrap" gap="12px">
        <Box>
          <Text fontSize="2xl" fontWeight="bold" color="gray.50">Min Strategi</Text>
          <Text color="gray.400" fontSize="sm">Välj strategier och se alla rekommendationer</Text>
        </Box>
        {/* Freshness Indicator */}
        {freshnessStats.total > 0 && (
          <HStack 
            bg={freshnessStats.fresh === freshnessStats.total ? 'green.900' : 'yellow.900'} 
            px="12px" 
            py="6px" 
            borderRadius="6px"
            title={`Data räknas som färsk om den uppdaterats inom ${FRESH_THRESHOLD_DAYS} dagar`}
          >
            <Box 
              w="8px" 
              h="8px" 
              borderRadius="full" 
              bg={freshnessStats.fresh === freshnessStats.total ? 'green.400' : 'yellow.400'} 
            />
            <Text fontSize="sm" color={freshnessStats.fresh === freshnessStats.total ? 'green.200' : 'yellow.200'}>
              {freshnessStats.fresh}/{freshnessStats.total} färsk data
            </Text>
          </HStack>
        )}
      </Flex>

      {/* Data Stale Warning */}
      {freshnessStats.total > 0 && freshnessStats.fresh < freshnessStats.total && (
        <Box bg="yellow.900" border="1px solid" borderColor="yellow.600" borderRadius="8px" p="12px">
          <HStack gap="8px">
            <Text>⚠️</Text>
            <Box>
              <Text fontSize="sm" color="yellow.200" fontWeight="medium">
                {freshnessStats.total - freshnessStats.fresh} aktier har gammal data
              </Text>
              <Text fontSize="xs" color="yellow.300">
                Data äldre än {FRESH_THRESHOLD_DAYS} dagar kan ge felaktiga rekommendationer. Synka data i inställningar.
              </Text>
            </Box>
          </HStack>
        </Box>
      )}

      {/* Strategy Selector */}
      <HStack gap="8px" flexWrap="wrap">
        {STRATEGIES.map(s => (
          <Box
            key={s.key}
            as="button"
            px="16px"
            py="10px"
            borderRadius="8px"
            bg={selected.includes(s.key) ? s.color : 'gray.700'}
            color="white"
            fontWeight="medium"
            fontSize="sm"
            onClick={() => toggleStrategy(s.key)}
            opacity={selected.includes(s.key) ? 1 : 0.6}
            border="2px solid"
            borderColor={selected.includes(s.key) ? s.color : 'gray.600'}
            _hover={{ opacity: 1 }}
            transition="all 150ms"
          >
            {selected.includes(s.key) ? '✓ ' : ''}{s.label}
          </Box>
        ))}
      </HStack>

      {/* Summary Cards */}
      <SimpleGrid columns={{ base: 2, md: 4 }} gap="12px">
        <SummaryCard label="Målaktier" value={grouped.BUY.length + grouped.HOLD.length} />
        <SummaryCard label="Har du" value={holdings.length} />
        <SummaryCard label="Köp" value={grouped.BUY.length} color="#48BB78" />
        <SummaryCard label="Sälj" value={grouped.SELL_NOW.length} color="#F56565" />
      </SimpleGrid>

      {/* Next Rebalance */}
      {daysUntil !== null && (
        <Box bg="gray.700" borderRadius="8px" p="12px">
          <Text fontSize="sm" color="gray.300">
            Nästa ombalansering: <Text as="span" color="gray.50" fontWeight="medium">{daysUntil} dagar</Text>
            {nextRebalance && ` (${new Date(nextRebalance.next_date).toLocaleDateString('sv-SE')})`}
          </Text>
        </Box>
      )}

      {selected.length === 0 ? (
        <EmptyState icon="📊" title="Välj strategier ovan" subtitle="för att se rekommendationer" />
      ) : holdings.length === 0 ? (
        <EmptyState icon="📁" title="Importera dina innehav" subtitle="för att se köp/sälj-rekommendationer" link="/portfolio/my" linkText="Importera CSV" />
      ) : (
        <>
          {/* Action Sections */}
          <ActionSection
            title="🔴 Sälj nu"
            items={grouped.SELL_NOW}
            expanded={expanded.SELL_NOW}
            onToggle={() => setExpanded(p => ({ ...p, SELL_NOW: !p.SELL_NOW }))}
            portfolioValue={portfolioValue}
          />
          <ActionSection
            title="🟢 Köp"
            items={grouped.BUY}
            expanded={expanded.BUY}
            onToggle={() => setExpanded(p => ({ ...p, BUY: !p.BUY }))}
            portfolioValue={portfolioValue}
            targetCount={grouped.BUY.length + grouped.HOLD.length}
          />
          <ActionSection
            title="✓ Behåll"
            items={grouped.HOLD}
            expanded={expanded.HOLD}
            onToggle={() => setExpanded(p => ({ ...p, HOLD: !p.HOLD }))}
            portfolioValue={portfolioValue}
          />
        </>
      )}
    </VStack>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Box bg="gray.700" borderRadius="8px" p="16px" borderLeft="3px solid" borderLeftColor={color || 'gray.600'}>
      <Text fontSize="2xl" fontWeight="bold" color={color || 'gray.50'}>{value}</Text>
      <Text fontSize="sm" color="gray.400">{label}</Text>
    </Box>
  );
}

function ActionSection({ title, items, expanded, onToggle, portfolioValue, targetCount }: {
  title: string;
  items: Action[];
  expanded: boolean;
  onToggle: () => void;
  portfolioValue: number;
  targetCount?: number;
}) {
  if (items.length === 0) return null;
  const targetValue = targetCount ? portfolioValue / targetCount : 0;

  return (
    <Box bg="gray.700" borderRadius="8px" overflow="hidden">
      <Flex
        as="button"
        w="100%"
        p="16px"
        justify="space-between"
        align="center"
        onClick={onToggle}
        _hover={{ bg: 'gray.650' }}
        transition="background 150ms"
      >
        <HStack gap="8px">
          <Text fontWeight="semibold" color="gray.50">{title}</Text>
          <Box bg="gray.600" px="8px" py="2px" borderRadius="full">
            <Text fontSize="xs" color="gray.300">{items.length}</Text>
          </Box>
        </HStack>
        <Text color="gray.400">{expanded ? '−' : '+'}</Text>
      </Flex>
      {expanded && (
        <VStack gap="8px" p="16px" pt="0" align="stretch">
          {items.map((item, i) => (
            <Link key={`${item.ticker}-${item.strategy}-${i}`} to={`/stock/${item.ticker}`}>
              <Box
                p="12px"
                borderRadius="6px"
                bg={`${item.strategyColor}10`}
                borderLeft="3px solid"
                borderLeftColor={item.strategyColor}
                _hover={{ bg: `${item.strategyColor}18` }}
                transition="background 150ms"
              >
                <Flex justify="space-between" align="flex-start">
                  <Box>
                    <HStack gap="8px">
                      <Text fontWeight="semibold" color="gray.50">{item.ticker}</Text>
                      <Box bg={`${item.strategyColor}30`} px="6px" py="1px" borderRadius="4px">
                        <Text fontSize="xs" color="gray.200">{item.strategy}</Text>
                      </Box>
                    </HStack>
                    <Text fontSize="sm" color="gray.400" mt="2px">{item.reason}</Text>
                  </Box>
                  <Text fontSize="sm" color="gray.300" textAlign="right">
                    {item.type === 'BUY' && targetValue > 0 ? `Köp ${formatSEK(targetValue)}` : 
                     item.value > 0 ? formatSEK(item.value) : ''}
                  </Text>
                </Flex>
              </Box>
            </Link>
          ))}
        </VStack>
      )}
    </Box>
  );
}

function EmptyState({ icon, title, subtitle, link, linkText }: { icon: string; title: string; subtitle: string; link?: string; linkText?: string }) {
  return (
    <Box bg="gray.700" borderRadius="8px" p="48px" textAlign="center">
      <Text fontSize="3xl" mb="12px">{icon}</Text>
      <Text color="gray.300" fontWeight="medium">{title}</Text>
      <Text color="gray.500" fontSize="sm">{subtitle}</Text>
      {link && (
        <Link to={link}>
          <Box as="span" color="brand.400" fontSize="sm" mt="12px" display="inline-block" _hover={{ textDecoration: 'underline' }}>
            {linkText}
          </Box>
        </Link>
      )}
    </Box>
  );
}

function formatSEK(value: number): string {
  return new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 }).format(value);
}
