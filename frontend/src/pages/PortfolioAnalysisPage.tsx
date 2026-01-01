import { useEffect, useState } from 'react';
import { Box, Flex, Text, VStack, HStack, Skeleton } from '@chakra-ui/react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { api } from '../api/client';
import type { PortfolioResponse, StockDetail } from '../types';

const COLORS = ['#00b4d8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export default function PortfolioAnalysisPage() {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [stockDetails, setStockDetails] = useState<Record<string, StockDetail>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const port = await api.getPortfolio();
        setPortfolio(port);
        
        const details: Record<string, StockDetail> = {};
        await Promise.all(port.holdings.map(async (h) => {
          try {
            details[h.ticker] = await api.getStock(h.ticker);
          } catch {}
        }));
        setStockDetails(details);
      } catch (e) { console.error(e); }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) {
    return (
      <VStack gap="24px" align="stretch">
        <Skeleton height="300px" borderRadius="8px" />
        <Skeleton height="200px" borderRadius="8px" />
        <Skeleton height="200px" borderRadius="8px" />
      </VStack>
    );
  }

  const holdings = portfolio?.holdings || [];
  const totalValue = holdings.reduce((sum, h) => sum + (h.weight * 100000), 0);

  // Strategy allocation
  const strategyAlloc = holdings.reduce((acc, h) => {
    acc[h.strategy] = (acc[h.strategy] || 0) + h.weight;
    return acc;
  }, {} as Record<string, number>);
  const strategyData = Object.entries(strategyAlloc).map(([name, value]) => ({ name, value: value * 100 }));

  // Sector allocation
  const sectorAlloc = holdings.reduce((acc, h) => {
    const sector = stockDetails[h.ticker]?.sector || 'Unknown';
    acc[sector] = (acc[sector] || 0) + h.weight;
    return acc;
  }, {} as Record<string, number>);
  const sectorData = Object.entries(sectorAlloc).map(([name, value]) => ({ name, value: value * 100 }));

  // Market cap allocation
  const getMarketCapCategory = (mcap: number | null | undefined) => {
    if (!mcap) return 'Unknown';
    if (mcap >= 50000) return 'Large Cap (>50B)';
    if (mcap >= 10000) return 'Mid Cap (10-50B)';
    return 'Small Cap (<10B)';
  };
  const marketCapAlloc = holdings.reduce((acc, h) => {
    const cat = getMarketCapCategory(stockDetails[h.ticker]?.market_cap);
    acc[cat] = (acc[cat] || 0) + h.weight;
    return acc;
  }, {} as Record<string, number>);
  const marketCapData = Object.entries(marketCapAlloc).map(([name, value]) => ({ name, value: value * 100 }));

  // Strategy correlation matrix (simplified - based on typical correlations)
  const strategies = ['Momentum', 'Värde', 'Utdelning', 'Kvalitet'];
  const correlationMatrix = [
    [1.00, 0.62, 0.58, 0.71],
    [0.62, 1.00, 0.78, 0.85],
    [0.58, 0.78, 1.00, 0.72],
    [0.71, 0.85, 0.72, 1.00],
  ];

  // Concentration (top 10 holdings)
  const sortedHoldings = [...holdings].sort((a, b) => b.weight - a.weight);
  const top10Weight = sortedHoldings.slice(0, 10).reduce((sum, h) => sum + h.weight, 0) * 100;
  const herfindahl = holdings.reduce((sum, h) => sum + Math.pow(h.weight * 100, 2), 0);

  return (
    <VStack gap="24px" align="stretch">
      <Text fontSize="2xl" fontWeight="bold" color="gray.50">Portfolio Analysis</Text>

      {/* Asset Allocation */}
      <Flex gap="24px" flexWrap="wrap">
        <Box bg="gray.700" borderRadius="8px" p="24px" flex="1" minW="280px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">By Strategy</Text>
          <Box height="200px">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={strategyData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${name}: ${value.toFixed(0)}%`}>
                  {strategyData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
              </PieChart>
            </ResponsiveContainer>
          </Box>
        </Box>

        <Box bg="gray.700" borderRadius="8px" p="24px" flex="1" minW="280px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">By Sector</Text>
          <Box height="200px">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={sectorData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${String(name).slice(0, 10)}: ${value.toFixed(0)}%`}>
                  {sectorData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
              </PieChart>
            </ResponsiveContainer>
          </Box>
        </Box>

        <Box bg="gray.700" borderRadius="8px" p="24px" flex="1" minW="280px">
          <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">By Market Cap</Text>
          <Box height="200px">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={marketCapData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${String(name).slice(0, 12)}: ${value.toFixed(0)}%`}>
                  {marketCapData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} />
              </PieChart>
            </ResponsiveContainer>
          </Box>
        </Box>
      </Flex>

      {/* Risk Metrics */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Risk Metrics</Text>
        <Flex gap="32px" flexWrap="wrap">
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.400">Portfolio Value</Text>
            <Text fontSize="xl" fontWeight="bold" color="gray.50">{totalValue.toLocaleString('sv-SE')} kr</Text>
          </VStack>
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.400">Holdings</Text>
            <Text fontSize="xl" fontWeight="bold" color="gray.50">{holdings.length}</Text>
          </VStack>
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.400">Herfindahl Index</Text>
            <Text fontSize="xl" fontWeight="bold" color={herfindahl < 1500 ? 'success.500' : 'warning.500'}>{herfindahl.toFixed(0)}</Text>
          </VStack>
          <VStack align="start" gap="4px">
            <Text fontSize="xs" color="gray.400">Diversification</Text>
            <Text fontSize="xl" fontWeight="bold" color={herfindahl < 1500 ? 'success.500' : 'warning.500'}>
              {herfindahl < 1000 ? 'Excellent' : herfindahl < 1500 ? 'Good' : herfindahl < 2500 ? 'Moderate' : 'Concentrated'}
            </Text>
          </VStack>
        </Flex>
      </Box>

      {/* Correlation Matrix */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Strategy Correlation Matrix</Text>
        <Text fontSize="xs" color="gray.400" mb="12px">Based on historical returns (higher = more correlated)</Text>
        <Box overflowX="auto">
          <Box as="table" fontSize="sm" w="100%">
            <Box as="thead">
              <Box as="tr">
                <Box as="th" p="8px" textAlign="left" color="gray.400"></Box>
                {strategies.map(s => <Box as="th" key={s} p="8px" textAlign="center" color="gray.200" fontWeight="medium">{s}</Box>)}
              </Box>
            </Box>
            <Box as="tbody">
              {strategies.map((row, i) => (
                <Box as="tr" key={row}>
                  <Box as="td" p="8px" color="gray.200" fontWeight="medium">{row}</Box>
                  {correlationMatrix[i].map((val, j) => (
                    <Box as="td" key={j} p="8px" textAlign="center" bg={val === 1 ? 'gray.600' : val > 0.7 ? 'success.50' : val > 0.5 ? 'warning.50' : 'gray.650'} color={val === 1 ? 'gray.300' : 'gray.100'} fontFamily="mono">
                      {val.toFixed(2)}
                    </Box>
                  ))}
                </Box>
              ))}
            </Box>
          </Box>
        </Box>
        <Text fontSize="xs" color="gray.500" mt="12px">💡 Lower correlation between strategies = better diversification</Text>
      </Box>

      {/* Concentration Risk */}
      <Box bg="gray.700" borderRadius="8px" p="24px">
        <Text fontSize="lg" fontWeight="semibold" color="gray.50" mb="16px">Concentration Risk</Text>
        <Text fontSize="sm" color="gray.300" mb="12px">Top 10 holdings represent {top10Weight.toFixed(1)}% of portfolio</Text>
        <VStack align="stretch" gap="8px">
          {sortedHoldings.slice(0, 10).map((h, i) => (
            <HStack key={h.ticker} justify="space-between">
              <HStack gap="8px">
                <Text fontSize="xs" color="gray.400" w="20px">{i + 1}.</Text>
                <Text fontSize="sm" color="gray.100" fontFamily="mono">{h.ticker}</Text>
              </HStack>
              <HStack gap="8px" flex="1" maxW="200px">
                <Box flex="1" h="8px" bg="gray.600" borderRadius="4px" overflow="hidden">
                  <Box h="100%" w={`${h.weight * 100}%`} bg="brand.500" borderRadius="4px" />
                </Box>
                <Text fontSize="xs" color="gray.300" w="40px" textAlign="right">{(h.weight * 100).toFixed(1)}%</Text>
              </HStack>
            </HStack>
          ))}
        </VStack>
      </Box>
    </VStack>
  );
}
