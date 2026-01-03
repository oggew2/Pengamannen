import { useState, useEffect, useMemo } from 'react';
import { Box, Text, VStack, HStack, Flex, SimpleGrid, Input, Button } from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';

const STRATEGIES = [
  { key: 'sammansatt_momentum', label: 'Momentum', color: '#4299E1', rebalance: 'quarterly', desc: 'Kvartalsvis' },
  { key: 'trendande_varde', label: 'Värde', color: '#48BB78', rebalance: 'annual', desc: 'Årsvis' },
  { key: 'trendande_utdelning', label: 'Utdelning', color: '#9F7AEA', rebalance: 'annual', desc: 'Årsvis' },
  { key: 'trendande_kvalitet', label: 'Kvalitet', color: '#ED8936', rebalance: 'annual', desc: 'Årsvis' },
];

type Holding = { ticker: string; shares: number; avgPrice: number };
type Action = { type: 'SELL' | 'BUY' | 'HOLD'; ticker: string; name: string; strategy: string; strategyColor: string; value: number; reason: string; rank?: number; targetValue?: number };

// Storage keys - will be migrated to backend for multi-user
const STORAGE_KEYS = {
  strategies: 'selectedStrategies',
  holdings: 'myHoldings',
  settings: 'rebalanceSettings',
};

