import { useState, useEffect } from 'react';
import { Box, Flex, Text, VStack, HStack, Button } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys, useSyncData, useScanStocks, useSyncPrices, type ScanResult } from '../api/hooks';

interface SyncStatus {
  stocks: number;
  prices: number;
  fundamentals: number;
  latest_price_date: string | null;
  latest_fundamental_date: string | null;
}

interface StockUniverse {
  total: number;
  by_type: Record<string, number>;
  real_stocks: number;
}

interface ScanRange {
  start: number;
  end: number;
  name: string;
  last_scanned?: string | null;
  stocks_found?: number;
}

interface SyncHistoryEntry {
  id: number;
  timestamp: string;
  sync_type: string;
  success: boolean;
  duration_seconds: number | null;
  stocks_updated: number;
  prices_updated: number;
  error_message: string | null;
}

interface SyncHistoryResponse {
  history: SyncHistoryEntry[];
  last_successful_sync: string | null;
  next_scheduled_sync: string;
  sync_hour_utc: number;
  total_syncs: number;
  successful_syncs: number;
  failed_syncs: number;
}

function SyncStatusPanel() {
  const { data: history } = useQuery({
    queryKey: queryKeys.data.syncHistory(7),
    queryFn: () => api.get<SyncHistoryResponse>('/data/sync-history?days=7'),
    staleTime: 60 * 1000, // 1 min
  });

  if (!history) return null;

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('sv-SE') + ' ' + d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Box bg="gray.800" borderRadius="lg" p="6">
      <Flex justify="space-between" align="center" mb="4">
        <Text fontSize="lg" fontWeight="semibold" color="white">Sync History (7 days)</Text>
        <HStack gap="4">
          <Text fontSize="sm" color="green.400">✓ {history.successful_syncs}</Text>
          {history.failed_syncs > 0 && <Text fontSize="sm" color="red.400">✗ {history.failed_syncs}</Text>}
        </HStack>
      </Flex>

      <VStack align="stretch" gap="2" mb="4">
        <Flex justify="space-between" p="2" bg="gray.700" borderRadius="md">
          <Text color="gray.400" fontSize="sm">Last successful sync</Text>
          <Text color="green.400" fontSize="sm">
            {history.last_successful_sync ? formatDate(history.last_successful_sync) : 'Never'}
          </Text>
        </Flex>
        <Flex justify="space-between" p="2" bg="gray.700" borderRadius="md">
          <Text color="gray.400" fontSize="sm">Next scheduled sync</Text>
          <Text color="blue.400" fontSize="sm">{formatDate(history.next_scheduled_sync)}</Text>
        </Flex>
      </VStack>

      {history.history.length > 0 && (
        <VStack align="stretch" gap="1">
          <Text fontSize="sm" color="gray.400" mb="1">Recent syncs</Text>
          {history.history.slice(0, 5).map((entry) => (
            <Flex 
              key={entry.id} 
              justify="space-between" 
              p="2" 
              bg={entry.success ? 'gray.750' : 'red.900'} 
              borderRadius="md"
              borderLeftWidth="3px"
              borderColor={entry.success ? 'green.500' : 'red.500'}
            >
              <HStack gap="3">
                <Text color={entry.success ? 'green.400' : 'red.400'} fontSize="sm">
                  {entry.success ? '✓' : '✗'}
                </Text>
                <Text color="gray.300" fontSize="sm">{formatDate(entry.timestamp)}</Text>
              </HStack>
              <HStack gap="4">
                {entry.duration_seconds && (
                  <Text color="gray.500" fontSize="xs">{entry.duration_seconds.toFixed(0)}s</Text>
                )}
                <Text color="gray.400" fontSize="xs">{entry.stocks_updated} stocks</Text>
              </HStack>
            </Flex>
          ))}
        </VStack>
      )}

      {history.history.length === 0 && (
        <Text color="gray.500" fontSize="sm" textAlign="center" py="4">
          No sync history available
        </Text>
      )}
    </Box>
  );
}

