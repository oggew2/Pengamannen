import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Box, Flex, Text, Button, HStack, VStack, Skeleton, Input } from '@chakra-ui/react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { api } from '../api/client';
import type { StockDetail } from '../types';

type Period = '1D' | '5D' | '1M' | '3M' | '1Y' | 'ALL';

interface UserHolding {
  ticker: string;
  shares: number;
  avgPrice: number;
}

export default function StockDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const [stock, setStock] = useState<StockDetail | null>(null);
  const [prices, setPrices] = useState<{ date: string; close: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<Period>('1Y');
  const [priceAlert, setPriceAlert] = useState('');
  const [userHolding, setUserHolding] = useState<UserHolding | null>(null);
  const [inStrategies, setInStrategies] = useState<string[]>([]);

  useEffect(() => {
    if (!ticker) return;
    // Load user's holding from localStorage
    const saved = localStorage.getItem('myHoldings');
    if (saved) {
      const holdings: UserHolding[] = JSON.parse(saved);
      const found = holdings.find(h => h.ticker === ticker || h.ticker === ticker.replace('.ST', ''));
      if (found) setUserHolding(found);
    }
    // Check which strategies contain this stock
    api.getStrategies().then(async (strategies) => {
      const found: string[] = [];
      for (const s of strategies) {
        try {
          const rankings = await api.getStrategyTop10(s.name);
          if (rankings.some(r => r.ticker === ticker || r.ticker.replace('.ST', '') === ticker?.replace('.ST', ''))) {
            found.push(s.display_name);
          }
        } catch {}
      }
      setInStrategies(found);
    });
  }, [ticker]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    const days = { '1D': 1, '5D': 5, '1M': 30, '3M': 90, '1Y': 365, 'ALL': 1825 }[period];
    Promise.all([
      api.getStock(ticker),
      api.getStockPrices(ticker, days).catch(() => ({ prices: [] }))
    ]).then(([stockData, priceData]) => {
      setStock(stockData);
      setPrices(priceData.prices || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [ticker, period]);

  const currentPrice = prices.length > 0 ? prices[prices.length - 1].close : 0;
  const prevPrice = prices.length > 1 ? prices[0].close : currentPrice;
  const priceChange = currentPrice - prevPrice;
  const priceChangePct = prevPrice > 0 ? (priceChange / prevPrice) * 100 : 0;

  const formatPct = (v: number | null) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '—';
  const formatNum = (v: number | null) => v != null ? v.toFixed(2) : '—';
  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0 }).format(v);

  if (loading) {
    return (
      <VStack gap="24px" align="stretch">
        <Skeleton height="200px" borderRadius="8px" />
        <Skeleton height="300px" borderRadius="8px" />
        <Skeleton height="150px" borderRadius="8px" />
      </VStack>
    );
  }

  if (!stock) {
    return <Text color="error.500">Stock not found</Text>;
  }

  return (
    <VStack gap="24px" align="stretch">
      {/* Header */}
      <Box>
        <Link to="/">
          <Text fontSize="sm" color="brand.500" mb="8px">← Back to Dashboard</Text>
        </Link>
        <HStack justify="space-between" align="start">
          <VStack align="start" gap="4px">
            <Text fontSize="2xl" fontWeight="bold" color="gray.50">{stock.ticker.replace('.ST', '')}</Text>
            <Text fontSize="sm" color="gray.200">{stock.name}</Text>
            <HStack gap="8px" fontSize="xs" color="gray.300">
              <Text>{stock.sector || 'Unknown'}</Text>
              {stock.market_cap && (
                <>
                  <Text>•</Text>
                  <Text>{(stock.market_cap / 1000000).toFixed(0)} MSEK</Text>
                </>
              )}
            </HStack>
            {inStrategies.length > 0 && (
              <Text fontSize="xs" color="brand.500">
                In: {inStrategies.join(', ')}
              </Text>
            )}
          </VStack>
          <VStack align="end" gap="2px">
            <Text fontSize="2xl" fontWeight="bold" color="gray.50">{currentPrice.toFixed(2)} kr</Text>
            <Text fontSize="sm" color={priceChange >= 0 ? 'success.500' : 'error.500'} fontWeight="semibold">
              {priceChange >= 0 ? '▲' : '▼'} {Math.abs(priceChange).toFixed(2)} ({formatPct(priceChangePct)})
            </Text>
          </VStack>
        </HStack>
      </Box>

      {/* Your Position (if holding) */}
      {userHolding && currentPrice > 0 && (
        <Box bg="gray.700" borderColor="brand.500" borderWidth="1px" borderRadius="8px" p="16px">
          <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="8px">Your Position</Text>
          <HStack justify="space-between" flexWrap="wrap" gap="16px">
            <VStack align="start" gap="2px">
              <Text fontSize="xs" color="gray.300">Shares</Text>
              <Text fontSize="sm" color="gray.100">{userHolding.shares}</Text>
            </VStack>
            <VStack align="start" gap="2px">
              <Text fontSize="xs" color="gray.300">Entry Price</Text>
              <Text fontSize="sm" color="gray.100">{userHolding.avgPrice.toFixed(2)} kr</Text>
            </VStack>
            <VStack align="start" gap="2px">
              <Text fontSize="xs" color="gray.300">Value</Text>
              <Text fontSize="sm" color="gray.100">{formatSEK(userHolding.shares * currentPrice)}</Text>
            </VStack>
            <VStack align="start" gap="2px">
              <Text fontSize="xs" color="gray.300">P&L</Text>
              {(() => {
                const pnl = userHolding.shares * (currentPrice - userHolding.avgPrice);
                const pnlPct = userHolding.avgPrice > 0 ? (pnl / (userHolding.shares * userHolding.avgPrice)) * 100 : 0;
                return (
                  <Text fontSize="sm" fontWeight="semibold" color={pnl >= 0 ? 'success.500' : 'error.500'}>
                    {pnl >= 0 ? '+' : ''}{formatSEK(pnl)} ({formatPct(pnlPct)})
                  </Text>
                );
              })()}
            </VStack>
          </HStack>
        </Box>
      )}

      {/* Returns Summary */}
      <HStack gap="16px" flexWrap="wrap">
        {[
          { label: '1M', value: stock.return_1m },
          { label: '3M', value: stock.return_3m },
          { label: '6M', value: stock.return_6m },
          { label: 'YTD', value: stock.return_12m },
        ].map(({ label, value }) => (
          <Box key={label} px="12px" py="8px" bg="gray.700" borderRadius="6px">
            <Text fontSize="xs" color="gray.300">{label}</Text>
            <Text fontSize="sm" fontWeight="semibold" color={value && value >= 0 ? 'success.500' : 'error.500'}>
              {formatPct(value)}
            </Text>
          </Box>
        ))}
      </HStack>

      {/* Price Chart */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="24px">
        <Flex justify="space-between" align="center" mb="16px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50">Price Chart</Text>
          <HStack gap="4px">
            {(['1D', '5D', '1M', '3M', '1Y', 'ALL'] as Period[]).map(p => (
              <Button
                key={p}
                size="xs"
                bg={period === p ? 'brand.500' : 'transparent'}
                color={period === p ? 'white' : 'gray.200'}
                _hover={{ bg: period === p ? 'brand.600' : 'gray.600' }}
                onClick={() => setPeriod(p)}
              >
                {p}
              </Button>
            ))}
          </HStack>
        </Flex>
        <Box height="250px">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={prices}>
              <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={{ stroke: '#374151' }} tickLine={false} />
              <YAxis domain={['auto', 'auto']} tick={{ fill: '#9ca3af', fontSize: 10 }} axisLine={false} tickLine={false} width={50} />
              <Tooltip
                contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: '6px' }}
                labelStyle={{ color: '#9ca3af' }}
                itemStyle={{ color: '#00b4d8' }}
              />
              <ReferenceLine y={prevPrice} stroke="#6b7280" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="close" stroke="#00b4d8" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      </Box>

      {/* Metrics Grid */}
      <Flex gap="16px" flexWrap="wrap">
        {/* Valuation */}
        <Box flex="1" minW="200px" bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
          <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="12px">Valuation</Text>
          <VStack align="stretch" gap="8px">
            {[
              { label: 'P/E', value: formatNum(stock.pe) },
              { label: 'P/B', value: formatNum(stock.pb) },
              { label: 'P/S', value: formatNum(stock.ps) },
              { label: 'EV/EBITDA', value: formatNum(stock.ev_ebitda) },
            ].map(({ label, value }) => (
              <HStack key={label} justify="space-between">
                <Text fontSize="xs" color="gray.300">{label}</Text>
                <Text fontSize="xs" color="gray.100" fontFamily="mono">{value}</Text>
              </HStack>
            ))}
          </VStack>
        </Box>

        {/* Quality */}
        <Box flex="1" minW="200px" bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
          <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="12px">Quality</Text>
          <VStack align="stretch" gap="8px">
            {[
              { label: 'ROE', value: formatPct(stock.roe) },
              { label: 'ROA', value: formatPct(stock.roa) },
              { label: 'ROIC', value: formatPct(stock.roic) },
              { label: 'Div Yield', value: formatPct(stock.dividend_yield) },
            ].map(({ label, value }) => (
              <HStack key={label} justify="space-between">
                <Text fontSize="xs" color="gray.300">{label}</Text>
                <Text fontSize="xs" color="gray.100" fontFamily="mono">{value}</Text>
              </HStack>
            ))}
          </VStack>
        </Box>
      </Flex>

      {/* Actions */}
      <Box bg="gray.700" borderColor="gray.600" borderWidth="1px" borderRadius="8px" p="16px">
        <Text fontSize="sm" fontWeight="semibold" color="gray.50" mb="12px">Actions</Text>
        <HStack gap="8px" flexWrap="wrap">
          <HStack gap="8px">
            <Input
              size="sm"
              placeholder="Price alert (kr)"
              value={priceAlert}
              onChange={(e) => setPriceAlert(e.target.value)}
              bg="gray.600"
              borderColor="gray.500"
              width="120px"
              type="number"
            />
            <Button size="sm" bg="brand.500" color="white" onClick={() => setPriceAlert('')}>
              Set Alert
            </Button>
          </HStack>
          <Link to="/dividends">
            <Button size="sm" variant="outline" borderColor="brand.500" color="brand.500">
              Dividend Calendar
            </Button>
          </Link>
        </HStack>
      </Box>
    </VStack>
  );
}