export default function MinStrategiPage() {
  const [tab, setTab] = useState<'strategier' | 'portfolj' | 'rebalansering'>('strategier');
  
  // Strategy state
  const [selected, setSelected] = useState<string[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.strategies);
    return saved ? JSON.parse(saved) : ['sammansatt_momentum'];
  });
  const [strategyData, setStrategyData] = useState<Record<string, any[]>>({});
  
  // Portfolio state
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [importResult, setImportResult] = useState<{ holdings: { ticker: string; shares: number }[]; total_fees_paid: number } | null>(null);
  const [newTicker, setNewTicker] = useState('');
  const [newShares, setNewShares] = useState('');
  const [newPrice, setNewPrice] = useState('');
  
  // Rebalancing state
  const [settings, setSettings] = useState<{ bandingPercent: number; reminders: { weekBefore: boolean; dayBefore: boolean } }>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.settings);
    return saved ? JSON.parse(saved) : { bandingPercent: 20, reminders: { weekBefore: true, dayBefore: true } };
  });
  const [_trades, setTrades] = useState<{ ticker: string; action: string; shares: number }[]>([]);
  const [costs, setCosts] = useState<{ courtage: number; spread_estimate: number; total: number; percentage: number } | null>(null);
  const [loadingTrades, setLoadingTrades] = useState(false);

  // Load holdings
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.holdings);
    if (saved) setHoldings(JSON.parse(saved));
  }, []);

  // Persist selections
  useEffect(() => { localStorage.setItem(STORAGE_KEYS.strategies, JSON.stringify(selected)); }, [selected]);
  useEffect(() => { localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(settings)); }, [settings]);

  // Fetch strategy data
  useEffect(() => {
    selected.forEach(key => {
      if (!strategyData[key]) {
        api.getStrategyRankings(key).then(data => setStrategyData(prev => ({ ...prev, [key]: data })));
      }
    });
  }, [selected, strategyData]);

  // Fetch prices
  useEffect(() => {
    holdings.forEach(h => {
      if (!prices[h.ticker]) {
        api.getStockPrices(h.ticker, 1).then(data => {
          if (data.prices?.[0]) setPrices(prev => ({ ...prev, [h.ticker]: data.prices[0].close }));
        }).catch(() => {});
      }
    });
  }, [holdings, prices]);

  const toggleStrategy = (key: string) => {
    setSelected(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  // Combined picks from selected strategies
  const picks = useMemo(() => {
    const result: { ticker: string; name: string; strategies: { key: string; label: string; color: string; rank: number }[] }[] = [];
    const tickerMap = new Map<string, typeof result[0]>();
    
    selected.forEach(key => {
      const stocks = strategyData[key] || [];
      const info = STRATEGIES.find(s => s.key === key)!;
      stocks.slice(0, 10).forEach((stock, i) => {
        const existing = tickerMap.get(stock.ticker);
        if (existing) {
          existing.strategies.push({ key, label: info.label, color: info.color, rank: i + 1 });
        } else {
          const item = { ticker: stock.ticker, name: stock.name, strategies: [{ key, label: info.label, color: info.color, rank: i + 1 }] };
          tickerMap.set(stock.ticker, item);
          result.push(item);
        }
      });
    });
    return result;
  }, [selected, strategyData]);

  // Actions (buy/sell/hold)
  const actions = useMemo(() => {
    const result: Action[] = [];
    const targetTickers = new Set(picks.map(p => p.ticker));
    const holdingMap = new Map(holdings.map(h => [h.ticker, h]));
    const portfolioValue = holdings.reduce((sum, h) => sum + h.shares * (prices[h.ticker] || h.avgPrice || 0), 0);
    const targetCount = picks.length;
    const targetValue = targetCount > 0 ? portfolioValue / targetCount : 0;

    picks.forEach(p => {
      const holding = holdingMap.get(p.ticker);
      const strategyInfo = p.strategies[0];
      if (holding) {
        const value = holding.shares * (prices[p.ticker] || holding.avgPrice || 0);
        result.push({ type: 'HOLD', ticker: p.ticker, name: p.name, strategy: strategyInfo.label, strategyColor: strategyInfo.color, value, reason: `Rank #${strategyInfo.rank}`, rank: strategyInfo.rank });
      } else {
        result.push({ type: 'BUY', ticker: p.ticker, name: p.name, strategy: strategyInfo.label, strategyColor: strategyInfo.color, value: 0, reason: `Ny i ${strategyInfo.label}`, rank: strategyInfo.rank, targetValue });
      }
    });

    holdings.forEach(h => {
      if (!targetTickers.has(h.ticker)) {
        result.push({ type: 'SELL', ticker: h.ticker, name: h.ticker, strategy: '-', strategyColor: '#718096', value: h.shares * (prices[h.ticker] || h.avgPrice || 0), reason: 'Inte i vald strategi' });
      }
    });

    return result;
  }, [picks, holdings, prices]);

  const portfolioValue = holdings.reduce((sum, h) => sum + h.shares * (prices[h.ticker] || h.avgPrice || 0), 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.avgPrice, 0);
  const pnl = portfolioValue - totalCost;

  // CSV Import
  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/v1/import/avanza-csv', { method: 'POST', body: formData, credentials: 'include' });
      setImportResult(await res.json());
    } catch { setImportResult(null); }
  };

  const applyImport = () => {
    if (!importResult) return;
    const newHoldings = importResult.holdings.map(h => ({ ticker: h.ticker, shares: h.shares, avgPrice: 0 }));
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(newHoldings));
    setImportResult(null);
  };

  const addHolding = () => {
    if (!newTicker || !newShares) return;
    const updated = [...holdings, { ticker: newTicker.toUpperCase(), shares: +newShares, avgPrice: +newPrice || 0 }];
    setHoldings(updated);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(updated));
    setNewTicker(''); setNewShares(''); setNewPrice('');
  };

  const removeHolding = (ticker: string) => {
    const updated = holdings.filter(h => h.ticker !== ticker);
    setHoldings(updated);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(updated));
  };

  const generateTrades = async () => {
    if (holdings.length === 0 || selected.length === 0) return;
    setLoadingTrades(true);
    try {
      const currentHoldings = holdings.map(h => ({ ticker: h.ticker, value: h.shares * (prices[h.ticker] || h.avgPrice), shares: h.shares }));
      const data = await api.getRebalanceTrades(selected[0], portfolioValue || 100000, currentHoldings);
      setTrades(data.trades || []);
      setCosts(data.costs || null);
    } catch { setTrades([]); setCosts(null); }
    setLoadingTrades(false);
  };

  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 }).format(v);

  return (
    <VStack gap="24px" align="stretch">
      {/* Header */}
      <Box>
        <Text fontSize="2xl" fontWeight="bold" color="fg">Min Strategi</Text>
        <Text color="fg.muted" fontSize="sm">Välj strategier, hantera portfölj och rebalansera</Text>
      </Box>

      {/* Tabs */}
      <HStack gap="0" borderBottom="1px solid" borderColor="border">
        {[
          { key: 'strategier', label: 'Strategier', icon: '📊' },
          { key: 'portfolj', label: 'Portfölj', icon: '💼' },
          { key: 'rebalansering', label: 'Rebalansering', icon: '⚖️' },
        ].map(t => (
          <Box
            key={t.key}
            as="button"
            px="20px"
            py="12px"
            color={tab === t.key ? 'fg' : 'fg.muted'}
            borderBottom="2px solid"
            borderColor={tab === t.key ? 'brand.solid' : 'transparent'}
            fontWeight={tab === t.key ? 'semibold' : 'normal'}
            fontSize="sm"
            onClick={() => setTab(t.key as any)}
            _hover={{ color: 'fg' }}
            transition="all 150ms"
          >
            {t.icon} {t.label}
          </Box>
        ))}
      </HStack>

      {/* Tab Content */}
      {tab === 'strategier' && (
        <VStack gap="20px" align="stretch">
          {/* Strategy Selector */}
          <Box>
            <Text fontSize="sm" fontWeight="semibold" color="fg" mb="12px">Välj strategier att följa</Text>
            <SimpleGrid columns={{ base: 2, md: 4 }} gap="12px">
              {STRATEGIES.map(s => (
                <Box
                  key={s.key}
                  as="button"
                  p="16px"
                  borderRadius="8px"
                  bg={selected.includes(s.key) ? `${s.color}20` : 'bg.subtle'}
                  border="2px solid"
                  borderColor={selected.includes(s.key) ? s.color : 'border'}
                  onClick={() => toggleStrategy(s.key)}
                  textAlign="left"
                  _hover={{ borderColor: s.color }}
                  transition="all 150ms"
                >
                  <HStack justify="space-between" mb="4px">
                    <Text fontWeight="semibold" color="fg">{s.label}</Text>
                    {selected.includes(s.key) && <Text color={s.color}>✓</Text>}
                  </HStack>
                  <Text fontSize="xs" color="fg.muted">{s.desc}</Text>
                </Box>
              ))}
            </SimpleGrid>
          </Box>

          {/* Picks Summary */}
          {selected.length > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Flex justify="space-between" align="center" mb="12px">
                <Text fontWeight="semibold" color="fg">
                  {picks.length} aktier i dina strategier
                </Text>
                <Text fontSize="sm" color="fg.muted">
                  {picks.filter(p => p.strategies.length > 1).length} överlapp
                </Text>
              </Flex>
              <VStack gap="8px" align="stretch" maxH="400px" overflowY="auto">
                {picks.map(p => (
                  <Link key={p.ticker} to={`/stock/${p.ticker}`}>
                    <Flex
                      p="12px"
                      bg="bg.muted"
                      borderRadius="6px"
                      justify="space-between"
                      align="center"
                      _hover={{ bg: 'bg.hover' }}
                      transition="background 150ms"
                    >
                      <HStack gap="12px">
                        <Text fontWeight="semibold" color="fg" fontFamily="mono">{p.ticker}</Text>
                        <Text fontSize="sm" color="fg.muted" maxW="150px" truncate>{p.name}</Text>
                      </HStack>
                      <HStack gap="4px">
                        {p.strategies.map(s => (
                          <Box key={s.key} bg={`${s.color}30`} px="6px" py="2px" borderRadius="4px">
                            <Text fontSize="xs" color="fg">#{s.rank}</Text>
                          </Box>
                        ))}
                      </HStack>
                    </Flex>
                  </Link>
                ))}
              </VStack>
              <Text fontSize="xs" color="fg.muted" mt="12px">
                💡 Klicka på en aktie för mer information. Gå till Portfölj-fliken för att importera dina innehav.
              </Text>
            </Box>
          )}

          {selected.length === 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center">
              <Text fontSize="3xl" mb="12px">📊</Text>
              <Text color="fg.muted">Välj minst en strategi ovan</Text>
            </Box>
          )}
        </VStack>
      )}

      {tab === 'portfolj' && (
        <VStack gap="20px" align="stretch">
          {/* Portfolio Summary */}
          <SimpleGrid columns={{ base: 2, md: 3 }} gap="12px">
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Text fontSize="xs" color="fg.muted">Portföljvärde</Text>
              <Text fontSize="xl" fontWeight="bold" color="fg">{formatSEK(portfolioValue)}</Text>
            </Box>
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Text fontSize="xs" color="fg.muted">Vinst/Förlust</Text>
              <Text fontSize="xl" fontWeight="bold" color={pnl >= 0 ? 'success' : 'error'}>
                {pnl >= 0 ? '+' : ''}{formatSEK(pnl)}
              </Text>
            </Box>
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Text fontSize="xs" color="fg.muted">Antal innehav</Text>
              <Text fontSize="xl" fontWeight="bold" color="fg">{holdings.length}</Text>
            </Box>
          </SimpleGrid>

          {/* CSV Import */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px" borderStyle="dashed">
            <Text fontWeight="semibold" color="fg" mb="8px">📁 Importera från Avanza</Text>
            <Text fontSize="sm" color="fg.muted" mb="12px">
              Exportera transaktioner: Avanza → Konto → Transaktioner → Exportera CSV
            </Text>
            <Input type="file" accept=".csv" onChange={handleCsvImport} size="sm" bg="bg.muted" borderColor="border" />
            {importResult && (
              <Box mt="12px" p="12px" bg="brand.subtle" borderRadius="6px">
                <Text fontSize="sm" color="fg">Hittade {importResult.holdings.length} aktier</Text>
                <Button size="sm" mt="8px" colorPalette="blue" onClick={applyImport}>Importera</Button>
              </Box>
            )}
          </Box>

          {/* Manual Add */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
            <Text fontWeight="semibold" color="fg" mb="12px">Lägg till manuellt</Text>
            <HStack gap="8px" flexWrap="wrap">
              <Input size="sm" placeholder="Ticker" value={newTicker} onChange={e => setNewTicker(e.target.value)} bg="bg.muted" borderColor="border" flex="1" minW="100px" />
              <Input size="sm" type="number" placeholder="Antal" value={newShares} onChange={e => setNewShares(e.target.value)} bg="bg.muted" borderColor="border" w="80px" />
              <Input size="sm" type="number" placeholder="GAV" value={newPrice} onChange={e => setNewPrice(e.target.value)} bg="bg.muted" borderColor="border" w="80px" />
              <Button size="sm" colorPalette="blue" onClick={addHolding}>Lägg till</Button>
            </HStack>
          </Box>

          {/* Holdings List */}
          {holdings.length > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Text fontWeight="semibold" color="fg" mb="12px">Dina innehav</Text>
              <VStack gap="8px" align="stretch">
                {holdings.map(h => {
                  const price = prices[h.ticker] || h.avgPrice;
                  const value = h.shares * price;
                  const holdingPnl = h.avgPrice > 0 ? value - h.shares * h.avgPrice : 0;
                  return (
                    <Flex key={h.ticker} p="12px" bg="bg.muted" borderRadius="6px" justify="space-between" align="center">
                      <HStack gap="12px">
                        <Text fontWeight="semibold" color="fg" fontFamily="mono">{h.ticker}</Text>
                        <Text fontSize="sm" color="fg.muted">{h.shares} st</Text>
                      </HStack>
                      <HStack gap="12px">
                        <Text fontSize="sm" color="fg">{formatSEK(value)}</Text>
                        {holdingPnl !== 0 && (
                          <Text fontSize="sm" color={holdingPnl >= 0 ? 'success' : 'error'}>
                            {holdingPnl >= 0 ? '+' : ''}{formatSEK(holdingPnl)}
                          </Text>
                        )}
                        <Box as="button" aria-label={`Remove ${h.ticker}`} color="fg.muted" _hover={{ color: 'error' }} onClick={() => removeHolding(h.ticker)}>✕</Box>
                      </HStack>
                    </Flex>
                  );
                })}
              </VStack>
            </Box>
          )}

          {holdings.length === 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center">
              <Text fontSize="3xl" mb="12px">💼</Text>
              <Text color="fg.muted">Importera eller lägg till innehav ovan</Text>
            </Box>
          )}
        </VStack>
      )}

      {tab === 'rebalansering' && (
        <VStack gap="20px" align="stretch">
          {/* Banding Settings */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
            <Text fontWeight="semibold" color="fg" mb="12px">⚖️ Toleransband</Text>
            <HStack gap="16px" align="center" mb="8px">
              <Text fontSize="sm" color="fg.muted">Rebalansera vid avvikelse över:</Text>
              <HStack gap="8px">
                <Input
                  type="number"
                  size="sm"
                  w="70px"
                  value={settings.bandingPercent}
                  onChange={e => setSettings(s => ({ ...s, bandingPercent: +e.target.value }))}
                  bg="bg.muted"
                  borderColor="border"
                />
                <Text color="fg">%</Text>
              </HStack>
            </HStack>
            <Text fontSize="xs" color="fg.muted">
              💡 Med {settings.bandingPercent}% tolerans och 10% målvikt per aktie: sälj om &gt;{10 + settings.bandingPercent * 0.1}%, köp om &lt;{10 - settings.bandingPercent * 0.1}%
            </Text>
          </Box>

          {/* Timing Recommendations */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
            <Text fontWeight="semibold" color="fg" mb="12px">📅 Rekommenderad timing</Text>
            <VStack gap="8px" align="stretch">
              {STRATEGIES.filter(s => selected.includes(s.key)).map(s => (
                <Flex key={s.key} justify="space-between" align="center" p="8px" bg="bg.muted" borderRadius="6px">
                  <HStack gap="8px">
                    <Box w="8px" h="8px" borderRadius="full" bg={s.color} />
                    <Text fontSize="sm" color="fg">{s.label}</Text>
                  </HStack>
                  <Text fontSize="sm" color="fg.muted">{s.desc} (mars, juni, sep, dec)</Text>
                </Flex>
              ))}
            </VStack>
            {selected.length === 0 && <Text fontSize="sm" color="fg.muted">Välj strategier i första fliken</Text>}
          </Box>

          {/* Actions Summary */}
          {holdings.length > 0 && selected.length > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
              <Flex justify="space-between" align="center" mb="16px">
                <Text fontWeight="semibold" color="fg">Rekommenderade åtgärder</Text>
                <Button size="sm" colorPalette="blue" onClick={generateTrades} loading={loadingTrades}>
                  Generera affärer
                </Button>
              </Flex>
              
              <SimpleGrid columns={3} gap="12px" mb="16px">
                <Box p="12px" bg="error.subtle" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="error.fg">{actions.filter(a => a.type === 'SELL').length}</Text>
                  <Text fontSize="xs" color="fg.muted">Sälj</Text>
                </Box>
                <Box p="12px" bg="success.subtle" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="success.fg">{actions.filter(a => a.type === 'BUY').length}</Text>
                  <Text fontSize="xs" color="fg.muted">Köp</Text>
                </Box>
                <Box p="12px" bg="bg.muted" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="fg">{actions.filter(a => a.type === 'HOLD').length}</Text>
                  <Text fontSize="xs" color="fg.muted">Behåll</Text>
                </Box>
              </SimpleGrid>

              {/* Sell List */}
              {actions.filter(a => a.type === 'SELL').length > 0 && (
                <Box mb="12px">
                  <Text fontSize="sm" fontWeight="semibold" color="error.fg" mb="8px">🔴 Sälj</Text>
                  <VStack gap="4px" align="stretch">
                    {actions.filter(a => a.type === 'SELL').map(a => (
                      <Flex key={a.ticker} p="8px" bg="bg.muted" borderRadius="4px" justify="space-between">
                        <Text fontSize="sm" color="fg" fontFamily="mono">{a.ticker}</Text>
                        <Text fontSize="sm" color="fg.muted">{formatSEK(a.value)}</Text>
                      </Flex>
                    ))}
                  </VStack>
                </Box>
              )}

              {/* Buy List */}
              {actions.filter(a => a.type === 'BUY').length > 0 && (
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" color="success.fg" mb="8px">🟢 Köp</Text>
                  <VStack gap="4px" align="stretch">
                    {actions.filter(a => a.type === 'BUY').map(a => (
                      <Flex key={a.ticker} p="8px" bg="bg.muted" borderRadius="4px" justify="space-between">
                        <HStack gap="8px">
                          <Text fontSize="sm" color="fg" fontFamily="mono">{a.ticker}</Text>
                          <Text fontSize="xs" color="fg.muted">{a.reason}</Text>
                        </HStack>
                        <Text fontSize="sm" color="fg.muted">{a.targetValue ? formatSEK(a.targetValue) : '-'}</Text>
                      </Flex>
                    ))}
                  </VStack>
                </Box>
              )}

              {/* Cost Estimate */}
              {costs && (
                <Box mt="16px" p="12px" bg="bg.muted" borderRadius="6px">
                  <Text fontSize="sm" fontWeight="semibold" color="fg" mb="4px">💰 Uppskattad kostnad</Text>
                  <Text fontSize="sm" color="fg.muted">
                    Courtage: {formatSEK(costs.courtage)} • Spread: {formatSEK(costs.spread_estimate)} • Totalt: {formatSEK(costs.total)} ({costs.percentage?.toFixed(2)}%)
                  </Text>
                </Box>
              )}
            </Box>
          )}

          {(holdings.length === 0 || selected.length === 0) && (
            <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center">
              <Text fontSize="3xl" mb="12px">⚖️</Text>
              <Text color="fg.muted">
                {holdings.length === 0 ? 'Importera innehav i Portfölj-fliken först' : 'Välj strategier i första fliken'}
              </Text>
            </Box>
          )}
        </VStack>
      )}
    </VStack>
  );
}
