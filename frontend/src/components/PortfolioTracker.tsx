import { useState, useEffect, useMemo } from 'react';
import { Box, Text, Button, VStack, HStack, SimpleGrid, Input } from '@chakra-ui/react';
import { api, type RebalanceResponse } from '../api/client';
import { useRebalanceDates } from '../api/hooks';
import { CsvImporter } from './CsvImporter';
import { PerformanceChart } from './PerformanceChart';

interface LockedHolding {
  ticker: string;
  shares: number;
  buyPrice: number;  // In SEK
  buyPriceLocal?: number;  // In original currency
  currency?: string;  // Original currency (SEK, EUR, DKK, NOK)
  buyDate: string;
  rankAtPurchase: number;
  currentRank?: number | null;  // Dynamic rank from API
  fees?: number;  // Transaction fees paid (Avanza courtage)
}

interface Transaction {
  date: string;
  type: 'BUY' | 'SELL' | 'EDIT';
  ticker: string;
  shares: number;
  price: number;
  fee: number;
}

interface RebalanceStock {
  ticker: string;
  shares: number;
  currentRank: number | null;
  previousRank: number;
  value: number;  // In local currency
  valueSek: number;  // In SEK
  currency: string;
  action: 'SELL' | 'HOLD' | 'BUY';
  reason?: string;
}

const STORAGE_KEY = 'borslabbet_locked_holdings';
const HISTORY_KEY = 'borslabbet_transaction_history';

// Quarterly momentum rebalance months (mid-month ~15th)
const REBALANCE_MONTHS = [3, 6, 9, 12];

function getNextRebalanceDate(): Date {
  const now = new Date();
  for (let offset = 0; offset < 12; offset++) {
    const check = new Date(now.getFullYear(), now.getMonth() + offset, 15);
    if (REBALANCE_MONTHS.includes(check.getMonth() + 1) && check > now) {
      return check;
    }
  }
  return new Date(now.getFullYear() + 1, 2, 15); // March next year
}

function isHighVolumeWarning(): boolean {
  const now = new Date();
  const day = now.getDate();
  const month = now.getMonth() + 1;
  // High volume: first/last week of month, or near quarterly rebalance
  return day <= 5 || day >= 25 || REBALANCE_MONTHS.includes(month);
}

function generateICS(nextDate: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  const formatDate = (d: Date) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  const uid = `momentum-rebalance-${formatDate(nextDate)}@borslabbet`;
  const now = new Date();
  return `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Borslabbet//Momentum Rebalance//SV
BEGIN:VEVENT
UID:${uid}
DTSTAMP:${formatDate(now)}T000000Z
DTSTART:${formatDate(nextDate)}
DTEND:${formatDate(nextDate)}
SUMMARY:📊 Momentum Ombalansering
DESCRIPTION:Dags att kolla din Sammansatt Momentum-portfölj!
END:VEVENT
END:VCALENDAR`;
}