export default function DataManagementPage() {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [stockUniverse, setStockUniverse] = useState<StockUniverse | null>(null);
  const [scanRanges, setScanRanges] = useState<ScanRange[]>([]);
  const [selectedRanges, setSelectedRanges] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [threads, setThreads] = useState(10);
  const [priceYears, setPriceYears] = useState(10);

  // Mutation hooks
  const syncMutation = useSyncData();
  const scanMutation = useScanStocks();
  const priceSyncMutation = useSyncPrices();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [status, universe, ranges] = await Promise.all([
        api.get<SyncStatus>('/data/sync-status').catch(() => null),
        api.get<StockUniverse>('/data/stocks/status').catch(() => null),
        api.get<ScanRange[]>('/data/stocks/ranges').catch(() => [])
      ]);
      if (status) setSyncStatus(status);
      if (universe) setStockUniverse(universe);
      setScanRanges(ranges);
    } catch (e) {
      console.error(e);
    }
  };

  const triggerSync = () => {
    setMessage('Syncing...');
    syncMutation.mutate(undefined, {
      onSuccess: () => {
        setMessage('Sync complete!');
        loadData();
      },
      onError: () => setMessage('Sync failed'),
    });
  };

  const scanForStocks = () => {
    setScanResult(null);
    setMessage('Scanning...');
    const ranges = selectedRanges.size > 0 
      ? scanRanges.filter(r => selectedRanges.has(`${r.start}-${r.end}`)).map(r => ({ start: r.start, end: r.end }))
      : undefined;
    
    scanMutation.mutate({ threads, ranges }, {
      onSuccess: (result) => {
        setScanResult(result);
        setMessage(`Found ${result.new_stocks_found} new stocks`);
        loadData();
      },
      onError: () => setMessage('Scan failed'),
    });
  };

  const toggleRange = (key: string) => {
    const s = new Set(selectedRanges);
    s.has(key) ? s.delete(key) : s.add(key);
    setSelectedRanges(s);
  };

  const syncExtendedPrices = () => {
    setMessage(`Syncing ${priceYears} years of prices...`);
    priceSyncMutation.mutate(priceYears, {
      onSuccess: (result) => {
        setMessage(`Synced ${result.stocks_synced} stocks with ${priceYears} years of data`);
        loadData();
      },
      onError: () => setMessage('Extended price sync failed'),
    });
  };

  return (
    <VStack gap="6" align="stretch" p="6">
      <Flex justify="space-between" align="center">
        <Text fontSize="2xl" fontWeight="semibold" color="white">Data Management</Text>
        <HStack>
          {message && <Text fontSize="sm" color="green.400">{message}</Text>}
          <Button 
            colorPalette="blue" 
            size="sm" 
            onClick={triggerSync} 
            loading={syncMutation.isPending}
          >
            Sync Now
          </Button>
        </HStack>
      </Flex>

      {/* Sync History Panel */}
      <SyncStatusPanel />

      {/* Data Status */}
      <Box bg="gray.800" borderRadius="lg" p="6">
        <Text fontSize="lg" fontWeight="semibold" color="white" mb="4">Data Status</Text>
        <VStack align="stretch" gap="3">
          <Flex justify="space-between">
            <Text color="gray.400">Stocks</Text>
            <Text color="white">{syncStatus?.stocks ?? 0}</Text>
          </Flex>
          <Flex justify="space-between">
            <Text color="gray.400">Prices</Text>
            <Text color="white">{syncStatus?.prices?.toLocaleString() ?? 0}</Text>
          </Flex>
          <Flex justify="space-between">
            <Text color="gray.400">Fundamentals</Text>
            <Text color="white">{syncStatus?.fundamentals ?? 0}</Text>
          </Flex>
          <Flex justify="space-between">
            <Text color="gray.400">Latest Price</Text>
            <Text color="white">{syncStatus?.latest_price_date ?? 'N/A'}</Text>
          </Flex>
        </VStack>
      </Box>

      {/* Stock Universe */}
      <Box bg="gray.800" borderRadius="lg" p="6">
        <Flex justify="space-between" align="center" mb="4">
          <Text fontSize="lg" fontWeight="semibold" color="white">Stock Universe</Text>
          <HStack>
            <select 
              value={threads} 
              onChange={(e) => setThreads(Number(e.target.value))}
              style={{ background: '#2D3748', color: 'white', border: 'none', borderRadius: '6px', padding: '6px 12px' }}
            >
              {[5, 10, 15, 20].map(n => <option key={n} value={n}>{n} threads</option>)}
            </select>
            <Button size="sm" colorPalette="blue" onClick={scanForStocks} loading={scanMutation.isPending}>
              Scan All
            </Button>
          </HStack>
        </Flex>

        {stockUniverse && (
          <VStack align="stretch" gap="2" mb="4">
            <Flex justify="space-between">
              <Text color="gray.400">Total</Text>
              <Text color="white">{stockUniverse.total}</Text>
            </Flex>
            <Flex justify="space-between">
              <Text color="gray.400">Real Stocks</Text>
              <Text color="green.400">{stockUniverse.real_stocks}</Text>
            </Flex>
            <Flex justify="space-between">
              <Text color="gray.400">ETFs (excluded)</Text>
              <Text color="gray.500">{stockUniverse.by_type?.etf_certificate ?? 0}</Text>
            </Flex>
          </VStack>
        )}

        <Text fontSize="sm" color="gray.400" mb="2">Scan Ranges (click to select)</Text>
        <VStack align="stretch" gap="2">
          {scanRanges.map(r => {
            const key = `${r.start}-${r.end}`;
            const selected = selectedRanges.has(key);
            return (
              <Flex 
                key={key}
                justify="space-between"
                p="3"
                bg={selected ? 'blue.900' : 'gray.700'}
                borderRadius="md"
                cursor="pointer"
                onClick={() => toggleRange(key)}
                borderWidth="1px"
                borderColor={selected ? 'blue.500' : 'transparent'}
              >
                <Box>
                  <Text color="white" fontSize="sm">{r.name}</Text>
                  <Text color="gray.500" fontSize="xs">{r.start.toLocaleString()} - {r.end.toLocaleString()}</Text>
                </Box>
                <Box textAlign="right">
                  <Text color={r.last_scanned ? 'green.400' : 'gray.500'} fontSize="xs">
                    {r.last_scanned ? new Date(r.last_scanned).toLocaleDateString() : 'Never'}
                  </Text>
                  {r.stocks_found ? <Text color="gray.400" fontSize="xs">{r.stocks_found} found</Text> : null}
                </Box>
              </Flex>
            );
          })}
        </VStack>

        {scanResult && scanResult.new_stocks_found > 0 && (
          <Box mt="4" p="3" bg="green.900" borderRadius="md">
            <Text color="green.300" fontWeight="medium">Found {scanResult.new_stocks_found} new stocks</Text>
            {scanResult.new_stocks.slice(0, 5).map(s => (
              <Text key={s.ticker} color="green.200" fontSize="sm">{s.ticker} - {s.name}</Text>
            ))}
          </Box>
        )}
      </Box>

      {/* Extended Price Sync */}
      <Box bg="gray.800" borderRadius="lg" p="6">
        <Flex justify="space-between" align="center" mb="4">
          <Box>
            <Text fontSize="lg" fontWeight="semibold" color="white">Extended Historical Prices</Text>
            <Text fontSize="sm" color="gray.400">Fetch 10+ years by stitching multiple API requests</Text>
          </Box>
          <HStack>
            <select 
              value={priceYears} 
              onChange={(e) => setPriceYears(Number(e.target.value))}
              style={{ background: '#2D3748', color: 'white', border: 'none', borderRadius: '6px', padding: '6px 12px' }}
            >
              {[5, 10, 15, 20].map(n => <option key={n} value={n}>{n} years</option>)}
            </select>
            <Button size="sm" colorPalette="orange" onClick={syncExtendedPrices} loading={priceSyncMutation.isPending}>
              Sync Extended
            </Button>
          </HStack>
        </Flex>
        <Text fontSize="xs" color="gray.500">
          Note: This makes multiple API calls per stock (~{Math.ceil(priceYears * 365 / 1800)} requests each). 
          Uses 3 threads to avoid rate limiting. May take 30+ minutes for all stocks.
        </Text>
      </Box>

      <Box bg="gray.900" p="4" borderRadius="md" borderLeftWidth="4px" borderColor="blue.400">
        <Text color="gray.400" fontSize="sm">
          <Text as="span" color="blue.400" fontWeight="medium">Data Source: </Text>
          Avanza API - Swedish stocks from Stockholmsbörsen and First North Stockholm.
        </Text>
      </Box>
    </VStack>
  );
}
