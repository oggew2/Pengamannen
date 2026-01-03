import { useState, useEffect, useMemo } from 'react';
import { Box, Text, VStack, HStack, Flex, SimpleGrid, Input, Button } from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { api } from '../api/client';
import { useRebalanceDates, queryKeys } from '../api/hooks';
import { toaster } from '../components/toaster';

const STRATEGIES = [
  { key: 'sammansatt_momentum', label: 'Momentum', color: '#4299E1', rebalance: 'quarterly', desc: 'Kvartalsvis' },
  { key: 'trendande_varde', label: 'Värde', color: '#48BB78', rebalance: 'annual', desc: 'Årsvis' },
  { key: 'trendande_utdelning', label: 'Utdelning', color: '#9F7AEA', rebalance: 'annual', desc: 'Årsvis' },
  { key: 'trendande_kvalitet', label: 'Kvalitet', color: '#ED8936', rebalance: 'annual', desc: 'Årsvis' },
];

type Holding = { ticker: string; shares: number; avgPrice: number };
type Action = { type: 'SELL' | 'BUY' | 'HOLD'; ticker: string; name: string; strategy: string; strategyColor: string; value: number; reason: string; rank?: number; targetValue?: number };
type BandingResult = {
  keeps: { ticker: string; rank: number; name: string }[];
  sells: { ticker: string; rank: number | null; name: string | null; reason: string }[];
  watch: { ticker: string; rank: number; name: string }[];
  suggested_buys: { ticker: string; rank: number; name: string }[];
  thresholds: { buy_rank: number; sell_rank: number; universe_size: number };
  summary: { total_holdings: number; to_keep: number; to_sell: number; in_danger_zone: number };
};

// Storage keys
const STORAGE_KEYS = {
  strategies: 'selectedStrategies',
  holdings: 'myHoldings',
  settings: 'rebalanceSettings',
  momentumHoldings: 'momentumHoldings',
};