export function PortfolioTracker() {
  const [holdings, setHoldings] = useState<LockedHolding[]>([]);
  const [transactionHistory, setTransactionHistory] = useState<Transaction[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showPerformance, setShowPerformance] = useState(false);
  const [rebalanceData, setRebalanceData] = useState<{
    sells: RebalanceStock[];
    holds: RebalanceStock[];
    buys: RebalanceStock[];  // Includes both topups (reason='undervikt') and new (reason='ny')
    summary: string;
    costs?: { courtage: number; spread: number; total: number };
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastChecked, setLastChecked] = useState<string | null>(null);
  const [executedTrades, setExecutedTrades] = useState<{ sells: string[]; buys: string[] }>({ sells: [], buys: [] });
  const [newCapital, setNewCapital] = useState<string>('');
  const [rebalanceMode, setRebalanceMode] = useState<'full' | 'add_only' | 'fix_drift'>('full');
  const [buyAdjustments, setBuyAdjustments] = useState<Record<string, number>>({});
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editShares, setEditShares] = useState<string>('');
  const [editPrice, setEditPrice] = useState<string>('');
  
  // Next rebalance countdown
  const { data: rebalanceDates } = useRebalanceDates();
  const nextRebalance = useMemo(() => {
    const momentum = rebalanceDates?.find(d => d.strategy_name === 'sammansatt_momentum');
    return momentum ? new Date(momentum.next_date) : getNextRebalanceDate();
  }, [rebalanceDates]);
  
  const daysUntil = useMemo(() => {
    const diff = nextRebalance.getTime() - Date.now();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  }, [nextRebalance]);
  
  const showVolumeWarning = isHighVolumeWarning();

  // Calculate drift for each holding (based on buy price, not current price)
  const driftData = useMemo(() => {
    if (holdings.length === 0) return { holdings: [], maxDrift: 0 };
    const total = holdings.reduce((sum, h) => sum + h.shares * h.buyPrice, 0);
    const targetWeight = 100 / holdings.length;
    const result = holdings.map(h => {
      const value = h.shares * h.buyPrice;
      const weight = total > 0 ? (value / total) * 100 : 0;
      const drift = weight - targetWeight;
      return { ticker: h.ticker, weight, drift };
    });
    const maxDrift = Math.max(...result.map(d => Math.abs(d.drift)));
    return { holdings: result, maxDrift };
  }, [holdings]);

  // Load holdings and history from database (with localStorage fallback)
  useEffect(() => {
    const loadHoldings = async () => {
      try {
        // Try database first
        const res = await fetch('/v1/user/momentum-portfolio', { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          if (data.holdings && data.holdings.length > 0) {
            setHoldings(data.holdings);
            // Sync to localStorage for offline access
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data.holdings));
          }
          if (data.history) {
            setTransactionHistory(data.history);
            localStorage.setItem(HISTORY_KEY, JSON.stringify(data.history));
          }
          return;
        }
      } catch { /* fallback to localStorage */ }
      
      // Fallback to localStorage
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          setHoldings(JSON.parse(saved));
        } catch { /* ignore */ }
      }
      const savedHistory = localStorage.getItem(HISTORY_KEY);
      if (savedHistory) {
        try {
          setTransactionHistory(JSON.parse(savedHistory));
        } catch { /* ignore */ }
      }
    };
    
    loadHoldings();
    
    // Listen for custom event (same-tab lock-in)
    const handleLockIn = () => loadHoldings();
    window.addEventListener('portfolio-locked-in', handleLockIn);
    
    return () => {
      window.removeEventListener('portfolio-locked-in', handleLockIn);
    };
  }, []);

  // Save to database when holdings change
  const saveToDatabase = async (newHoldings: LockedHolding[], newHistory?: Transaction[]) => {
    const historyToSave = newHistory || transactionHistory;
    try {
      const res = await fetch('/v1/user/momentum-portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ holdings: newHoldings, history: historyToSave })
      });
      if (!res.ok) console.error('Failed to save portfolio:', res.status);
    } catch (e) { console.error('Failed to save portfolio:', e); }
  };

  const addTransaction = (tx: Omit<Transaction, 'date'>) => {
    const newTx: Transaction = { ...tx, date: new Date().toISOString() };
    const newHistory = [...transactionHistory, newTx];
    setTransactionHistory(newHistory);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
    return newHistory;
  };

  const clearHoldings = () => {
    if (!confirm('Vill du rensa din sparade portfölj?')) return;
    setHoldings([]);
    setRebalanceData(null);
    setError(null);
    setLastChecked(null);
    localStorage.removeItem(STORAGE_KEY);
    saveToDatabase([]);  // Clear from database too
  };

  // Calculate Avanza courtage: 0.069% min 1 SEK
  const calculateFee = (value: number) => Math.max(1, Math.round(value * 0.00069));

  const startEditing = (h: LockedHolding) => {
    setEditingTicker(h.ticker);
    setEditShares(h.shares.toString());
    setEditPrice(h.buyPrice.toString());
  };

  const cancelEditing = () => {
    setEditingTicker(null);
    setEditShares('');
    setEditPrice('');
  };

  const saveEditing = () => {
    if (!editingTicker) return;
    const shares = parseInt(editShares) || 0;
    const price = parseFloat(editPrice) || 0;
    const oldHolding = holdings.find(h => h.ticker === editingTicker);
    
    if (shares <= 0) {
      // Delete holding if shares is 0
      deleteHolding(editingTicker);
    } else {
      const fee = calculateFee(shares * price);
      const newHoldings = holdings.map(h => 
        h.ticker === editingTicker 
          ? { ...h, shares, buyPrice: price, fees: fee }
          : h
      );
      // Log edit transaction
      const newHistory = addTransaction({
        type: 'EDIT',
        ticker: editingTicker,
        shares: shares - (oldHolding?.shares || 0),
        price,
        fee: 0,  // No fee for manual edits
      });
      setHoldings(newHoldings);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newHoldings));
      saveToDatabase(newHoldings, newHistory);
    }
    cancelEditing();
  };

  const deleteHolding = (ticker: string) => {
    if (!confirm(`Ta bort ${ticker} från portföljen?`)) return;
    const oldHolding = holdings.find(h => h.ticker === ticker);
    const newHoldings = holdings.filter(h => h.ticker !== ticker);
    // Log sell transaction
    const newHistory = addTransaction({
      type: 'SELL',
      ticker,
      shares: oldHolding?.shares || 0,
      price: oldHolding?.buyPrice || 0,
      fee: calculateFee((oldHolding?.shares || 0) * (oldHolding?.buyPrice || 0)),
    });
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newHoldings));
    saveToDatabase(newHoldings, newHistory);
    cancelEditing();
  };

  const checkRebalance = async () => {
    if (holdings.length === 0) return;
    
    setLoading(true);
    setError(null);
    setRebalanceData(null);
    try {
      const holdingsForApi = holdings.map(h => ({ ticker: h.ticker, shares: h.shares }));
      const newInvestment = parseFloat(newCapital) || 0;
      const res: RebalanceResponse = await api.calculateRebalance(holdingsForApi, newInvestment, rebalanceMode);
      
      const sells: RebalanceStock[] = res.sell.map(s => ({
        ticker: s.ticker,
        shares: s.shares,
        currentRank: s.rank,
        previousRank: holdings.find(h => h.ticker === s.ticker)?.rankAtPurchase || 0,
        value: s.value,
        valueSek: s.value_sek ?? s.value,
        currency: s.currency || 'SEK',
        action: 'SELL' as const,
        reason: s.rank && s.rank > 20 ? `Rank sjönk till ${s.rank}` : 'Ej längre i universum'
      }));

      const holds: RebalanceStock[] = res.final_portfolio
        .filter(p => p.action === 'HOLD')
        .map(p => ({
          ticker: p.ticker,
          shares: p.shares,
          currentRank: p.rank,
          previousRank: holdings.find(h => h.ticker === p.ticker)?.rankAtPurchase || 0,
          value: p.value,
          valueSek: p.value_sek ?? p.value,
          currency: p.currency || 'SEK',
          action: 'HOLD' as const
        }));

      // Separate new buys from topups (existing holdings that need more)
      const heldTickers = new Set(holdings.map(h => h.ticker));
      const allBuys: RebalanceStock[] = res.buy.map(b => ({
        ticker: b.ticker,
        shares: b.shares,
        currentRank: b.rank,
        previousRank: holdings.find(h => h.ticker === b.ticker)?.rankAtPurchase || 0,
        value: b.value,
        valueSek: b.value_sek ?? b.value,
        currency: b.currency || 'SEK',
        action: 'BUY' as const,
        reason: heldTickers.has(b.ticker) ? 'undervikt' : 'ny'
      }));
      
      // Sort: topups first (existing), then new positions
      allBuys.sort((a, b) => {
        const aIsTopup = a.reason === 'undervikt';
        const bIsTopup = b.reason === 'undervikt';
        if (aIsTopup && !bIsTopup) return -1;
        if (!aIsTopup && bIsTopup) return 1;
        return (a.currentRank || 99) - (b.currentRank || 99);
      });

      const summary = sells.length === 0 && allBuys.length === 0
        ? '✓ Portföljen är balanserad'
        : `${sells.length} sälj, ${allBuys.length} köp`;

      // Calculate transaction costs (Avanza: 0.069% min 1kr, spread ~0.3%)
      const sellValue = sells.reduce((sum, s) => sum + s.value, 0);
      const buyValue = allBuys.reduce((sum, b) => sum + b.value, 0);
      const totalTurnover = sellValue + buyValue;
      const courtage = Math.max(totalTurnover * 0.00069, (sells.length + allBuys.length));
      const spread = totalTurnover * 0.003;
      const costs = { courtage: Math.round(courtage), spread: Math.round(spread), total: Math.round(courtage + spread) };

      console.log('Rebalance result:', { sells: sells.length, holds: holds.length, buys: allBuys.length });
      setRebalanceData({ sells, holds, buys: allBuys, summary, costs });
      setBuyAdjustments({});  // Reset adjustments
      setExecutedTrades({ sells: [], buys: [] });
      setLastChecked(new Date().toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' }));
    } catch (err) {
      console.error('Rebalance check failed:', err);
      setError('Kunde inte hämta data. Försök igen.');
    } finally {
      setLoading(false);
    }
  };

  const copyTrades = async () => {
    if (!rebalanceData) return;
    const lines: string[] = [];
    if (rebalanceData.sells.length) {
      lines.push('SÄLJ:');
      rebalanceData.sells.forEach(s => lines.push(`${s.ticker}\t${s.shares} st\t${formatPrice(s.value, s.currency, s.valueSek)}`));
    }
    if (rebalanceData.buys.length) {
      lines.push('', 'KÖP:');
      rebalanceData.buys.forEach(b => {
        const tag = b.reason === 'undervikt' ? ' (fyll på)' : '';
        lines.push(`${b.ticker}${tag}\t${b.shares} st\t${formatPrice(b.value, b.currency, b.valueSek)}`);
      });
    }
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Kunde inte kopiera. Markera texten manuellt.');
    }
  };

  const formatPrice = (valueLocal: number, currency: string, valueSek: number) => {
    const sekFormatted = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(valueSek);
    if (currency === 'SEK') return `${sekFormatted} kr`;
    const localFormatted = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(valueLocal);
    return `${localFormatted} ${currency} (≈${sekFormatted} kr)`;
  };
  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(v) + ' kr';
  
  const toggleExecuted = (type: 'sells' | 'buys', ticker: string) => {
    setExecutedTrades(prev => ({
      ...prev,
      [type]: prev[type].includes(ticker)
        ? prev[type].filter(t => t !== ticker)
        : [...prev[type], ticker]
    }));
  };

  const adjustBuyShares = (ticker: string, delta: number) => {
    setBuyAdjustments(prev => {
      const base = rebalanceData?.buys.find(b => b.ticker === ticker)?.shares || 0;
      const current = prev[ticker] ?? base;
      const newVal = Math.max(0, current + delta);
      return { ...prev, [ticker]: newVal };
    });
  };

  const getBuyShares = (ticker: string, original: number) => buyAdjustments[ticker] ?? original;

  const saveExecutedTrades = () => {
    if (!rebalanceData) return;
    
    let newHistory = [...transactionHistory];
    
    // Log sell transactions
    rebalanceData.sells
      .filter(s => executedTrades.sells.includes(s.ticker))
      .forEach(s => {
        const oldHolding = holdings.find(h => h.ticker === s.ticker);
        newHistory.push({
          date: new Date().toISOString(),
          type: 'SELL',
          ticker: s.ticker,
          shares: oldHolding?.shares || s.shares,
          price: s.value / s.shares,
          fee: calculateFee(s.value),
        });
      });
    
    // Remove sold stocks
    let newHoldings = holdings.filter(h => !executedTrades.sells.includes(h.ticker));
    
    // Process buys (both topups and new positions)
    rebalanceData.buys
      .filter(b => executedTrades.buys.includes(b.ticker))
      .forEach(b => {
        const shares = getBuyShares(b.ticker, b.shares);
        const price = b.value / b.shares;
        const value = shares * price;
        const fee = calculateFee(value);
        
        newHistory.push({
          date: new Date().toISOString(),
          type: 'BUY',
          ticker: b.ticker,
          shares,
          price,
          fee,
        });
        
        const existing = newHoldings.find(h => h.ticker === b.ticker);
        if (existing) {
          // Topup: add to existing position
          existing.shares += shares;
          existing.fees = (existing.fees || 0) + fee;
        } else {
          // New position
          newHoldings.push({
            ticker: b.ticker,
            shares,
            buyPrice: price,
            buyDate: new Date().toISOString(),
            rankAtPurchase: b.currentRank || 0,
            fees: fee,
          });
        }
      });
    
    setTransactionHistory(newHistory);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newHoldings));
    saveToDatabase(newHoldings, newHistory);
    setExecutedTrades({ sells: [], buys: [] });
    setBuyAdjustments({});
    setRebalanceData(null);
    window.dispatchEvent(new Event('portfolio-locked-in'));
  };
  
  const downloadCalendar = () => {
    const ics = generateICS(nextRebalance);
    const blob = new Blob([ics], { type: 'text/calendar' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `momentum-rebalance-${nextRebalance.toISOString().slice(0, 10)}.ics`;
    a.click();
    URL.revokeObjectURL(url);
  };
  const formatDate = (d: string) => new Date(d).toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' });

  const totalValue = holdings.reduce((sum, h) => sum + (h.shares * h.buyPrice), 0);

  return (
    <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
      <HStack justify="space-between" mb="16px">
        <HStack gap="8px">
          <Text fontSize="lg" fontWeight="semibold">Min Portfölj</Text>
          {holdings.length > 0 && <Text fontSize="xs" color="green.400" title="Synkad till ditt konto">☁️</Text>}
        </HStack>
        {holdings.length > 0 && (
          <VStack gap="8px" align="flex-end">
            <HStack gap="8px">
              <Input
                type="number"
                placeholder="Nytt kapital (SEK)"
                value={newCapital}
                onChange={e => setNewCapital(e.target.value)}
                size="xs"
                width="120px"
                bg="bg"
              />
              <Button size="xs" variant="solid" colorPalette="blue" onClick={checkRebalance} loading={loading}>
                🔄 Kolla ombalansering
              </Button>
              <Button size="xs" variant="ghost" colorPalette="red" onClick={clearHoldings}>
                Rensa
              </Button>
            </HStack>
            {/* Segmented control for rebalance mode */}
            <HStack 
              gap="0" 
              bg="bg" 
              borderRadius="md" 
              borderWidth="1px" 
              borderColor="border"
              overflow="hidden"
            >
              <Box
                px="12px"
                py="4px"
                bg={rebalanceMode === 'full' ? 'blue.600' : 'transparent'}
                color={rebalanceMode === 'full' ? 'white' : 'fg.muted'}
                fontWeight={rebalanceMode === 'full' ? 'semibold' : 'normal'}
                fontSize="xs"
                cursor="pointer"
                onClick={() => setRebalanceMode('full')}
                title="Sälj aktier under rank 20, köp nya topp-aktier"
                _hover={{ bg: rebalanceMode === 'full' ? 'blue.600' : 'bg.subtle' }}
              >
                🔄 Kvartalsvis
              </Box>
              <Box
                px="12px"
                py="4px"
                bg={rebalanceMode === 'fix_drift' ? 'blue.600' : 'transparent'}
                color={rebalanceMode === 'fix_drift' ? 'white' : 'fg.muted'}
                fontWeight={rebalanceMode === 'fix_drift' ? 'semibold' : 'normal'}
                fontSize="xs"
                cursor="pointer"
                borderLeftWidth="1px"
                borderRightWidth="1px"
                borderColor="border"
                onClick={() => setRebalanceMode('fix_drift')}
                title="Sälj och återbalansera befintliga (köp inga nya)"
                _hover={{ bg: rebalanceMode === 'fix_drift' ? 'blue.600' : 'bg.subtle' }}
              >
                ⚖️ Balansera
              </Box>
              <Box
                px="12px"
                py="4px"
                bg={rebalanceMode === 'add_only' ? 'blue.600' : 'transparent'}
                color={rebalanceMode === 'add_only' ? 'white' : 'fg.muted'}
                fontWeight={rebalanceMode === 'add_only' ? 'semibold' : 'normal'}
                fontSize="xs"
                cursor="pointer"
                onClick={() => setRebalanceMode('add_only')}
                title="Lägg bara till nya positioner (sälj inget)"
                _hover={{ bg: rebalanceMode === 'add_only' ? 'blue.600' : 'bg.subtle' }}
              >
                💰 Månadsspar
              </Box>
            </HStack>
          </VStack>
        )}
      </HStack>

      {/* Next Rebalance Countdown */}
      <SimpleGrid columns={{ base: 1, md: 2 }} gap="12px" mb="16px">
        <Box bg="bg" borderRadius="8px" p="12px" borderWidth="1px" borderColor="border">
          <HStack justify="space-between">
            <Box>
              <Text fontSize="xs" color="fg.muted">Nästa ombalansering</Text>
              <HStack gap="8px" align="baseline">
                <Text fontSize="xl" fontWeight="bold" color={daysUntil <= 7 ? 'orange.400' : 'fg'}>
                  {daysUntil} dagar
                </Text>
                <Text fontSize="sm" color="fg.muted">
                  ({nextRebalance.toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' })})
                </Text>
              </HStack>
            </Box>
            <Button size="xs" variant="ghost" colorPalette="gray" onClick={downloadCalendar} title="Lägg till i kalender">
              📅
            </Button>
          </HStack>
        </Box>
        {showVolumeWarning && (
          <Box bg="orange.900/20" borderRadius="8px" p="12px" borderWidth="1px" borderColor="orange.500">
            <Text fontSize="xs" color="orange.400" fontWeight="semibold">⚠️ Hög volymperiod</Text>
            <Text fontSize="xs" color="fg.muted">Spreaden kan vara högre. Undvik öppning/stängning.</Text>
          </Box>
        )}
      </SimpleGrid>

      {holdings.length === 0 ? (
        <VStack gap="16px" py="20px">
          <Text color="fg.muted" textAlign="center">
            Ingen portfölj sparad. Använd "🔒 Lås in portfölj" ovan efter att du allokerat.
          </Text>
          <Text color="fg.muted" fontSize="sm">— eller —</Text>
          <Button size="sm" variant="outline" onClick={() => setShowImport(!showImport)}>
            📥 Importera från Avanza CSV
          </Button>
          {showImport && (
            <Box w="100%">
              <CsvImporter 
                onImportComplete={() => {}}
                onSyncComplete={(newHoldings) => {
                  const holdings: LockedHolding[] = newHoldings.map(h => ({
                    ticker: h.ticker,
                    shares: h.shares,
                    buyPrice: h.buyPrice,
                    buyDate: new Date().toISOString(),
                    rankAtPurchase: 0,
                  }));
                  setHoldings(holdings);
                  localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings));
                  setShowImport(false);
                }}
              />
            </Box>
          )}
        </VStack>
      ) : (
        <VStack align="stretch" gap="16px">
          {/* Current holdings summary */}
          <HStack gap="24px" flexWrap="wrap" justify="space-between">
            <HStack gap="24px" flexWrap="wrap">
              <Box>
                <Text fontSize="xs" color="fg.muted">Innehav</Text>
                <Text fontWeight="semibold">{holdings.length} aktier</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Inköpsvärde</Text>
                <Text fontWeight="semibold">{formatSEK(totalValue)}</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Courtage betalt</Text>
                <Text fontWeight="semibold">{formatSEK(holdings.reduce((sum, h) => sum + (h.fees || 0), 0))}</Text>
              </Box>
              <Box>
                <Text fontSize="xs" color="fg.muted">Låst</Text>
                <Text fontWeight="semibold">{holdings[0] ? formatDate(holdings[0].buyDate) : '—'}</Text>
              </Box>
            </HStack>
            <HStack gap="4px">
              <Button size="xs" variant="ghost" onClick={() => setShowPerformance(!showPerformance)}>
                📊 {showPerformance ? 'Dölj' : 'Översikt'}
              </Button>
              <Button size="xs" variant="ghost" onClick={() => setShowImport(!showImport)}>
                📥 {showImport ? 'Dölj' : 'Import'}
              </Button>
              <Button size="xs" variant="ghost" onClick={() => setShowHistory(!showHistory)}>
                📜 {showHistory ? 'Dölj' : 'Historik'}
              </Button>
            </HStack>
          </HStack>

          {/* Performance Overview */}
          {showPerformance && (
            <Box bg="bg" borderRadius="md" p="12px" borderWidth="1px" borderColor="border">
              <PerformanceChart />
            </Box>
          )}

          {/* CSV Import */}
          {showImport && (
            <Box bg="bg" borderRadius="md" p="12px" borderWidth="1px" borderColor="border">
              <CsvImporter 
                onImportComplete={() => {}}
                onSyncComplete={(newHoldings) => {
                  const holdings: LockedHolding[] = newHoldings.map(h => ({
                    ticker: h.ticker,
                    shares: h.shares,
                    buyPrice: h.buyPrice,
                    buyDate: new Date().toISOString(),
                    rankAtPurchase: 0,
                  }));
                  setHoldings(holdings);
                  localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings));
                  setShowImport(false);
                }}
              />
            </Box>
          )}

          {/* Transaction History */}
          {showHistory && transactionHistory.length > 0 && (
            <Box bg="bg" borderRadius="md" p="12px" borderWidth="1px" borderColor="border" maxH="200px" overflowY="auto">
              <Text fontSize="xs" fontWeight="semibold" mb="8px">Transaktionshistorik</Text>
              <VStack align="stretch" gap="4px">
                {[...transactionHistory].reverse().map((tx, i) => (
                  <HStack key={i} fontSize="xs" justify="space-between">
                    <HStack gap="8px">
                      <Text color="fg.muted">{new Date(tx.date).toLocaleDateString('sv-SE')}</Text>
                      <Text color={tx.type === 'BUY' ? 'green.400' : tx.type === 'SELL' ? 'red.400' : 'blue.400'}>
                        {tx.type === 'BUY' ? '🟢 Köp' : tx.type === 'SELL' ? '🔴 Sälj' : '✏️ Ändra'}
                      </Text>
                      <Text fontWeight="medium">{tx.ticker}</Text>
                    </HStack>
                    <HStack gap="8px">
                      <Text>{tx.shares > 0 ? '+' : ''}{tx.shares} st</Text>
                      <Text color="fg.muted">@ {tx.price.toFixed(2)}</Text>
                      {tx.fee > 0 && <Text color="fg.muted">(avg {tx.fee} kr)</Text>}
                    </HStack>
                  </HStack>
                ))}
              </VStack>
            </Box>
          )}
          {showHistory && transactionHistory.length === 0 && (
            <Text fontSize="xs" color="fg.muted">Ingen historik ännu.</Text>
          )}

          {/* Holdings list */}
          <Box fontSize="sm">
            {driftData.maxDrift > 2 && (
              <Text fontSize="xs" color="orange.400" mb="8px">
                ⚠️ Portföljen har driftat {driftData.maxDrift.toFixed(1)}% från målvikt. Överväg "Fix drift".
              </Text>
            )}
            <HStack gap="8px" flexWrap="wrap">
              {holdings.map(h => {
                const rank = h.currentRank ?? h.rankAtPurchase;
                const isInDanger = rank && rank > 15;
                const isSellZone = rank && rank > 20;
                const drift = driftData.holdings.find(d => d.ticker === h.ticker)?.drift ?? 0;
                const hasDrift = Math.abs(drift) > 2;
                const isEditing = editingTicker === h.ticker;
                
                if (isEditing) {
                  return (
                    <Box key={h.ticker} bg="blue.900/20" px="8px" py="4px" borderRadius="md" borderWidth="1px" borderColor="blue.500">
                      <Text fontWeight="medium" mb="4px">{h.ticker}</Text>
                      <HStack gap="4px" mb="4px">
                        <Input size="xs" width="60px" value={editShares} onChange={e => setEditShares(e.target.value)} placeholder="Antal" type="number" bg="bg" />
                        <Input size="xs" width="70px" value={editPrice} onChange={e => setEditPrice(e.target.value)} placeholder="Pris" type="number" step="0.01" bg="bg" />
                      </HStack>
                      <HStack gap="4px">
                        <Button size="xs" colorPalette="green" onClick={saveEditing}>✓</Button>
                        <Button size="xs" variant="ghost" onClick={cancelEditing}>✕</Button>
                        <Button size="xs" variant="ghost" colorPalette="red" onClick={() => deleteHolding(h.ticker)}>🗑</Button>
                      </HStack>
                    </Box>
                  );
                }
                
                return (
                  <Box 
                    key={h.ticker} 
                    bg={isSellZone ? 'red.900/20' : isInDanger ? 'orange.900/20' : 'bg'} 
                    px="8px" 
                    py="4px" 
                    borderRadius="md" 
                    borderWidth="1px" 
                    borderColor={isSellZone ? 'red.500' : isInDanger ? 'orange.500' : 'border'}
                    cursor="pointer"
                    onClick={() => startEditing(h)}
                    title="Klicka för att redigera"
                    _hover={{ borderColor: 'blue.400' }}
                  >
                    <Text fontWeight="medium">{h.ticker}</Text>
                    <Text fontSize="xs" color={isSellZone ? 'red.400' : isInDanger ? 'orange.400' : 'fg.muted'}>
                      {h.shares} st @ {(h.currency && h.currency !== 'SEK' && h.buyPriceLocal) 
                        ? `${h.buyPriceLocal.toFixed(2)} ${h.currency} ≈${h.buyPrice.toFixed(0)} kr`
                        : `${h.buyPrice.toFixed(2)} kr`}
                      {' · '}#{rank}{rank !== h.rankAtPurchase && ` (var #${h.rankAtPurchase})`}
                      {hasDrift && <Text as="span" color={drift > 0 ? 'green.400' : 'red.400'}> ({drift > 0 ? '+' : ''}{drift.toFixed(1)}%)</Text>}
                    </Text>
                  </Box>
                );
              })}
            </HStack>
          </Box>

          {/* Error message */}
          {error && (
            <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="md" p="12px">
              <Text fontSize="sm" color="red.400">{error}</Text>
            </Box>
          )}

          {/* Rebalance results */}
          {rebalanceData && (
            <VStack align="stretch" gap="12px" mt="8px">
              {/* Summary boxes */}
              <SimpleGrid columns={3} gap="8px">
                <Box p="12px" bg="blue.900/20" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="blue.400">{rebalanceData.holds.length}</Text>
                  <Text fontSize="xs" color="fg.muted">Behåll</Text>
                </Box>
                <Box p="12px" bg="red.900/20" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="red.400">{rebalanceData.sells.length}</Text>
                  <Text fontSize="xs" color="fg.muted">Sälj</Text>
                </Box>
                <Box p="12px" bg="green.900/20" borderRadius="6px" textAlign="center">
                  <Text fontSize="2xl" fontWeight="bold" color="green.400">{rebalanceData.buys.length}</Text>
                  <Text fontSize="xs" color="fg.muted">Köp</Text>
                </Box>
              </SimpleGrid>

              <HStack justify="space-between" flexWrap="wrap" gap="8px">
                <Text fontSize="xs" color="fg.muted">{lastChecked && `Kontrollerat ${lastChecked}`}</Text>
                <Button size="xs" variant="outline" colorPalette="gray" onClick={copyTrades}>
                  {copied ? '✓ Kopierat!' : '📋 Kopiera'}
                </Button>
              </HStack>

              {/* Sells - clickable */}
              {rebalanceData.sells.length > 0 && (
                <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="red.400" fontWeight="semibold" mb="8px">SÄLJ</Text>
                  <VStack gap="4px" align="stretch">
                    {rebalanceData.sells.map(s => (
                      <Box
                        key={s.ticker}
                        p="8px"
                        bg={executedTrades.sells.includes(s.ticker) ? 'green.900/30' : 'bg'}
                        borderRadius="4px"
                        cursor="pointer"
                        onClick={() => toggleExecuted('sells', s.ticker)}
                      >
                        <HStack justify="space-between" fontSize="sm">
                          <HStack gap="8px">
                            <Text color={executedTrades.sells.includes(s.ticker) ? 'green.400' : 'red.400'}>
                              {executedTrades.sells.includes(s.ticker) ? '✓' : '•'}
                            </Text>
                            <Text fontWeight="medium">{s.ticker}</Text>
                            <Text fontSize="xs" color="fg.muted">{s.reason}</Text>
                          </HStack>
                          <Text color="fg.muted">{s.shares} st</Text>
                        </HStack>
                      </Box>
                    ))}
                  </VStack>
                </Box>
              )}

              {/* Holds */}
              {rebalanceData.holds.length > 0 && (
                <Box bg="blue.900/20" borderColor="blue.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="blue.400" fontWeight="semibold" mb="8px">BEHÅLL</Text>
                  <HStack gap="8px" flexWrap="wrap">
                    {rebalanceData.holds.map(h => (
                      <Box key={h.ticker} px="8px" py="4px" bg="bg" borderRadius="4px">
                        <Text fontSize="sm" fontWeight="medium" display="inline">{h.ticker}</Text>
                        <Text fontSize="xs" color="fg.muted" display="inline" ml="4px">#{h.currentRank}</Text>
                      </Box>
                    ))}
                  </HStack>
                </Box>
              )}

              {/* Buys - merged list with undervikt/ny indicator */}
              {rebalanceData.buys.length > 0 && (
                <Box bg="green.900/20" borderColor="green.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="green.400" fontWeight="semibold" mb="8px">KÖP</Text>
                  <VStack gap="4px" align="stretch">
                    {rebalanceData.buys.map(b => {
                      const shares = getBuyShares(b.ticker, b.shares);
                      const priceLocal = b.shares > 0 ? b.value / b.shares : 0;
                      const priceSek = b.shares > 0 ? b.valueSek / b.shares : 0;
                      const valueLocal = shares * priceLocal;
                      const valueSek = shares * priceSek;
                      const isTopup = b.reason === 'undervikt';
                      return (
                        <Box key={b.ticker} p="8px" bg={executedTrades.buys.includes(b.ticker) ? 'green.900/30' : 'bg'} borderRadius="4px">
                          <HStack justify="space-between" fontSize="sm">
                            <HStack gap="8px">
                              <Text
                                color={executedTrades.buys.includes(b.ticker) ? 'green.400' : 'green.300'}
                                cursor="pointer"
                                onClick={() => toggleExecuted('buys', b.ticker)}
                              >
                                {executedTrades.buys.includes(b.ticker) ? '✓' : '+'}
                              </Text>
                              <a
                                href={`https://www.avanza.se/aktier/om-aktien.html?query=${b.ticker}`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <Text fontWeight="medium" color="green.300" textDecoration="underline">{b.ticker}</Text>
                              </a>
                              <Text fontSize="xs" color={isTopup ? 'yellow.400' : 'fg.muted'}>
                                #{b.currentRank} {isTopup && '↑'}
                              </Text>
                            </HStack>
                            <HStack gap="4px">
                              <Button size="xs" variant="ghost" onClick={() => adjustBuyShares(b.ticker, -1)}>−</Button>
                              <Text minW="50px" textAlign="center">{shares} st</Text>
                              <Button size="xs" variant="ghost" onClick={() => adjustBuyShares(b.ticker, 1)}>+</Button>
                              <Text color="fg.muted" minW="80px" textAlign="right">{formatPrice(valueLocal, b.currency, valueSek)}</Text>
                            </HStack>
                          </HStack>
                        </Box>
                      );
                    })}
                  </VStack>
                  <Text fontSize="xs" color="fg.muted" mt="8px">↑ = fyll på befintlig • ✓ = genomförd</Text>
                </Box>
              )}

              {/* Transaction Costs + Save Button */}
              <Box bg="bg" borderRadius="md" p="12px" borderWidth="1px" borderColor="border">
                <HStack justify="space-between" flexWrap="wrap" gap="12px">
                  {rebalanceData.costs && rebalanceData.costs.total > 0 && (
                    <HStack gap="16px" fontSize="sm">
                      <Text color="fg.muted">
                        Kostnad: {formatSEK(rebalanceData.costs.total)} 
                        <Text as="span" fontSize="xs"> (courtage + spread)</Text>
                      </Text>
                    </HStack>
                  )}
                  {(executedTrades.sells.length > 0 || executedTrades.buys.length > 0) && (
                    <Button size="sm" colorPalette="green" onClick={saveExecutedTrades}>
                      ✓ Spara {executedTrades.sells.length + executedTrades.buys.length} genomförda
                    </Button>
                  )}
                </HStack>
              </Box>
            </VStack>
          )}
        </VStack>
      )}
    </Box>
  );
}

// Hook to lock in holdings from AllocationCalculator
export function useLockInPortfolio() {
  const lockIn = async (allocations: Array<{ ticker: string; shares: number; price: number; rank: number }>) => {
    const holdings: LockedHolding[] = allocations
      .filter(a => a.shares > 0)
      .map(a => ({
        ticker: a.ticker,
        shares: a.shares,
        buyPrice: a.price,
        buyDate: new Date().toISOString(),
        rankAtPurchase: a.rank
      }));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings));
    
    // Save to database
    try {
      await fetch('/v1/user/momentum-portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ holdings })
      });
    } catch { /* localStorage is backup */ }
    
    // Dispatch event for same-tab listeners
    window.dispatchEvent(new Event('portfolio-locked-in'));
    return holdings.length;
  };

  return { lockIn };
}
