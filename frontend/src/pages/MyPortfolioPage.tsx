import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Box, Text, Button, HStack, VStack, Input } from '@chakra-ui/react';
import { api } from '../api/client';

interface Holding {
  ticker: string;
  shares: number;
  avgPrice: number;
}

interface Trade {
  ticker: string;
  action: 'BUY' | 'SELL';
  shares: number;
  amount_sek: number;
  price: number | null;
  isin?: string | null;
}

interface Strategy {
  name: string;
  display_name: string;
}

export default function MyPortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [ticker, setTicker] = useState('');
  const [shares, setShares] = useState('');
  const [avgPrice, setAvgPrice] = useState('');
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('sammansatt_momentum');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [costs, setCosts] = useState<{ courtage: number; spread_estimate: number; total: number; percentage: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [importResult, setImportResult] = useState<{ holdings: { ticker: string; shares: number }[]; total_fees_paid: number } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('myHoldings');
    if (saved) setHoldings(JSON.parse(saved));
    api.getStrategies().then(setStrategies).catch(() => {});
  }, []);

  useEffect(() => {
    holdings.forEach(h => {
      api.getStockPrices(h.ticker, 1).then(data => {
        if (data.prices?.length) setPrices(p => ({ ...p, [h.ticker]: data.prices[0].close }));
      }).catch(() => {});
    });
  }, [holdings]);

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
    localStorage.setItem('myHoldings', JSON.stringify(newHoldings));
    setImportResult(null);
  };

  const addHolding = () => {
    if (!ticker || !shares) return;
    const newHoldings = [...holdings, { ticker: ticker.toUpperCase(), shares: +shares, avgPrice: +avgPrice || 0 }];
    setHoldings(newHoldings);
    localStorage.setItem('myHoldings', JSON.stringify(newHoldings));
    setTicker(''); setShares(''); setAvgPrice('');
  };

  const removeHolding = (t: string) => {
    const newHoldings = holdings.filter(h => h.ticker !== t);
    setHoldings(newHoldings);
    localStorage.setItem('myHoldings', JSON.stringify(newHoldings));
  };

  const totalValue = holdings.reduce((sum, h) => sum + h.shares * (prices[h.ticker] || h.avgPrice), 0);
  const totalCost = holdings.reduce((sum, h) => sum + h.shares * h.avgPrice, 0);
  const totalPnL = totalValue - totalCost;
  const totalReturn = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

  const generateTrades = async () => {
    setLoading(true);
    const currentHoldings = holdings.map(h => ({ ticker: h.ticker, value: h.shares * (prices[h.ticker] || h.avgPrice) }));
    try {
      const data = await api.getRebalanceTrades(selectedStrategy, totalValue || 100000, currentHoldings.map(h => ({ ...h, shares: 0 })));
      setTrades(data.trades || []);
      setCosts(data.costs || null);
    } catch { setTrades([]); setCosts(null); }
    setLoading(false);
  };

  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0 }).format(v);

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="3xl" fontWeight="semibold" color="gray.50">My Portfolio</Text>

      {/* Summary Stats */}
      <HStack gap="16px" flexWrap="wrap">
        <Box flex="1" minW="150px" bg="gray.700" borderRadius="8px" p="16px">
          <Text fontSize="xs" color="gray.300">Total Value</Text>
          <Text fontSize="xl" fontWeight="bold" color="gray.50">{formatSEK(totalValue)}</Text>
        </Box>
        <Box flex="1" minW="150px" bg="gray.700" borderRadius="8px" p="16px">
          <Text fontSize="xs" color="gray.300">P&L</Text>
          <Text fontSize="xl" fontWeight="bold" color={totalPnL >= 0 ? 'success.500' : 'error.500'}>
            {totalPnL >= 0 ? '+' : ''}{formatSEK(totalPnL)}
          </Text>
        </Box>
        <Box flex="1" minW="150px" bg="gray.700" borderRadius="8px" p="16px">
          <Text fontSize="xs" color="gray.300">Return</Text>
          <Text fontSize="xl" fontWeight="bold" color={totalReturn >= 0 ? 'success.500' : 'error.500'}>
            {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(1)}%
          </Text>
        </Box>
      </HStack>

      {/* Import from Avanza */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
        <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="8px">Import from Avanza</Text>
        <Text fontSize="xs" color="gray.300" mb="12px">
          Export transactions: Avanza → Konto → Transaktioner → Exportera CSV
        </Text>
        <Input type="file" accept=".csv" onChange={handleCsvImport} size="sm" bg="gray.600" borderColor="gray.500" mb="8px" />
        {importResult && (
          <Box mt="8px" p="12px" bg="brand.500" borderRadius="6px">
            <Text fontSize="sm" color="white">Found {importResult.holdings.length} stocks, {formatSEK(importResult.total_fees_paid)} in fees</Text>
            <Button size="sm" mt="8px" bg="white" color="brand.500" onClick={applyImport}>Apply Import</Button>
          </Box>
        )}
      </Box>

      {/* Add Holding */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
        <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="12px">Add Holding</Text>
        <HStack gap="8px" flexWrap="wrap">
          <Input size="sm" placeholder="Ticker (e.g. VOLV-B)" value={ticker} onChange={e => setTicker(e.target.value)} bg="gray.600" borderColor="gray.500" flex="1" minW="120px" />
          <Input size="sm" type="number" placeholder="Shares" value={shares} onChange={e => setShares(e.target.value)} bg="gray.600" borderColor="gray.500" width="80px" />
          <Input size="sm" type="number" placeholder="Avg Price" value={avgPrice} onChange={e => setAvgPrice(e.target.value)} bg="gray.600" borderColor="gray.500" width="90px" />
          <Button size="sm" bg="brand.500" color="white" onClick={addHolding}>Add</Button>
        </HStack>
      </Box>

      {/* Holdings Table */}
      {holdings.length > 0 && (
        <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" overflow="hidden">
          <Box overflowX="auto">
            <Box as="table" width="100%" fontSize="sm">
              <Box as="thead" bg="gray.600">
                <Box as="tr">
                  <Box as="th" p="12px" textAlign="left" color="gray.200" fontWeight="medium">Ticker</Box>
                  <Box as="th" p="12px" textAlign="right" color="gray.200" fontWeight="medium">Shares</Box>
                  <Box as="th" p="12px" textAlign="right" color="gray.200" fontWeight="medium">Avg</Box>
                  <Box as="th" p="12px" textAlign="right" color="gray.200" fontWeight="medium">Current</Box>
                  <Box as="th" p="12px" textAlign="right" color="gray.200" fontWeight="medium">Value</Box>
                  <Box as="th" p="12px" textAlign="right" color="gray.200" fontWeight="medium">P&L</Box>
                  <Box as="th" p="12px" width="40px"></Box>
                </Box>
              </Box>
              <Box as="tbody">
                {holdings.map(h => {
                  const current = prices[h.ticker] || h.avgPrice;
                  const value = h.shares * current;
                  const pnl = h.shares * (current - h.avgPrice);
                  return (
                    <Box as="tr" key={h.ticker} borderTop="1px solid" borderColor="gray.600" _hover={{ bg: 'gray.650' }}>
                      <Box as="td" p="12px">
                        <Link to={`/stock/${h.ticker}`}>
                          <Text color="brand.500" fontWeight="medium" fontFamily="mono">{h.ticker}</Text>
                        </Link>
                      </Box>
                      <Box as="td" p="12px" textAlign="right" color="gray.100">{h.shares}</Box>
                      <Box as="td" p="12px" textAlign="right" color="gray.300">{h.avgPrice.toFixed(2)}</Box>
                      <Box as="td" p="12px" textAlign="right" color="gray.100">{current.toFixed(2)}</Box>
                      <Box as="td" p="12px" textAlign="right" color="gray.100">{formatSEK(value)}</Box>
                      <Box as="td" p="12px" textAlign="right" color={pnl >= 0 ? 'success.500' : 'error.500'} fontWeight="medium">
                        {pnl >= 0 ? '+' : ''}{formatSEK(pnl)}
                      </Box>
                      <Box as="td" p="12px">
                        <Button size="xs" variant="ghost" color="error.400" onClick={() => removeHolding(h.ticker)}>×</Button>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          </Box>
        </Box>
      )}

      {/* Rebalance Trades */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
        <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="12px">Rebalance to Strategy</Text>
        <HStack gap="8px" mb="16px" flexWrap="wrap">
          {strategies.map(s => (
            <Button
              key={s.name}
              size="sm"
              bg={selectedStrategy === s.name ? 'brand.500' : 'gray.600'}
              color={selectedStrategy === s.name ? 'white' : 'gray.200'}
              _hover={{ bg: selectedStrategy === s.name ? 'brand.600' : 'gray.500' }}
              onClick={() => setSelectedStrategy(s.name)}
            >
              {s.display_name.split(' ')[0]}
            </Button>
          ))}
          <Button size="sm" bg="brand.500" color="white" onClick={generateTrades} disabled={loading}>
            {loading ? 'Loading...' : 'Generate'}
          </Button>
        </HStack>

        {trades.length > 0 && (
          <>
            <VStack align="stretch" gap="8px" mb="16px">
              {trades.filter(t => t.action === 'SELL').length > 0 && (
                <Box>
                  <Text fontSize="xs" fontWeight="semibold" color="error.500" mb="4px">SELL</Text>
                  {trades.filter(t => t.action === 'SELL').map(t => (
                    <HStack key={t.ticker} justify="space-between" p="8px" bg="gray.600" borderRadius="4px" mb="4px">
                      <Text fontSize="sm" color="gray.100" fontFamily="mono">{t.ticker}</Text>
                      <HStack gap="16px">
                        <Text fontSize="xs" color="gray.300">{t.shares} @ {t.price?.toFixed(2) || '—'}</Text>
                        <Text fontSize="sm" color="error.500">{formatSEK(t.amount_sek)}</Text>
                        {t.isin && (
                          <Button size="xs" variant="ghost" color="brand.500" onClick={() => navigator.clipboard.writeText(t.isin!)}>
                            Copy ISIN
                          </Button>
                        )}
                      </HStack>
                    </HStack>
                  ))}
                </Box>
              )}
              {trades.filter(t => t.action === 'BUY').length > 0 && (
                <Box>
                  <Text fontSize="xs" fontWeight="semibold" color="success.500" mb="4px">BUY</Text>
                  {trades.filter(t => t.action === 'BUY').map(t => (
                    <HStack key={t.ticker} justify="space-between" p="8px" bg="gray.600" borderRadius="4px" mb="4px">
                      <Text fontSize="sm" color="gray.100" fontFamily="mono">{t.ticker}</Text>
                      <HStack gap="16px">
                        <Text fontSize="xs" color="gray.300">{t.shares} @ {t.price?.toFixed(2) || '—'}</Text>
                        <Text fontSize="sm" color="success.500">{formatSEK(t.amount_sek)}</Text>
                        {t.isin && (
                          <Button size="xs" variant="ghost" color="brand.500" onClick={() => navigator.clipboard.writeText(t.isin!)}>
                            Copy ISIN
                          </Button>
                        )}
                      </HStack>
                    </HStack>
                  ))}
                </Box>
              )}
            </VStack>
            {costs && (
              <Box p="12px" bg="warning.500" borderRadius="6px">
                <Text fontSize="sm" color="gray.900" fontWeight="semibold">
                  Est. Cost: {formatSEK(costs.total)} ({costs.percentage.toFixed(2)}%)
                </Text>
                <Text fontSize="xs" color="gray.700">
                  Courtage: {formatSEK(costs.courtage)} • Spread: {formatSEK(costs.spread_estimate)}
                </Text>
              </Box>
            )}
          </>
        )}
      </Box>
    </VStack>
  );
}