export default function MinStrategiPage() {
  const [tab, setTab] = useState<'strategier' | 'portfolj' | 'rebalansering'>('strategier');
  
  // Strategy state
  const [selected, setSelected] = useState<string[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.strategies);
    return saved ? JSON.parse(saved) : ['sammansatt_momentum'];
  });
  
  // Portfolio state
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [importResult, setImportResult] = useState<{ holdings: { ticker: string; shares: number }[]; total_fees_paid: number } | null>(null);
  const [newTicker, setNewTicker] = useState('');
  const [newShares, setNewShares] = useState('');
  const [newPrice, setNewPrice] = useState('');
  
  // Rebalancing state
  const [settings, setSettings] = useState<{ bandingPercent: number; reminders: { weekBefore: boolean; dayBefore: boolean }; bandingMode: boolean }>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.settings);
    return saved ? JSON.parse(saved) : { bandingPercent: 20, reminders: { weekBefore: true, dayBefore: true }, bandingMode: false };
  });
  const [_trades, setTrades] = useState<{ ticker: string; action: string; shares: number }[]>([]);
  const [costs, setCosts] = useState<{ courtage: number; spread_estimate: number; total: number; percentage: number } | null>(null);
  const [loadingTrades, setLoadingTrades] = useState(false);

  // Investment suggestion state
  const [investAmount, setInvestAmount] = useState(() => {
    const saved = localStorage.getItem('investAmount');
    return saved || '';
  });
  const [boughtTickers, setBoughtTickers] = useState<Set<string>>(() => {
    const saved = localStorage.getItem('boughtTickers');
    return saved ? new Set(JSON.parse(saved)) : new Set();
  });
  const [suggestion, setSuggestion] = useState<{
    current: { holdings: any[]; value: number; new_investment: number; total: number };
    sells: { ticker: string; name: string; shares: number; value: number; reason: string }[];
    buys: { ticker: string; name: string; amount: number; strategies: string[]; current_value: number; target_value: number; price?: number; shares?: number; avanza_id?: string }[];
    target_portfolio: { ticker: string; name: string; value: number; weight: number; strategies: string[] }[];
    costs: { courtage: number; spread: number; total: number };
    summary: { sell_count: number; buy_count: number; sell_value: number; buy_value: number };
  } | null>(null);
  const [loadingSuggestion, setLoadingSuggestion] = useState(false);
  const [executedTrades, setExecutedTrades] = useState<{ sells: string[]; buys: string[] }>(() => {
    const saved = localStorage.getItem('executedTrades');
    return saved ? JSON.parse(saved) : { sells: [], buys: [] };
  });

  // Momentum banding state
  const [momentumHoldings, setMomentumHoldings] = useState<string[]>(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.momentumHoldings);
    return saved ? JSON.parse(saved) : [];
  });
  const [bandingResult, setBandingResult] = useState<BandingResult | null>(null);
  const [loadingBanding, setLoadingBanding] = useState(false);

  // TanStack Query for rebalance dates
  const { data: rebalanceDatesData = [] } = useRebalanceDates();
  const rebalanceDates = useMemo(() => {
    const map: Record<string, string> = {};
    rebalanceDatesData.forEach(d => { map[d.strategy_name] = d.next_date; });
    return map;
  }, [rebalanceDatesData]);

  // TanStack Query for strategy rankings
  const allStrategiesToFetch = useMemo(() => {
    const strategies = [...selected];
    if (settings.bandingMode && !strategies.includes('sammansatt_momentum')) {
      strategies.push('sammansatt_momentum');
    }
    return strategies;
  }, [selected, settings.bandingMode]);

  const strategyQueries = useQueries({
    queries: allStrategiesToFetch.map(key => ({
      queryKey: queryKeys.strategies.rankings(key),
      queryFn: () => api.getStrategyRankings(key),
    })),
  });

  const strategyData = useMemo(() => {
    const data: Record<string, any[]> = {};
    allStrategiesToFetch.forEach((key, i) => {
      if (strategyQueries[i]?.data) {
        data[key] = strategyQueries[i].data;
      }
    });
    return data;
  }, [allStrategiesToFetch, strategyQueries]);

  // TanStack Query for stock prices
  const priceQueries = useQueries({
    queries: holdings.map(h => ({
      queryKey: queryKeys.stocks.prices(h.ticker, 1),
      queryFn: () => api.getStockPrices(h.ticker, 1),
      enabled: !!h.ticker,
    })),
  });

  const prices = useMemo(() => {
    const priceMap: Record<string, number> = {};
    holdings.forEach((h, i) => {
      const data = priceQueries[i]?.data;
      if (data?.prices?.[0]) {
        priceMap[h.ticker] = data.prices[0].close;
      }
    });
    return priceMap;
  }, [holdings, priceQueries]);

  // Load holdings from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEYS.holdings);
    if (saved) setHoldings(JSON.parse(saved));
  }, []);

  // Persist selections to localStorage
  useEffect(() => { localStorage.setItem(STORAGE_KEYS.strategies, JSON.stringify(selected)); }, [selected]);
  useEffect(() => { localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(settings)); }, [settings]);
  useEffect(() => { localStorage.setItem(STORAGE_KEYS.momentumHoldings, JSON.stringify(momentumHoldings)); }, [momentumHoldings]);
  useEffect(() => { if (investAmount) localStorage.setItem('investAmount', investAmount); }, [investAmount]);
  useEffect(() => { localStorage.setItem('boughtTickers', JSON.stringify([...boughtTickers])); }, [boughtTickers]);

  // Check momentum banding
  const checkMomentumBanding = async (holdingsToCheck?: string[]) => {
    const tickers = holdingsToCheck || momentumHoldings;
    if (tickers.length === 0) return;
    setLoadingBanding(true);
    try {
      const res = await fetch('/v1/strategies/sammansatt_momentum/banding-check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(tickers)
      });
      if (res.ok) setBandingResult(await res.json());
    } catch { setBandingResult(null); }
    setLoadingBanding(false);
  };

  // Initialize momentum portfolio with top 10
  const initMomentumPortfolio = async () => {
    const top10 = (strategyData['sammansatt_momentum'] || []).slice(0, 10).map(s => s.ticker);
    if (top10.length > 0) {
      setMomentumHoldings(top10);
      await checkMomentumBanding(top10);
    }
  };

  // Apply banding trades
  const applyBandingTrades = () => {
    if (!bandingResult) return;
    const newHoldings = [
      ...bandingResult.keeps.map(k => k.ticker),
      ...bandingResult.suggested_buys.map(b => b.ticker)
    ];
    setMomentumHoldings(newHoldings);
    setBandingResult(null);
  };

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

  // TanStack Query for pick prices (for share calculation)
  const pickPriceQueries = useQueries({
    queries: picks.map(p => ({
      queryKey: queryKeys.stocks.prices(p.ticker, 1),
      queryFn: () => api.getStockPrices(p.ticker, 1),
      enabled: !!p.ticker,
    })),
  });

  const pickPrices = useMemo(() => {
    const priceMap: Record<string, number> = {};
    picks.forEach((p, i) => {
      const data = pickPriceQueries[i]?.data;
      if (data?.prices?.[0]) {
        priceMap[p.ticker] = data.prices[0].close;
      }
    });
    return priceMap;
  }, [picks, pickPriceQueries]);

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
    // Merge with existing holdings - CSV shares replace, but keep avgPrice from existing or use current price
    const existingMap = new Map(holdings.map(h => [h.ticker, h]));
    const newHoldings = importResult.holdings.map(h => {
      const existing = existingMap.get(h.ticker);
      const currentPrice = prices[h.ticker] || pickPrices[h.ticker] || 0;
      return {
        ticker: h.ticker,
        shares: h.shares,
        avgPrice: existing?.avgPrice || currentPrice // Keep existing avgPrice or use current price
      };
    });
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(newHoldings));
    // Clear any pending suggestions/trades when importing
    setSuggestion(null);
    setExecutedTrades({ sells: [], buys: [] });
    localStorage.removeItem('executedTrades');
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

  // Add bought stocks to holdings
  const addBoughtToHoldings = () => {
    const boughtPicks = picks.filter(p => boughtTickers.has(p.ticker));
    if (boughtPicks.length === 0) return;
    
    const perStock = parseFloat(investAmount) / selected.length / 10;
    const newHoldings = [...holdings];
    let addedCount = 0;
    
    for (const p of boughtPicks) {
      const allocation = perStock * p.strategies.length;
      const price = pickPrices[p.ticker] || 0;
      const shares = price > 0 ? Math.floor(allocation / price) : 0;
      if (shares === 0) continue;
      
      const existing = newHoldings.find(h => h.ticker === p.ticker);
      if (existing) {
        const totalShares = existing.shares + shares;
        const totalCost = existing.shares * existing.avgPrice + shares * price;
        existing.shares = totalShares;
        existing.avgPrice = totalCost / totalShares;
      } else {
        newHoldings.push({ ticker: p.ticker, shares, avgPrice: price });
      }
      addedCount++;
    }
    
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(newHoldings));
    setBoughtTickers(new Set());
    
    toaster.create({
      title: `${addedCount} aktier tillagda`,
      description: 'Gå till Portfölj-fliken för att se dina innehav',
      type: 'success',
    });
  };

  // Get investment suggestion
  const getInvestmentSuggestion = async () => {
    const amount = parseFloat(investAmount) || 0;
    if (amount <= 0 && holdings.length === 0) return;
    setLoadingSuggestion(true);
    try {
      const holdingsWithValues = holdings.map(h => ({
        ticker: h.ticker,
        shares: h.shares,
        value: h.shares * (prices[h.ticker] || h.avgPrice || 0)
      }));
      const res = await fetch('/v1/portfolio/investment-suggestion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          amount,
          strategies: selected,
          holdings: holdingsWithValues,
          mode: settings.bandingMode ? 'banding' : 'classic'
        })
      });
      if (res.ok) {
        setSuggestion(await res.json());
        setExecutedTrades({ sells: [], buys: [] });
      }
    } catch { setSuggestion(null); }
    setLoadingSuggestion(false);
  };

  // Mark trade as executed
  const toggleTradeExecuted = (type: 'sells' | 'buys', ticker: string) => {
    setExecutedTrades(prev => {
      const updated = {
        ...prev,
        [type]: prev[type].includes(ticker) 
          ? prev[type].filter(t => t !== ticker)
          : [...prev[type], ticker]
      };
      localStorage.setItem('executedTrades', JSON.stringify(updated));
      return updated;
    });
  };

  // Apply executed trades to holdings
  const applyExecutedTrades = () => {
    if (!suggestion) return;
    let updated = holdings.filter(h => !executedTrades.sells.includes(h.ticker));
    for (const buy of suggestion.buys) {
      if (executedTrades.buys.includes(buy.ticker)) {
        const existing = updated.find(h => h.ticker === buy.ticker);
        if (existing) {
          existing.shares += Math.round(buy.amount / (prices[buy.ticker] || 100));
        } else {
          updated.push({ ticker: buy.ticker, shares: Math.round(buy.amount / (prices[buy.ticker] || 100)), avgPrice: prices[buy.ticker] || 0 });
        }
      }
    }
    setHoldings(updated);
    localStorage.setItem(STORAGE_KEYS.holdings, JSON.stringify(updated));
    setSuggestion(null);
    setExecutedTrades({ sells: [], buys: [] });
    localStorage.removeItem('executedTrades');
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

  // Generate ICS file for rebalance reminders
  const generateICS = () => {
    const events: string[] = [];
    const now = new Date();
    const stamp = now.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    
    for (const strat of STRATEGIES.filter(s => selected.includes(s.key))) {
      const nextDate = rebalanceDates[strat.key];
      if (!nextDate) continue;
      
      const [year, month, day] = nextDate.split('-').map(Number);
      const eventDate = `${year}${String(month).padStart(2, '0')}${String(day).padStart(2, '0')}`;
      const uid = `${strat.key}-${eventDate}@borslabbet`;
      const rrule = strat.rebalance === 'quarterly' ? 'RRULE:FREQ=MONTHLY;INTERVAL=3' : 'RRULE:FREQ=YEARLY';
      
      let event = `BEGIN:VEVENT
UID:${uid}
DTSTAMP:${stamp}
DTSTART;VALUE=DATE:${eventDate}
SUMMARY:Rebalansera ${strat.label}
DESCRIPTION:Dags att rebalansera din ${strat.label}-portfölj på Börslabbet.
${rrule}`;
      
      if (settings.reminders.weekBefore) {
        event += `
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Rebalansering om 1 vecka
TRIGGER:-P1W
END:VALARM`;
      }
      if (settings.reminders.dayBefore) {
        event += `
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Rebalansering imorgon
TRIGGER:-P1D
END:VALARM`;
      }
      
      event += `
END:VEVENT`;
      events.push(event);
    }
    
    const ics = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Borslabbet//Rebalansering//SV
CALSCALE:GREGORIAN
METHOD:PUBLISH
${events.join('\n')}
END:VCALENDAR`;
    
    const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'borslabbet-rebalansering.ics';
    a.click();
    URL.revokeObjectURL(url);
  };

  // Copy buy list to clipboard
  const copyBuyListToClipboard = () => {
    const perStock = parseFloat(investAmount) / selected.length / 10;
    const lines = [...picks]
      .sort((a, b) => b.strategies.length - a.strategies.length)
      .map(p => {
        const allocation = perStock * p.strategies.length;
        const price = pickPrices[p.ticker] || 0;
        const shares = price > 0 ? Math.floor(allocation / price) : 0;
        return `${p.ticker}\t${shares} st\t${Math.round(shares * price)} kr`;
      });
    const text = `Köplista - ${formatSEK(parseFloat(investAmount))}\n${'─'.repeat(30)}\n${lines.join('\n')}`;
    navigator.clipboard.writeText(text);
    toaster.create({ title: 'Kopierat till urklipp', type: 'success' });
  };

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
          { key: 'strategier', label: 'Strategier' },
          { key: 'portfolj', label: 'Portfölj' },
          { key: 'rebalansering', label: 'Rebalansering' },
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
            {t.label}
          </Box>
        ))}
      </HStack>

      {/* Tab Content */}
      {tab === 'strategier' && (
        <VStack gap="20px" align="stretch">
          {/* Step Indicator */}
          <Flex gap="8px" align="center" fontSize="sm">
            <Flex align="center" gap="6px" color={selected.length > 0 ? 'success' : 'brand.solid'}>
              <Box w="20px" h="20px" borderRadius="full" bg={selected.length > 0 ? 'success' : 'brand.solid'} color="white" display="flex" alignItems="center" justifyContent="center" fontSize="xs" fontWeight="bold">
                {selected.length > 0 ? '✓' : '1'}
              </Box>
              <Text fontWeight={selected.length === 0 ? 'semibold' : 'normal'}>Välj strategi</Text>
            </Flex>
            <Box w="24px" h="2px" bg={selected.length > 0 ? 'success' : 'border'} />
            <Flex align="center" gap="6px" color={parseFloat(investAmount) > 0 ? 'success' : selected.length > 0 ? 'brand.solid' : 'fg.muted'}>
              <Box w="20px" h="20px" borderRadius="full" bg={parseFloat(investAmount) > 0 ? 'success' : selected.length > 0 ? 'brand.solid' : 'bg.muted'} color={selected.length > 0 ? 'white' : 'fg.muted'} display="flex" alignItems="center" justifyContent="center" fontSize="xs" fontWeight="bold" border={selected.length === 0 ? '2px solid' : 'none'} borderColor="border">
                {parseFloat(investAmount) > 0 ? '✓' : '2'}
              </Box>
              <Text fontWeight={selected.length > 0 && !parseFloat(investAmount) ? 'semibold' : 'normal'}>Ange belopp</Text>
            </Flex>
            <Box w="24px" h="2px" bg={parseFloat(investAmount) > 0 ? 'success' : 'border'} />
            <Flex align="center" gap="6px" color={boughtTickers.size > 0 ? 'success' : parseFloat(investAmount) > 0 ? 'brand.solid' : 'fg.muted'}>
              <Box w="20px" h="20px" borderRadius="full" bg={boughtTickers.size > 0 ? 'success' : parseFloat(investAmount) > 0 ? 'brand.solid' : 'bg.muted'} color={parseFloat(investAmount) > 0 ? 'white' : 'fg.muted'} display="flex" alignItems="center" justifyContent="center" fontSize="xs" fontWeight="bold" border={parseFloat(investAmount) <= 0 ? '2px solid' : 'none'} borderColor="border">
                {boughtTickers.size > 0 ? '✓' : '3'}
              </Box>
              <Text fontWeight={parseFloat(investAmount) > 0 ? 'semibold' : 'normal'}>Köp aktier</Text>
            </Flex>
          </Flex>

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

          {/* Investment Calculator - Progressive disclosure: only show when strategies selected */}
          {selected.length > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Text fontWeight="semibold" color="fg" mb="12px">Investeringsbelopp</Text>
              <HStack gap="12px" mb="12px">
                <Input
                  type="number"
                  placeholder="Belopp (SEK)"
                  value={investAmount}
                  onChange={e => setInvestAmount(e.target.value)}
                  bg="bg.muted"
                  borderColor="border"
                  w="150px"
                  size="sm"
                />
                <Text fontSize="sm" color="fg.muted">
                  {investAmount && parseFloat(investAmount) > 0 ? (
                    <>
                      {formatSEK(parseFloat(investAmount) / selected.length)} per strategi → {formatSEK(parseFloat(investAmount) / selected.length / 10)} per aktie
                    </>
                  ) : 'Ange belopp för att beräkna'}
                </Text>
              </HStack>
            </Box>
          )}

          {/* Rebalance Dates & Reminders */}
          {selected.length > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Flex justify="space-between" align="center" mb="12px">
                <Text fontWeight="semibold" color="fg">Nästa rebalansering</Text>
                <Button size="xs" colorPalette="blue" onClick={generateICS} disabled={selected.length === 0}>
                  Exportera kalender
                </Button>
              </Flex>
              <VStack gap="8px" align="stretch" mb="12px">
                {STRATEGIES.filter(s => selected.includes(s.key)).map(s => {
                  const nextDate = rebalanceDates[s.key];
                  const daysUntil = nextDate ? Math.ceil((new Date(nextDate).getTime() - Date.now()) / (1000 * 60 * 60 * 24)) : null;
                  return (
                    <Flex key={s.key} p="10px" bg="bg.muted" borderRadius="6px" justify="space-between" align="center">
                      <HStack gap="8px">
                        <Box w="8px" h="8px" borderRadius="full" bg={s.color} />
                        <Text fontSize="sm" fontWeight="medium" color="fg">{s.label}</Text>
                      </HStack>
                      <HStack gap="8px">
                        {nextDate && (
                          <>
                            <Text fontSize="sm" color="fg.muted">{new Date(nextDate).toLocaleDateString('sv-SE')}</Text>
                            <Text fontSize="xs" px="6px" py="2px" borderRadius="4px" bg={daysUntil && daysUntil <= 7 ? 'warning/20' : 'bg.subtle'} color={daysUntil && daysUntil <= 7 ? 'warning' : 'fg.muted'}>
                              {daysUntil} dagar
                            </Text>
                          </>
                        )}
                      </HStack>
                    </Flex>
                  );
                })}
              </VStack>
              <Flex gap="16px" pt="8px" borderTop="1px solid" borderColor="border">
                <HStack gap="6px">
                  <Box
                    as="button"
                    w="18px"
                    h="18px"
                    borderRadius="4px"
                    border="2px solid"
                    borderColor={settings.reminders.weekBefore ? 'brand.solid' : 'border'}
                    bg={settings.reminders.weekBefore ? 'brand.solid' : 'transparent'}
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    onClick={() => setSettings(s => ({ ...s, reminders: { ...s.reminders, weekBefore: !s.reminders.weekBefore } }))}
                  >
                    {settings.reminders.weekBefore && <Text color="white" fontSize="xs">✓</Text>}
                  </Box>
                  <Text fontSize="sm" color="fg.muted">1 vecka innan</Text>
                </HStack>
                <HStack gap="6px">
                  <Box
                    as="button"
                    w="18px"
                    h="18px"
                    borderRadius="4px"
                    border="2px solid"
                    borderColor={settings.reminders.dayBefore ? 'brand.solid' : 'border'}
                    bg={settings.reminders.dayBefore ? 'brand.solid' : 'transparent'}
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    onClick={() => setSettings(s => ({ ...s, reminders: { ...s.reminders, dayBefore: !s.reminders.dayBefore } }))}
                  >
                    {settings.reminders.dayBefore && <Text color="white" fontSize="xs">✓</Text>}
                  </Box>
                  <Text fontSize="sm" color="fg.muted">1 dag innan</Text>
                </HStack>
              </Flex>
            </Box>
          )}

          {/* Buy List */}
          {selected.length > 0 && parseFloat(investAmount) > 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="16px" borderColor="border" borderWidth="1px">
              <Flex justify="space-between" align="center" mb="12px">
                <HStack gap="8px">
                  <Text fontWeight="semibold" color="fg">Köplista</Text>
                  <Text fontSize="sm" color="fg.muted">
                    {boughtTickers.size}/{picks.length} köpta
                  </Text>
                </HStack>
                <HStack gap="8px">
                  <Button size="xs" variant="ghost" onClick={copyBuyListToClipboard} title="Kopiera till urklipp">
                    Kopiera
                  </Button>
                  {boughtTickers.size > 0 && boughtTickers.size < picks.length && (
                    <Button size="xs" variant="ghost" onClick={() => setBoughtTickers(new Set(picks.map(p => p.ticker)))}>
                      Markera alla
                    </Button>
                  )}
                  {boughtTickers.size > 0 && (
                    <Button size="xs" variant="ghost" onClick={() => setBoughtTickers(new Set())}>
                      Rensa
                    </Button>
                  )}
                </HStack>
              </Flex>
              
              {/* Progress bar */}
              <Box bg="bg.muted" borderRadius="4px" h="4px" mb="12px" overflow="hidden">
                <Box bg="success" h="100%" w={`${(boughtTickers.size / picks.length) * 100}%`} transition="width 200ms" />
              </Box>

              <VStack gap="8px" align="stretch" maxH="400px" overflowY="auto">
                {[...picks]
                  .sort((a, b) => (b.strategies.length - a.strategies.length)) // Overlaps first
                  .map(p => {
                  const perStock = parseFloat(investAmount) / selected.length / 10;
                  const allocation = perStock * p.strategies.length;
                  const price = pickPrices[p.ticker];
                  const shares = price && allocation > 0 ? Math.floor(allocation / price) : 0;
                  const actualCost = shares * (price || 0);
                  const isBought = boughtTickers.has(p.ticker);
                  const isLoading = !price && pickPriceQueries.some(q => q.isLoading);
                  return (
                    <Flex
                      key={p.ticker}
                      p="12px"
                      bg={isBought ? 'success/10' : 'bg.muted'}
                      borderRadius="6px"
                      justify="space-between"
                      align="center"
                      opacity={isBought ? 0.7 : 1}
                      transition="all 150ms"
                    >
                      <HStack gap="12px">
                        <Box
                          as="button"
                          w="20px"
                          h="20px"
                          borderRadius="4px"
                          border="2px solid"
                          borderColor={isBought ? 'success' : 'border'}
                          bg={isBought ? 'success' : 'transparent'}
                          display="flex"
                          alignItems="center"
                          justifyContent="center"
                          onClick={() => setBoughtTickers(prev => {
                            const next = new Set(prev);
                            isBought ? next.delete(p.ticker) : next.add(p.ticker);
                            return next;
                          })}
                          aria-label={`Markera ${p.ticker} som köpt`}
                          flexShrink={0}
                        >
                          {isBought && <Text color="white" fontSize="xs">✓</Text>}
                        </Box>
                        <Link to={`/stock/${p.ticker}`}>
                          <HStack gap="8px" _hover={{ textDecoration: 'underline' }}>
                            <Text fontWeight="semibold" color="fg" fontFamily="mono" textDecoration={isBought ? 'line-through' : 'none'}>{p.ticker}</Text>
                            <Text fontSize="sm" color="fg.muted" maxW="100px" truncate>{p.name}</Text>
                          </HStack>
                        </Link>
                        <a
                          href={`https://www.avanza.se/aktier/om-aktien.html?query=${encodeURIComponent(p.ticker)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          title="Öppna i Avanza"
                          onClick={e => e.stopPropagation()}
                        >
                          <Text fontSize="xs" color="fg.muted" _hover={{ color: 'brand.solid' }}>↗</Text>
                        </a>
                      </HStack>
                      <HStack gap="8px">
                        {isLoading ? (
                          <Text fontSize="xs" color="fg.muted">...</Text>
                        ) : (
                          <>
                            {shares > 0 && <Text fontSize="sm" fontWeight="semibold" color="fg">{shares} st</Text>}
                            <Text fontSize="sm" fontWeight="semibold" color={p.strategies.length > 1 ? 'success' : 'fg'}>
                              {formatSEK(actualCost || allocation)}
                            </Text>
                          </>
                        )}
                        {p.strategies.map(s => (
                          <Box key={s.key} bg={`${s.color}40`} px="6px" py="2px" borderRadius="4px" title={s.label}>
                            <Text fontSize="xs" color="fg" fontWeight="medium">{s.label.slice(0, 3)}</Text>
                          </Box>
                        ))}
                      </HStack>
                    </Flex>
                  );
                })}
              </VStack>

              {/* Summary and Add to Holdings */}
              <Flex justify="space-between" align="center" mt="12px" pt="12px" borderTop="1px solid" borderColor="border">
                <VStack align="start" gap="2px">
                  <Text fontSize="sm" color="fg.muted">
                    Totalt: {formatSEK(parseFloat(investAmount))}
                  </Text>
                  <Text fontSize="sm" color="success" fontWeight="semibold">
                    Köpt: {formatSEK(picks.filter(p => boughtTickers.has(p.ticker)).reduce((sum, p) => {
                      const perStock = parseFloat(investAmount) / selected.length / 10;
                      return sum + perStock * p.strategies.length;
                    }, 0))}
                  </Text>
                </VStack>
                {boughtTickers.size > 0 && (
                  <Button
                    colorPalette="blue"
                    size="sm"
                    onClick={addBoughtToHoldings}
                  >
                    Lägg till i portfölj ({boughtTickers.size})
                  </Button>
                )}
              </Flex>
            </Box>
          )}

          {/* Picks Summary (when no amount entered) */}
          {selected.length > 0 && !parseFloat(investAmount) && (
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
                        <Text fontSize="sm" color="fg.muted" maxW="120px" truncate>{p.name}</Text>
                      </HStack>
                      <HStack gap="4px">
                        {p.strategies.map(s => (
                          <Box key={s.key} bg={`${s.color}40`} px="6px" py="2px" borderRadius="4px" title={s.label}>
                            <Text fontSize="xs" color="fg" fontWeight="medium">{s.label.slice(0, 3)}</Text>
                          </Box>
                        ))}
                      </HStack>
                    </Flex>
                  </Link>
                ))}
              </VStack>
              <Text fontSize="xs" color="fg.muted" mt="12px">
                Ange ett belopp ovan för att se köplista med antal aktier.
              </Text>
            </Box>
          )}

          {selected.length === 0 && (
            <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center">
              <Text color="fg.muted">Välj minst en strategi ovan för att komma igång</Text>
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
            <Text fontWeight="semibold" color="fg" mb="8px">Importera från Avanza</Text>
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
              <Text color="fg.muted">Importera eller lägg till innehav ovan</Text>
            </Box>
          )}
        </VStack>
      )}

      {tab === 'rebalansering' && (
        <VStack gap="20px" align="stretch">
          {/* Mode Toggle */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
            <Text fontWeight="semibold" color="fg" mb="12px">Rebalanseringsmetod</Text>
            <HStack gap="12px">
              <Box
                as="button"
                flex="1"
                p="12px"
                borderRadius="6px"
                bg={!settings.bandingMode ? 'brand.subtle' : 'bg.muted'}
                border="2px solid"
                borderColor={!settings.bandingMode ? 'brand.solid' : 'border'}
                onClick={() => setSettings(s => ({ ...s, bandingMode: false }))}
                textAlign="left"
              >
                <Text fontWeight="semibold" color="fg" fontSize="sm">Klassisk</Text>
                <Text fontSize="xs" color="fg.muted">Kvartalsvis, byt till exakt topp 10</Text>
              </Box>
              <Box
                as="button"
                flex="1"
                p="12px"
                borderRadius="6px"
                bg={settings.bandingMode ? 'brand.subtle' : 'bg.muted'}
                border="2px solid"
                borderColor={settings.bandingMode ? 'brand.solid' : 'border'}
                onClick={() => setSettings(s => ({ ...s, bandingMode: true }))}
                textAlign="left"
                title="Banding minskar omsättningen genom att behålla aktier som fortfarande är inom topp 20%, istället för att sälja så fort de faller ur topp 10. Detta sparar courtage och minskar skatteeffekter."
              >
                <HStack gap="4px" mb="2px">
                  <Text fontWeight="semibold" color="fg" fontSize="sm">Banding (Momentum)</Text>
                  <Text fontSize="xs" color="fg.muted" cursor="help" title="Banding minskar omsättningen genom att behålla aktier som fortfarande är inom topp 20%, istället för att sälja så fort de faller ur topp 10.">ⓘ</Text>
                </HStack>
                <Text fontSize="xs" color="fg.muted">Månadsvis, sälj endast under topp 20%</Text>
              </Box>
            </HStack>
          </Box>

          {/* Investment Suggestion */}
          <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
            <Text fontWeight="semibold" color="fg" mb="12px">Investeringsförslag</Text>
            <HStack gap="12px" mb="16px" flexWrap="wrap">
              <Box flex="1" minW="150px">
                <Text fontSize="xs" color="fg.muted" mb="4px">Belopp att investera</Text>
                <Input
                  type="number"
                  placeholder="100000"
                  value={investAmount}
                  onChange={e => setInvestAmount(e.target.value)}
                  bg="bg.muted"
                  borderColor="border"
                  size="sm"
                />
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted" mb="4px">&nbsp;</Text>
                <Button
                  size="sm"
                  colorPalette="blue"
                  onClick={getInvestmentSuggestion}
                  loading={loadingSuggestion}
                  disabled={selected.length === 0}
                >
                  Beräkna
                </Button>
              </Box>
            </HStack>

            {suggestion && (
              <VStack gap="16px" align="stretch">
                {/* Three Column View */}
                <SimpleGrid columns={{ base: 1, md: 3 }} gap="12px">
                  {/* TODAY - Current Holdings */}
                  <Box bg="bg.muted" borderRadius="6px" p="12px">
                    <Text fontSize="sm" fontWeight="semibold" color="fg" mb="8px">IDAG</Text>
                    <VStack gap="4px" align="stretch" mb="8px">
                      {suggestion.current.holdings.length > 0 ? (
                        suggestion.current.holdings.map(h => (
                          <Flex key={h.ticker} justify="space-between" fontSize="xs">
                            <Text color="fg" fontFamily="mono">{h.ticker}</Text>
                            <Text color="fg.muted">{formatSEK(h.value)}</Text>
                          </Flex>
                        ))
                      ) : (
                        <Text fontSize="xs" color="fg.muted">Inga innehav</Text>
                      )}
                    </VStack>
                    <Box borderTop="1px solid" borderColor="border" pt="8px">
                      <Flex justify="space-between" fontSize="xs">
                        <Text color="fg.muted">Nuvarande</Text>
                        <Text color="fg">{formatSEK(suggestion.current.value)}</Text>
                      </Flex>
                      <Flex justify="space-between" fontSize="xs">
                        <Text color="fg.muted">+ Nytt</Text>
                        <Text color="success.fg">+{formatSEK(suggestion.current.new_investment)}</Text>
                      </Flex>
                      <Flex justify="space-between" fontSize="sm" fontWeight="semibold" mt="4px">
                        <Text color="fg">Totalt</Text>
                        <Text color="fg">{formatSEK(suggestion.current.total)}</Text>
                      </Flex>
                    </Box>
                  </Box>

                  {/* REBALANCE - Actions */}
                  <Box bg="bg.muted" borderRadius="6px" p="12px">
                    <Text fontSize="sm" fontWeight="semibold" color="fg" mb="8px">ÅTGÄRDER</Text>
                    {suggestion.sells.length > 0 && (
                      <Box mb="8px">
                        <Text fontSize="xs" color="error.fg" fontWeight="semibold" mb="4px">SÄLJ</Text>
                        <VStack gap="2px" align="stretch">
                          {suggestion.sells.map(s => (
                            <Flex
                              key={s.ticker}
                              justify="space-between"
                              fontSize="xs"
                              p="4px"
                              borderRadius="4px"
                              bg={executedTrades.sells.includes(s.ticker) ? 'success.subtle' : 'error.subtle'}
                              cursor="pointer"
                              onClick={() => toggleTradeExecuted('sells', s.ticker)}
                            >
                              <HStack gap="4px">
                                <Text color={executedTrades.sells.includes(s.ticker) ? 'success.fg' : 'error.fg'}>
                                  {executedTrades.sells.includes(s.ticker) ? '✓' : '•'}
                                </Text>
                                <Text color="fg" fontFamily="mono">{s.ticker}</Text>
                              </HStack>
                              <Text color="fg.muted">-{formatSEK(s.value)}</Text>
                            </Flex>
                          ))}
                        </VStack>
                      </Box>
                    )}
                    {suggestion.buys.length > 0 && (
                      <Box>
                        <Text fontSize="xs" color="success.fg" fontWeight="semibold" mb="4px">KÖP</Text>
                        <VStack gap="2px" align="stretch">
                          {suggestion.buys.map(b => (
                            <Flex
                              key={b.ticker}
                              direction="column"
                              fontSize="xs"
                              p="4px"
                              borderRadius="4px"
                              bg={executedTrades.buys.includes(b.ticker) ? 'success.subtle' : 'brand.subtle'}
                              cursor="pointer"
                              onClick={() => toggleTradeExecuted('buys', b.ticker)}
                            >
                              <Flex justify="space-between">
                                <HStack gap="4px">
                                  <Text color={executedTrades.buys.includes(b.ticker) ? 'success.fg' : 'brand.fg'}>
                                    {executedTrades.buys.includes(b.ticker) ? '✓' : '+'}
                                  </Text>
                                  {b.strategies.length > 1 && <Text color="warning.fg">★</Text>}
                                  {b.avanza_id ? (
                                    <a href={`https://www.avanza.se/aktier/om-aktien.html/${b.avanza_id}`} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                                      <Text color="brand.fg" fontFamily="mono" textDecoration="underline">{b.ticker}</Text>
                                    </a>
                                  ) : (
                                    <Text color="fg" fontFamily="mono">{b.ticker}</Text>
                                  )}
                                </HStack>
                                <Text color="fg.muted">+{formatSEK(b.amount)}</Text>
                              </Flex>
                              {b.price && b.shares && (
                                <Text color="fg.muted" fontSize="10px" ml="24px">~{b.shares} st à {Math.round(b.price)} SEK</Text>
                              )}
                            </Flex>
                          ))}
                        </VStack>
                      </Box>
                    )}
                    {suggestion.sells.length === 0 && suggestion.buys.length === 0 && (
                      <Text fontSize="xs" color="fg.muted">Inga åtgärder behövs</Text>
                    )}
                    <Text fontSize="xs" color="fg.muted" mt="8px">Klicka för att markera som genomförd</Text>
                  </Box>

                  {/* AFTER - Target Portfolio */}
                  <Box bg="bg.muted" borderRadius="6px" p="12px">
                    <Text fontSize="sm" fontWeight="semibold" color="fg" mb="8px">EFTER</Text>
                    <VStack gap="4px" align="stretch" mb="8px">
                      {suggestion.target_portfolio.map(t => (
                        <Flex key={t.ticker} justify="space-between" fontSize="xs">
                          <HStack gap="4px">
                            {t.strategies.length > 1 && <Text color="warning.fg">★</Text>}
                            <Text color="fg" fontFamily="mono">{t.ticker}</Text>
                            <Text color="fg.muted">({t.weight}%)</Text>
                          </HStack>
                          <Text color="fg.muted">{formatSEK(t.value)}</Text>
                        </Flex>
                      ))}
                    </VStack>
                    <Box borderTop="1px solid" borderColor="border" pt="8px">
                      <Flex justify="space-between" fontSize="sm" fontWeight="semibold">
                        <Text color="fg">{suggestion.target_portfolio.length} aktier</Text>
                        <Text color="fg">{formatSEK(suggestion.current.total)}</Text>
                      </Flex>
                    </Box>
                  </Box>
                </SimpleGrid>

                {/* Cost and Apply */}
                <Flex justify="space-between" align="center" p="12px" bg="bg.muted" borderRadius="6px">
                  <Text fontSize="xs" color="fg.muted">
                    Kostnad: {formatSEK(suggestion.costs.total)} (courtage {formatSEK(suggestion.costs.courtage)} + spread {formatSEK(suggestion.costs.spread)})
                  </Text>
                  {(executedTrades.sells.length > 0 || executedTrades.buys.length > 0) && (
                    <Button size="sm" colorPalette="green" onClick={applyExecutedTrades}>
                      Spara {executedTrades.sells.length + executedTrades.buys.length} genomförda
                    </Button>
                  )}
                </Flex>
              </VStack>
            )}

            {!suggestion && selected.length > 0 && (
              <Text fontSize="sm" color="fg.muted">
                Ange belopp och klicka Beräkna för att se förslag. Dina valda strategier: {selected.map(s => STRATEGIES.find(st => st.key === s)?.label).join(', ')}
              </Text>
            )}
            {selected.length === 0 && (
              <Text fontSize="sm" color="fg.muted">Välj strategier i första fliken först</Text>
            )}
          </Box>

          {/* Banding Mode UI */}
          {settings.bandingMode && (
            <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
              <Flex justify="space-between" align="center" mb="16px">
                <Box>
                  <Text fontWeight="semibold" color="fg">Momentumportföljen</Text>
                  <Text fontSize="xs" color="fg.muted">Köp topp 10%, sälj under topp 20%, kontrollera månadsvis</Text>
                </Box>
                {momentumHoldings.length === 0 ? (
                  <Button size="sm" colorPalette="blue" onClick={initMomentumPortfolio} disabled={!strategyData['sammansatt_momentum']}>
                    Starta med topp 10
                  </Button>
                ) : (
                  <Button size="sm" colorPalette="blue" onClick={() => checkMomentumBanding()} loading={loadingBanding}>
                    Kontrollera
                  </Button>
                )}
              </Flex>

              {momentumHoldings.length === 0 ? (
                <Box p="24px" bg="bg.muted" borderRadius="6px" textAlign="center">
                  <Text color="fg.muted" fontSize="sm">Klicka "Starta med topp 10" för att initiera momentumportföljen</Text>
                </Box>
              ) : bandingResult ? (
                <VStack gap="12px" align="stretch">
                  {/* Summary */}
                  <SimpleGrid columns={4} gap="8px">
                    <Box p="8px" bg="bg.muted" borderRadius="4px" textAlign="center">
                      <Text fontSize="lg" fontWeight="bold" color="fg">{bandingResult.summary.to_keep}</Text>
                      <Text fontSize="xs" color="fg.muted">Behåll</Text>
                    </Box>
                    <Box p="8px" bg="warning.subtle" borderRadius="4px" textAlign="center">
                      <Text fontSize="lg" fontWeight="bold" color="warning.fg">{bandingResult.summary.in_danger_zone}</Text>
                      <Text fontSize="xs" color="fg.muted">Bevaka</Text>
                    </Box>
                    <Box p="8px" bg="error.subtle" borderRadius="4px" textAlign="center">
                      <Text fontSize="lg" fontWeight="bold" color="error.fg">{bandingResult.summary.to_sell}</Text>
                      <Text fontSize="xs" color="fg.muted">Sälj</Text>
                    </Box>
                    <Box p="8px" bg="success.subtle" borderRadius="4px" textAlign="center">
                      <Text fontSize="lg" fontWeight="bold" color="success.fg">{bandingResult.suggested_buys.length}</Text>
                      <Text fontSize="xs" color="fg.muted">Köp</Text>
                    </Box>
                  </SimpleGrid>

                  {/* Thresholds info */}
                  <Text fontSize="xs" color="fg.muted" textAlign="center">
                    Universum: {bandingResult.thresholds.universe_size} aktier • Köp: topp {bandingResult.thresholds.buy_rank} • Sälj: under topp {bandingResult.thresholds.sell_rank}
                  </Text>

                  {/* Holdings list */}
                  <VStack gap="4px" align="stretch">
                    {bandingResult.keeps.map(k => (
                      <Flex key={k.ticker} p="8px" bg={k.rank <= bandingResult.thresholds.buy_rank ? 'success.subtle' : 'warning.subtle'} borderRadius="4px" justify="space-between">
                        <HStack gap="8px">
                          <Text fontSize="sm" color={k.rank <= bandingResult.thresholds.buy_rank ? 'success.fg' : 'warning.fg'}>
                            {k.rank <= bandingResult.thresholds.buy_rank ? '✓' : '!'}
                          </Text>
                          <Text fontSize="sm" color="fg" fontFamily="mono">{k.ticker}</Text>
                          <Text fontSize="xs" color="fg.muted">{k.name}</Text>
                        </HStack>
                        <Text fontSize="sm" color="fg.muted">#{k.rank}</Text>
                      </Flex>
                    ))}
                    {bandingResult.sells.map(s => (
                      <Flex key={s.ticker} p="8px" bg="error.subtle" borderRadius="4px" justify="space-between">
                        <HStack gap="8px">
                          <Text fontSize="sm" color="error.fg">×</Text>
                          <Text fontSize="sm" color="fg" fontFamily="mono">{s.ticker}</Text>
                          <Text fontSize="xs" color="fg.muted">{s.reason}</Text>
                        </HStack>
                        <Text fontSize="sm" color="error.fg">SÄLJ</Text>
                      </Flex>
                    ))}
                  </VStack>

                  {/* Suggested buys */}
                  {bandingResult.suggested_buys.length > 0 && (
                    <Box>
                      <Text fontSize="sm" fontWeight="semibold" color="success.fg" mb="8px">Köp istället</Text>
                      <VStack gap="4px" align="stretch">
                        {bandingResult.suggested_buys.map(b => (
                          <Flex key={b.ticker} p="8px" bg="success.subtle" borderRadius="4px" justify="space-between">
                            <HStack gap="8px">
                              <Text fontSize="sm" color="fg" fontFamily="mono">{b.ticker}</Text>
                              <Text fontSize="xs" color="fg.muted">{b.name}</Text>
                            </HStack>
                            <Text fontSize="sm" color="success.fg">#{b.rank}</Text>
                          </Flex>
                        ))}
                      </VStack>
                    </Box>
                  )}

                  {/* Apply button */}
                  {bandingResult.sells.length > 0 && (
                    <Button colorPalette="blue" onClick={applyBandingTrades}>
                      Markera byten som genomförda
                    </Button>
                  )}

                  {bandingResult.sells.length === 0 && (
                    <Box p="12px" bg="success.subtle" borderRadius="6px" textAlign="center">
                      <Text color="success.fg" fontSize="sm">Inga byten behövs - alla aktier inom topp 20%</Text>
                    </Box>
                  )}
                </VStack>
              ) : (
                <VStack gap="8px" align="stretch">
                  <Text fontSize="sm" color="fg.muted" mb="8px">Dina {momentumHoldings.length} momentumaktier:</Text>
                  <Flex gap="8px" flexWrap="wrap">
                    {momentumHoldings.map(t => (
                      <Box key={t} px="8px" py="4px" bg="bg.muted" borderRadius="4px">
                        <Text fontSize="sm" color="fg" fontFamily="mono">{t}</Text>
                      </Box>
                    ))}
                  </Flex>
                  <Text fontSize="xs" color="fg.muted">Klicka "Kontrollera" för att se om några byten behövs</Text>
                </VStack>
              )}
            </Box>
          )}

          {/* Classic Mode - Timing Recommendations */}
          {!settings.bandingMode && (
            <Box bg="bg.subtle" borderRadius="8px" p="20px" borderColor="border" borderWidth="1px">
              <Text fontWeight="semibold" color="fg" mb="12px">📅 Nästa rebalansering</Text>
              <VStack gap="8px" align="stretch">
                {STRATEGIES.filter(s => selected.includes(s.key)).map(s => {
                  const nextDate = rebalanceDates[s.key];
                  const formatted = nextDate ? new Date(nextDate).toLocaleDateString('sv-SE', { day: 'numeric', month: 'long', year: 'numeric' }) : s.desc;
                  return (
                    <Flex key={s.key} justify="space-between" align="center" p="8px" bg="bg.muted" borderRadius="6px">
                      <HStack gap="8px">
                        <Box w="8px" h="8px" borderRadius="full" bg={s.color} />
                        <Text fontSize="sm" color="fg">{s.label}</Text>
                      </HStack>
                      <Text fontSize="sm" color={nextDate ? 'fg' : 'fg.muted'} fontWeight={nextDate ? 'semibold' : 'normal'}>
                        {nextDate ? formatted : s.desc}
                      </Text>
                    </Flex>
                  );
                })}
              </VStack>
              {selected.length === 0 && <Text fontSize="sm" color="fg.muted">Välj strategier i första fliken</Text>}
            </Box>
          )}

          {/* Classic Mode - Actions Summary */}
          {!settings.bandingMode && holdings.length > 0 && selected.length > 0 && (
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
                  <Text fontSize="sm" fontWeight="semibold" color="error.fg" mb="8px">Sälj</Text>
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
                  <Text fontSize="sm" fontWeight="semibold" color="success.fg" mb="8px">Köp</Text>
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
                  <Text fontSize="sm" fontWeight="semibold" color="fg" mb="4px">Uppskattad kostnad</Text>
                  <Text fontSize="sm" color="fg.muted">
                    Courtage: {formatSEK(costs.courtage)} • Spread: {formatSEK(costs.spread_estimate)} • Totalt: {formatSEK(costs.total)} ({costs.percentage?.toFixed(2)}%)
                  </Text>
                </Box>
              )}
            </Box>
          )}

          {/* Empty state for classic mode */}
          {!settings.bandingMode && (holdings.length === 0 || selected.length === 0) && (
            <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center">
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
