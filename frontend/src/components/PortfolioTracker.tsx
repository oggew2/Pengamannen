import { useState, useEffect, useMemo } from 'react';
import { Box, Text, Button, VStack, HStack, SimpleGrid, Input } from '@chakra-ui/react';
import { api, type RebalanceResponse } from '../api/client';
import { useRebalanceDates } from '../api/hooks';

interface LockedHolding {
  ticker: string;
  shares: number;
  buyPrice: number;
  buyDate: string;
  rankAtPurchase: number;
}

interface RebalanceStock {
  ticker: string;
  shares: number;
  currentRank: number | null;
  previousRank: number;
  value: number;
  currency: string;
  action: 'SELL' | 'HOLD' | 'BUY';
  reason?: string;
}

const STORAGE_KEY = 'borslabbet_locked_holdings';

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
  const [rebalanceData, setRebalanceData] = useState<{
    sells: RebalanceStock[];
    holds: RebalanceStock[];
    buys: RebalanceStock[];
    summary: string;
    costs?: { courtage: number; spread: number; total: number };
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastChecked, setLastChecked] = useState<string | null>(null);
  const [executedTrades, setExecutedTrades] = useState<{ sells: string[]; buys: string[] }>({ sells: [], buys: [] });
  const [newCapital, setNewCapital] = useState<string>('');
  
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

  // Load holdings from database (with localStorage fallback)
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
            return;
          }
        }
      } catch { /* fallback to localStorage */ }
      
      // Fallback to localStorage
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          setHoldings(JSON.parse(saved));
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
  const saveToDatabase = async (newHoldings: LockedHolding[]) => {
    try {
      await fetch('/v1/user/momentum-portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ holdings: newHoldings })
      });
    } catch { /* ignore - localStorage is backup */ }
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

  const checkRebalance = async () => {
    if (holdings.length === 0) return;
    
    setLoading(true);
    setError(null);
    setRebalanceData(null);
    try {
      const holdingsForApi = holdings.map(h => ({ ticker: h.ticker, shares: h.shares }));
      const newInvestment = parseFloat(newCapital) || 0;
      const res: RebalanceResponse = await api.calculateRebalance(holdingsForApi, newInvestment);
      
      const sells: RebalanceStock[] = res.sell.map(s => ({
        ticker: s.ticker,
        shares: s.shares,
        currentRank: s.rank,
        previousRank: holdings.find(h => h.ticker === s.ticker)?.rankAtPurchase || 0,
        value: s.value,
        currency: (s as any).currency || 'SEK',
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
          currency: (p as any).currency || 'SEK',
          action: 'HOLD' as const
        }));

      const buys: RebalanceStock[] = res.buy.map(b => ({
        ticker: b.ticker,
        shares: b.shares,
        currentRank: b.rank,
        previousRank: 0,
        value: b.value,
        currency: (b as any).currency || 'SEK',
        action: 'BUY' as const,
        reason: `Ny i topp 10 (rank ${b.rank})`
      }));

      const summary = sells.length === 0 && buys.length === 0
        ? '✓ Ingen ombalansering behövs'
        : `${sells.length} att sälja, ${buys.length} att köpa`;

      // Calculate transaction costs (Avanza: 0.069% min 1kr, spread ~0.3%)
      const sellValue = sells.reduce((sum, s) => sum + s.value, 0);
      const buyValue = buys.reduce((sum, b) => sum + b.value, 0);
      const totalTurnover = sellValue + buyValue;
      const courtage = Math.max(totalTurnover * 0.00069, (sells.length + buys.length));
      const spread = totalTurnover * 0.003;
      const costs = { courtage: Math.round(courtage), spread: Math.round(spread), total: Math.round(courtage + spread) };

      setRebalanceData({ sells, holds, buys, summary, costs });
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
      rebalanceData.sells.forEach(s => lines.push(`${s.ticker}\t${s.shares} st\t${formatPrice(s.value, s.currency)}`));
    }
    if (rebalanceData.buys.length) {
      lines.push('', 'KÖP:');
      rebalanceData.buys.forEach(b => lines.push(`${b.ticker}\t${b.shares} st\t${formatPrice(b.value, b.currency)}`));
    }
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers without clipboard API
      setError('Kunde inte kopiera. Markera texten manuellt.');
    }
  };

  const formatPrice = (v: number, currency: string = 'SEK') => {
    const formatted = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(v);
    if (currency === 'SEK') return `${formatted} kr`;
    return `${formatted} ${currency} (≈SEK)`;
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

  const saveExecutedTrades = () => {
    if (!rebalanceData) return;
    // Remove sold stocks, add bought stocks to holdings
    const newHoldings = holdings
      .filter(h => !executedTrades.sells.includes(h.ticker))
      .concat(
        rebalanceData.buys
          .filter(b => executedTrades.buys.includes(b.ticker))
          .map(b => ({
            ticker: b.ticker,
            shares: b.shares,
            buyPrice: b.value / b.shares,
            buyDate: new Date().toISOString(),
            rankAtPurchase: b.currentRank || 0
          }))
      );
    setHoldings(newHoldings);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newHoldings));
    saveToDatabase(newHoldings);  // Save to database
    setExecutedTrades({ sells: [], buys: [] });
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
          <HStack gap="8px">
            <Input
              type="number"
              placeholder="Nytt kapital"
              value={newCapital}
              onChange={e => setNewCapital(e.target.value)}
              size="xs"
              width="100px"
              bg="bg"
            />
            <Button size="xs" variant="outline" colorPalette="blue" onClick={checkRebalance} loading={loading}>
              🔄 Kolla
            </Button>
            <Button size="xs" variant="ghost" colorPalette="red" onClick={clearHoldings}>
              Rensa
            </Button>
          </HStack>
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
        <Text color="fg.muted" textAlign="center" py="20px">
          Ingen portfölj sparad. Använd "🔒 Lås in portfölj" ovan efter att du allokerat.
        </Text>
      ) : (
        <VStack align="stretch" gap="16px">
          {/* Current holdings summary */}
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
              <Text fontSize="xs" color="fg.muted">Låst</Text>
              <Text fontWeight="semibold">{holdings[0] ? formatDate(holdings[0].buyDate) : '—'}</Text>
            </Box>
          </HStack>

          {/* Holdings list */}
          <Box fontSize="sm">
            <HStack gap="8px" flexWrap="wrap">
              {holdings.map(h => (
                <Box key={h.ticker} bg="bg" px="8px" py="4px" borderRadius="md" borderWidth="1px" borderColor="border">
                  <Text fontWeight="medium">{h.ticker}</Text>
                  <Text fontSize="xs" color="fg.muted">{h.shares} st · #{h.rankAtPurchase}</Text>
                </Box>
              ))}
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

              {/* Buys - clickable with Avanza links */}
              {rebalanceData.buys.length > 0 && (
                <Box bg="green.900/20" borderColor="green.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="green.400" fontWeight="semibold" mb="8px">KÖP</Text>
                  <VStack gap="4px" align="stretch">
                    {rebalanceData.buys.map(b => (
                      <Box
                        key={b.ticker}
                        p="8px"
                        bg={executedTrades.buys.includes(b.ticker) ? 'green.900/30' : 'bg'}
                        borderRadius="4px"
                        cursor="pointer"
                        onClick={() => toggleExecuted('buys', b.ticker)}
                      >
                        <HStack justify="space-between" fontSize="sm">
                          <HStack gap="8px">
                            <Text color={executedTrades.buys.includes(b.ticker) ? 'green.400' : 'green.300'}>
                              {executedTrades.buys.includes(b.ticker) ? '✓' : '+'}
                            </Text>
                            <a
                              href={`https://www.avanza.se/aktier/om-aktien.html?query=${b.ticker}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                            >
                              <Text fontWeight="medium" color="green.300" textDecoration="underline">{b.ticker}</Text>
                            </a>
                            <Text fontSize="xs" color="fg.muted">#{b.currentRank}</Text>
                          </HStack>
                          <Text color="fg.muted">{b.shares} st = {formatSEK(b.value)}</Text>
                        </HStack>
                      </Box>
                    ))}
                  </VStack>
                  <Text fontSize="xs" color="fg.muted" mt="8px">Klicka för att markera • Ticker öppnar Avanza</Text>
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
