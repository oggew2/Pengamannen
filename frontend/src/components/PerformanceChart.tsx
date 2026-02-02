import { useState, useEffect } from 'react';
import { Box, Text, Button, VStack, HStack, Spinner, Badge } from '@chakra-ui/react';

interface PerformanceSummary {
  total_invested: number;
  current_value: number;
  gross_return: number;
  gross_return_pct: number;
  net_return_pct: number;
  total_fees: number;
  estimated_spread: number;
  total_costs: number;
  cost_impact_pct: number;
}

interface Position {
  ticker: string;
  shares: number;
  cost: number;
  avg_price: number;
  fees: number;
}

interface ChartPoint {
  date: string;
  value: number;
}

interface PerformanceData {
  summary: PerformanceSummary | null;
  positions: Position[];
  period: string;
  message?: string;
  warning?: string;
  chart_data?: ChartPoint[];
}

type Period = '1M' | '3M' | '6M' | 'YTD' | '1Y' | 'ALL';

export function PerformanceChart() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>('1Y');
  const [showNet, setShowNet] = useState(true);

  useEffect(() => {
    fetchPerformance();
  }, [period]);

  const fetchPerformance = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/v1/portfolio/performance?period=${period}`, {
        credentials: 'include',
      });

      if (!res.ok) {
        throw new Error('Failed to fetch performance data');
      }

      const result: PerformanceData = await res.json();
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box p={6} textAlign="center">
        <Spinner size="lg" color="blue.400" />
        <Text mt={2} color="gray.400">Laddar...</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={6} bg="red.900" borderRadius="lg">
        <Text color="red.200">{error}</Text>
        <Button mt={2} size="sm" onClick={fetchPerformance}>Försök igen</Button>
      </Box>
    );
  }

  if (!data?.summary) {
    return (
      <Box p={6} bg="gray.800" borderRadius="lg" textAlign="center">
        <Text color="gray.400">Inga transaktioner importerade ännu.</Text>
        <Text color="gray.500" fontSize="sm" mt={2}>
          Importera en CSV-fil för att se din portföljutveckling.
        </Text>
      </Box>
    );
  }

  const { summary, positions } = data;
  const returnPct = showNet ? summary.net_return_pct : summary.gross_return_pct;
  const isPositive = returnPct >= 0;

  return (
    <VStack gap={4} align="stretch">
      {/* Warning if price data missing */}
      {data.warning && (
        <Box bg="orange.900" p={3} borderRadius="md">
          <Text color="orange.200" fontSize="sm">⚠️ {data.warning}</Text>
        </Box>
      )}
      
      {/* Period selector */}
      <HStack justify="space-between" flexWrap="wrap">
        <Text fontSize="lg" fontWeight="bold">📊 Portföljöversikt</Text>
        <HStack gap={1}>
          {(['1M', '3M', '6M', 'YTD', '1Y', 'ALL'] as Period[]).map((p) => (
            <Button
              key={p}
              size="xs"
              variant={period === p ? 'solid' : 'ghost'}
              colorScheme={period === p ? 'blue' : 'gray'}
              onClick={() => setPeriod(p)}
            >
              {p}
            </Button>
          ))}
        </HStack>
      </HStack>

      {/* Main return display */}
      <Box bg="gray.800" p={4} borderRadius="lg">
        <HStack justify="space-between" align="start">
          <VStack align="start" gap={1}>
            <Text color="gray.400" fontSize="sm">Avkastning</Text>
            <Text
              fontSize="3xl"
              fontWeight="bold"
              color={isPositive ? 'green.400' : 'red.400'}
            >
              {isPositive ? '+' : ''}{returnPct.toFixed(1)}%
            </Text>
            <Text color="gray.500" fontSize="sm">
              {showNet ? 'netto, efter avgifter' : 'brutto'}
            </Text>
          </VStack>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowNet(!showNet)}
          >
            {showNet ? '📊 Visa brutto' : '💰 Visa netto'}
          </Button>
        </HStack>
      </Box>

      {/* Line chart */}
      {data.chart_data && data.chart_data.length > 1 && (
        <Box bg="gray.800" p={4} borderRadius="lg" overflow="hidden">
          <svg viewBox="0 0 300 120" style={{ width: '100%', height: '140px' }}>
            <defs>
              <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? '#48BB78' : '#F56565'} stopOpacity="0.3" />
                <stop offset="100%" stopColor={isPositive ? '#48BB78' : '#F56565'} stopOpacity="0" />
              </linearGradient>
            </defs>
            {(() => {
              const pts = data.chart_data!;
              const vals = pts.map(p => p.value);
              const min = Math.min(...vals) * 0.98;
              const max = Math.max(...vals) * 1.02;
              const range = max - min || 1;
              
              // Build smooth curve path
              const getY = (v: number) => 100 - ((v - min) / range) * 85;
              const getX = (i: number) => (i / (pts.length - 1)) * 290 + 5;
              
              // Create smooth bezier curve
              let linePath = `M ${getX(0)},${getY(vals[0])}`;
              for (let i = 1; i < pts.length; i++) {
                const x0 = getX(i - 1), y0 = getY(vals[i - 1]);
                const x1 = getX(i), y1 = getY(vals[i]);
                const cpx = (x0 + x1) / 2;
                linePath += ` C ${cpx},${y0} ${cpx},${y1} ${x1},${y1}`;
              }
              
              // Area path (close to bottom)
              const areaPath = linePath + ` L 295,110 L 5,110 Z`;
              
              const color = isPositive ? '#48BB78' : '#F56565';
              
              return (
                <>
                  {/* Gradient fill area */}
                  <path d={areaPath} fill="url(#areaGradient)" />
                  {/* Main line */}
                  <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  {/* End dot with glow */}
                  <circle cx={getX(pts.length - 1)} cy={getY(vals[vals.length - 1])} r="4" fill={color} />
                  <circle cx={getX(pts.length - 1)} cy={getY(vals[vals.length - 1])} r="8" fill={color} opacity="0.3" />
                </>
              );
            })()}
          </svg>
          <HStack justify="space-between" mt={1}>
            <Text fontSize="xs" color="gray.500">{data.chart_data[0].date}</Text>
            <Text fontSize="xs" color="gray.500">{data.chart_data[data.chart_data.length - 1].date}</Text>
          </HStack>
        </Box>
      )}

      {/* Stats grid */}
      <HStack gap={4} flexWrap="wrap">
        <Box flex="1" minW="120px" bg="gray.800" p={3} borderRadius="md">
          <Text color="gray.400" fontSize="xs">Investerat</Text>
          <Text fontWeight="bold">{Math.round(summary.total_invested).toLocaleString('sv-SE')} kr</Text>
        </Box>
        <Box flex="1" minW="120px" bg="gray.800" p={3} borderRadius="md">
          <Text color="gray.400" fontSize="xs">Nuvarande värde</Text>
          <Text fontWeight="bold">{Math.round(summary.current_value).toLocaleString('sv-SE')} kr</Text>
        </Box>
        <Box flex="1" minW="120px" bg="gray.800" p={3} borderRadius="md">
          <Text color="gray.400" fontSize="xs">Avkastning</Text>
          <Text fontWeight="bold" color={summary.gross_return >= 0 ? 'green.400' : 'red.400'}>
            {summary.gross_return >= 0 ? '+' : ''}{Math.round(summary.gross_return).toLocaleString('sv-SE')} kr
          </Text>
        </Box>
        <Box flex="1" minW="120px" bg="gray.800" p={3} borderRadius="md">
          <Text color="gray.400" fontSize="xs">Kostnader</Text>
          <Text fontWeight="bold">{Math.round(summary.total_costs).toLocaleString('sv-SE')} kr</Text>
        </Box>
      </HStack>

      {/* Cost breakdown */}
      <Box bg="gray.800" p={4} borderRadius="lg">
        <Text fontWeight="medium" mb={3}>Kostnadsfördelning</Text>
        <VStack align="stretch" gap={2}>
          <HStack justify="space-between">
            <Text color="gray.400">Courtage (faktisk)</Text>
            <Text>{Math.round(summary.total_fees).toLocaleString('sv-SE')} kr</Text>
          </HStack>
          <HStack justify="space-between">
            <HStack>
              <Text color="gray.400">Spread (uppskattad)</Text>
              <Badge size="sm" colorScheme="gray">0.3%</Badge>
            </HStack>
            <Text>{Math.round(summary.estimated_spread).toLocaleString('sv-SE')} kr</Text>
          </HStack>
          <Box borderTop="1px" borderColor="gray.600" pt={2}>
            <HStack justify="space-between">
              <Text fontWeight="medium">Totalt</Text>
              <HStack>
                <Text fontWeight="bold">{Math.round(summary.total_costs).toLocaleString('sv-SE')} kr</Text>
                <Text color="gray.400">({summary.cost_impact_pct.toFixed(2)}%)</Text>
              </HStack>
            </HStack>
          </Box>
        </VStack>
        <Text fontSize="xs" color="gray.500" mt={3}>
          💡 Spread är en uppskattning baserad på 0.3% av omsättning
        </Text>
      </Box>

      {/* Holdings table */}
      {positions.length > 0 && (
        <Box bg="gray.800" p={4} borderRadius="lg">
          <Text fontWeight="medium" mb={3}>Innehav</Text>
          <Box overflowX="auto">
            <Box as="table" w="100%" fontSize="sm">
              <Box as="thead">
                <Box as="tr" borderBottom="1px" borderColor="gray.600">
                  <Box as="th" textAlign="left" py={2} color="gray.400">Aktie</Box>
                  <Box as="th" textAlign="right" py={2} color="gray.400">Antal</Box>
                  <Box as="th" textAlign="right" py={2} color="gray.400">Kostnad</Box>
                  <Box as="th" textAlign="right" py={2} color="gray.400">Snitt</Box>
                  <Box as="th" textAlign="right" py={2} color="gray.400">Avgifter</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {positions.map((pos) => (
                  <Box as="tr" key={pos.ticker} borderBottom="1px" borderColor="gray.700">
                    <Box as="td" py={2} fontWeight="medium">{pos.ticker}</Box>
                    <Box as="td" py={2} textAlign="right">{pos.shares} st</Box>
                    <Box as="td" py={2} textAlign="right">{Math.round(pos.cost).toLocaleString('sv-SE')} kr</Box>
                    <Box as="td" py={2} textAlign="right">{pos.avg_price.toFixed(2)} kr</Box>
                    <Box as="td" py={2} textAlign="right">{Math.round(pos.fees).toLocaleString('sv-SE')} kr</Box>
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </Box>
      )}
    </VStack>
  );
}
