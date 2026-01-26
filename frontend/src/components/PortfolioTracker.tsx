import { useState, useEffect } from 'react';
import { Box, Text, Button, VStack, HStack } from '@chakra-ui/react';
import { api, type RebalanceResponse } from '../api/client';

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

export function PortfolioTracker() {
  const [holdings, setHoldings] = useState<LockedHolding[]>([]);
  const [rebalanceData, setRebalanceData] = useState<{
    sells: RebalanceStock[];
    holds: RebalanceStock[];
    buys: RebalanceStock[];
    summary: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  // Load holdings from localStorage (and listen for changes)
  useEffect(() => {
    const loadHoldings = () => {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          setHoldings(JSON.parse(saved));
        } catch { /* ignore */ }
      } else {
        setHoldings([]);
      }
    };
    
    loadHoldings();
    
    // Listen for storage changes (cross-tab)
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) loadHoldings();
    };
    window.addEventListener('storage', handleStorage);
    
    // Listen for custom event (same-tab lock-in)
    const handleLockIn = () => loadHoldings();
    window.addEventListener('portfolio-locked-in', handleLockIn);
    
    return () => {
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('portfolio-locked-in', handleLockIn);
    };
  }, []);

  const clearHoldings = () => {
    if (!confirm('Vill du rensa din sparade portfölj?')) return;
    setHoldings([]);
    setRebalanceData(null);
    setError(null);
    setLastChecked(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const checkRebalance = async () => {
    if (holdings.length === 0) return;
    
    setLoading(true);
    setError(null);
    setRebalanceData(null);
    try {
      const holdingsForApi = holdings.map(h => ({ ticker: h.ticker, shares: h.shares }));
      const res: RebalanceResponse = await api.calculateRebalance(holdingsForApi, 0);
      
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

      setRebalanceData({ sells, holds, buys, summary });
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
  const formatDate = (d: string) => new Date(d).toLocaleDateString('sv-SE', { day: 'numeric', month: 'short' });

  const totalValue = holdings.reduce((sum, h) => sum + (h.shares * h.buyPrice), 0);

  return (
    <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
      <HStack justify="space-between" mb="16px">
        <Text fontSize="lg" fontWeight="semibold">Min Portfölj</Text>
        {holdings.length > 0 && (
          <HStack gap="8px">
            <Button size="xs" variant="outline" colorPalette="blue" onClick={checkRebalance} loading={loading}>
              🔄 Kolla ombalansering
            </Button>
            <Button size="xs" variant="ghost" colorPalette="red" onClick={clearHoldings}>
              Rensa
            </Button>
          </HStack>
        )}
      </HStack>

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
              <HStack justify="space-between" flexWrap="wrap" gap="8px">
                <HStack gap="8px">
                  <Text fontWeight="semibold">{rebalanceData.summary}</Text>
                  {lastChecked && <Text fontSize="xs" color="fg.muted">({lastChecked})</Text>}
                </HStack>
                {(rebalanceData.sells.length > 0 || rebalanceData.buys.length > 0) && (
                  <Button size="xs" variant="outline" colorPalette="gray" onClick={copyTrades}>
                    {copied ? '✓ Kopierat!' : '📋 Kopiera trades'}
                  </Button>
                )}
              </HStack>

              {/* Sells */}
              {rebalanceData.sells.length > 0 && (
                <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="red.400" fontWeight="semibold" mb="8px">
                    🔴 SÄLJ ({rebalanceData.sells.length})
                  </Text>
                  {rebalanceData.sells.map(s => (
                    <HStack key={s.ticker} justify="space-between" fontSize="sm" mb="4px">
                      <Box>
                        <Text fontWeight="medium">{s.ticker}</Text>
                        <Text fontSize="xs" color="red.300">{s.reason}</Text>
                      </Box>
                      <Text>{s.shares} st = {formatPrice(s.value, s.currency)}</Text>
                    </HStack>
                  ))}
                </Box>
              )}

              {/* Holds */}
              {rebalanceData.holds.length > 0 && (
                <Box bg="blue.900/20" borderColor="blue.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="blue.400" fontWeight="semibold" mb="8px">
                    🔵 BEHÅLL ({rebalanceData.holds.length})
                  </Text>
                  <HStack gap="8px" flexWrap="wrap">
                    {rebalanceData.holds.map(h => (
                      <Box key={h.ticker} fontSize="sm">
                        <Text fontWeight="medium" display="inline">{h.ticker}</Text>
                        <Text fontSize="xs" color="fg.muted" display="inline" ml="4px">
                          #{h.previousRank}→#{h.currentRank}
                        </Text>
                      </Box>
                    ))}
                  </HStack>
                </Box>
              )}

              {/* Buys */}
              {rebalanceData.buys.length > 0 && (
                <Box bg="green.900/20" borderColor="green.500" borderWidth="1px" borderRadius="md" p="12px">
                  <Text fontSize="sm" color="green.400" fontWeight="semibold" mb="8px">
                    🟢 KÖP ({rebalanceData.buys.length})
                  </Text>
                  {rebalanceData.buys.map(b => (
                    <HStack key={b.ticker} justify="space-between" fontSize="sm" mb="4px">
                      <Box>
                        <Text fontWeight="medium">{b.ticker}</Text>
                        <Text fontSize="xs" color="green.300">{b.reason}</Text>
                      </Box>
                      <Text>{b.shares} st = {formatPrice(b.value, b.currency)}</Text>
                    </HStack>
                  ))}
                </Box>
              )}
            </VStack>
          )}
        </VStack>
      )}
    </Box>
  );
}

// Hook to lock in holdings from AllocationCalculator
export function useLockInPortfolio() {
  const lockIn = (allocations: Array<{ ticker: string; shares: number; price: number; rank: number }>) => {
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
    // Dispatch event for same-tab listeners
    window.dispatchEvent(new Event('portfolio-locked-in'));
    return holdings.length;
  };

  return { lockIn };
}
