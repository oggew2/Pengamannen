import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Box, Text, Button, VStack, HStack, Badge } from '@chakra-ui/react';

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
  current_value: number;
  return_pct: number;
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

// Skeleton loader component
function ChartSkeleton() {
  return (
    <Box p={6}>
      <HStack justify="space-between" mb={4}>
        <VStack align="start" gap={2}>
          <Box w="80px" h="14px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
          <Box w="120px" h="32px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
        </VStack>
        <Box w="100px" h="32px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
      </HStack>
      <Box w="100%" h="120px" bg="gray.700" borderRadius="lg" className="skeleton-pulse" />
      <HStack gap={4} mt={4}>
        {[1,2,3,4].map(i => <Box key={i} flex="1" h="60px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />)}
      </HStack>
    </Box>
  );
}

export function PerformanceChart() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>('1Y');
  const [showNet, setShowNet] = useState(true);
  const [scrubIndex, setScrubIndex] = useState<number | null>(null);
  const chartRef = useRef<SVGSVGElement>(null);

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

  // Chart scrubbing handler - throttled
  const handleScrub = useCallback((e: React.TouchEvent | React.MouseEvent) => {
    if (!chartRef.current || !data?.chart_data) return;
    const rect = chartRef.current.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const x = (clientX - rect.left) / rect.width;
    const idx = Math.round(x * (data.chart_data.length - 1));
    setScrubIndex(Math.max(0, Math.min(data.chart_data.length - 1, idx)));
  }, [data?.chart_data]);

  if (loading) return <ChartSkeleton />;

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
      <Box p={8} bg="gray.800" borderRadius="lg" textAlign="center">
        {/* Empty state illustration */}
        <svg width="120" height="80" viewBox="0 0 120 80" style={{ margin: '0 auto 16px' }}>
          <rect x="10" y="50" width="20" height="25" rx="2" fill="#2D3748" />
          <rect x="35" y="35" width="20" height="40" rx="2" fill="#2D3748" />
          <rect x="60" y="20" width="20" height="55" rx="2" fill="#2D3748" />
          <rect x="85" y="10" width="20" height="65" rx="2" fill="#48BB78" opacity="0.6" />
          <path d="M15 45 L45 30 L75 15 L105 5" stroke="#48BB78" strokeWidth="2" fill="none" strokeLinecap="round" />
          <circle cx="105" cy="5" r="4" fill="#48BB78" />
        </svg>
        <Text color="gray.300" fontWeight="medium">Börja spåra din portfölj</Text>
        <Text color="gray.500" fontSize="sm" mt={2}>
          Importera en CSV-fil från Avanza för att se din utveckling över tid.
        </Text>
      </Box>
    );
  }

  const { summary, positions } = data;
  const returnPct = showNet ? summary.net_return_pct : summary.gross_return_pct;
  const isPositive = returnPct >= 0;

  // Memoize chart path calculations
  const chartPaths = useMemo(() => {
    if (!data.chart_data || data.chart_data.length < 2) return null;
    const pts = data.chart_data;
    const vals = pts.map(p => p.value);
    const min = Math.min(...vals) * 0.98;
    const max = Math.max(...vals) * 1.02;
    const range = max - min || 1;
    
    const getY = (v: number) => 100 - ((v - min) / range) * 85;
    const getX = (i: number) => (i / (pts.length - 1)) * 290 + 5;
    
    let linePath = `M ${getX(0)},${getY(vals[0])}`;
    for (let i = 1; i < pts.length; i++) {
      const x0 = getX(i - 1), y0 = getY(vals[i - 1]);
      const x1 = getX(i), y1 = getY(vals[i]);
      const cpx = (x0 + x1) / 2;
      linePath += ` C ${cpx},${y0} ${cpx},${y1} ${x1},${y1}`;
    }
    
    return { linePath, areaPath: linePath + ` L 295,110 L 5,110 Z`, vals, getX, getY };
  }, [data.chart_data]);

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

      {/* Line chart with scrubbing */}
      {data.chart_data && data.chart_data.length > 1 && (
        <Box bg="gray.800" p={4} borderRadius="lg" overflow="hidden">
          {/* Scrub value display */}
          {scrubIndex !== null && (
            <HStack justify="center" mb={2}>
              <Text fontSize="sm" color="gray.400">{data.chart_data[scrubIndex].date}</Text>
              <Text fontSize="sm" fontWeight="bold">{data.chart_data[scrubIndex].value.toLocaleString('sv-SE')} kr</Text>
            </HStack>
          )}
          <svg 
            ref={chartRef}
            viewBox="0 0 300 120" 
            style={{ width: '100%', height: '140px', touchAction: 'none', cursor: 'crosshair' }}
            onMouseMove={handleScrub}
            onMouseLeave={() => setScrubIndex(null)}
            onTouchMove={handleScrub}
            onTouchEnd={() => setScrubIndex(null)}
          >
            <defs>
              <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={isPositive ? '#48BB78' : '#F56565'} stopOpacity="0.3" />
                <stop offset="100%" stopColor={isPositive ? '#48BB78' : '#F56565'} stopOpacity="0" />
              </linearGradient>
            </defs>
            {chartPaths && (() => {
              const { linePath, areaPath, vals, getX, getY } = chartPaths;
              const color = isPositive ? '#48BB78' : '#F56565';
              const activeIdx = scrubIndex ?? vals.length - 1;
              
              return (
                <>
                  <path d={areaPath} fill="url(#areaGradient)" />
                  <path d={linePath} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
                  {scrubIndex !== null && (
                    <line x1={getX(scrubIndex)} y1="10" x2={getX(scrubIndex)} y2="110" stroke="white" strokeWidth="1" opacity="0.5" />
                  )}
                  <circle cx={getX(activeIdx)} cy={getY(vals[activeIdx])} r="5" fill={color} />
                  <circle cx={getX(activeIdx)} cy={getY(vals[activeIdx])} r="10" fill={color} opacity="0.2" />
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

      {/* Best & Worst Performers */}
      {positions.length >= 2 && (() => {
        const sorted = [...positions].sort((a, b) => b.return_pct - a.return_pct);
        const best = sorted[0];
        const worst = sorted[sorted.length - 1];
        return (
          <HStack gap={4}>
            <Box flex="1" bg="gray.800" p={3} borderRadius="md" borderLeft="3px solid" borderColor="green.400">
              <Text fontSize="xs" color="gray.400">🏆 Bäst</Text>
              <HStack justify="space-between">
                <Text fontWeight="bold">{best.ticker}</Text>
                <Text color="green.400" fontWeight="bold">+{best.return_pct.toFixed(1)}%</Text>
              </HStack>
            </Box>
            <Box flex="1" bg="gray.800" p={3} borderRadius="md" borderLeft="3px solid" borderColor="red.400">
              <Text fontSize="xs" color="gray.400">📉 Sämst</Text>
              <HStack justify="space-between">
                <Text fontWeight="bold">{worst.ticker}</Text>
                <Text color={worst.return_pct >= 0 ? 'green.400' : 'red.400'} fontWeight="bold">
                  {worst.return_pct >= 0 ? '+' : ''}{worst.return_pct.toFixed(1)}%
                </Text>
              </HStack>
            </Box>
          </HStack>
        );
      })()}

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
                  <Box as="th" textAlign="right" py={2} color="gray.400">Värde</Box>
                  <Box as="th" textAlign="right" py={2} color="gray.400">Avkastning</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {[...positions].sort((a, b) => b.return_pct - a.return_pct).map((pos) => (
                  <Box as="tr" key={pos.ticker} borderBottom="1px" borderColor="gray.700">
                    <Box as="td" py={2}>
                      <Text fontWeight="medium">{pos.ticker}</Text>
                      <Text fontSize="xs" color="gray.500">{pos.shares} st @ {pos.avg_price.toFixed(0)} kr</Text>
                    </Box>
                    <Box as="td" py={2} textAlign="right">{Math.round(pos.current_value).toLocaleString('sv-SE')} kr</Box>
                    <Box as="td" py={2} textAlign="right">
                      <Text color={pos.return_pct >= 0 ? 'green.400' : 'red.400'} fontWeight="medium">
                        {pos.return_pct >= 0 ? '+' : ''}{pos.return_pct.toFixed(1)}%
                      </Text>
                    </Box>
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
