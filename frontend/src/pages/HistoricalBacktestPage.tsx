import { useState } from 'react';
import { Box, Text, VStack, HStack, Flex, Button, Input, Skeleton, SimpleGrid, NativeSelect } from '@chakra-ui/react';
import { BacktestChart } from '../components/BacktestChart';

interface YearlyReturn {
  year: number;
  return: number;
}

interface HistoricalResult {
  strategy_name: string;
  start_date: string;
  end_date: string;
  years: number;
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  cagr_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  best_year: YearlyReturn;
  worst_year: YearlyReturn;
  rebalance_count: number;
  yearly_returns: YearlyReturn[];
  equity_curve: { date: string; value: number }[];
  data_source: string;
}

interface CompareResult {
  period: string;
  summary: { strategy: string; cagr: number; sharpe: number; max_dd: number; win_rate: number }[];
}

const STRATEGIES = [
  { value: 'sammansatt_momentum', label: 'Sammansatt Momentum' },
  { value: 'trendande_varde', label: 'Trendande Värde' },
  { value: 'trendande_utdelning', label: 'Trendande Utdelning' },
  { value: 'trendande_kvalitet', label: 'Trendande Kvalitet' },
];

export function HistoricalBacktestPage() {
  const [strategy, setStrategy] = useState('sammansatt_momentum');
  const [startYear, setStartYear] = useState(2005);
  const [endYear, setEndYear] = useState(2024);
  const [result, setResult] = useState<HistoricalResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runBacktest = async () => {
    setLoading(true);
    setError('');
    setCompareResult(null);
    try {
      const res = await fetch(`/v1/backtesting/historical?strategy_name=${strategy}&start_year=${startYear}&end_year=${endYear}&use_synthetic=true`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Backtest failed');
      setResult(await res.json());
    } catch {
      setError('Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  const compareAll = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch(`/v1/backtesting/historical/compare?start_year=${startYear}&end_year=${endYear}`, {
        method: 'POST',
        credentials: 'include'
      });
      if (!res.ok) throw new Error('Compare failed');
      setCompareResult(await res.json());
    } catch {
      setError('Failed to compare strategies');
    } finally {
      setLoading(false);
    }
  };

  return (
    <VStack gap="24px" align="stretch">
      <Box>
        <Text fontSize="2xl" fontWeight="bold" color="fg">Historisk Backtest (20+ år)</Text>
        <Text color="fg.muted" fontSize="sm">Testa strategier på historisk data</Text>
      </Box>

      <SimpleGrid columns={{ base: 1, md: 2 }} gap="24px">
        {/* Configuration */}
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Konfiguration</Text>
          
          <VStack gap="16px" align="stretch">
            <Box>
              <Text fontSize="sm" color="fg.muted" mb="4px">Strategi</Text>
              <NativeSelect.Root w="100%">
                <NativeSelect.Field value={strategy} onChange={e => setStrategy(e.target.value)} bg="bg.muted" borderColor="border" color="fg">
                  {STRATEGIES.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </NativeSelect.Field>
                <NativeSelect.Indicator />
              </NativeSelect.Root>
            </Box>

            <HStack gap="12px">
              <Box flex="1">
                <Text fontSize="sm" color="fg.muted" mb="4px">Startår</Text>
                <Input type="number" min={1990} max={2023} value={startYear} onChange={e => setStartYear(Number(e.target.value))} bg="bg.muted" borderColor="border" size="sm" />
              </Box>
              <Box flex="1">
                <Text fontSize="sm" color="fg.muted" mb="4px">Slutår</Text>
                <Input type="number" min={2000} max={2024} value={endYear} onChange={e => setEndYear(Number(e.target.value))} bg="bg.muted" borderColor="border" size="sm" />
              </Box>
            </HStack>

            <VStack gap="8px" align="stretch">
              <Button colorPalette="blue" onClick={runBacktest} loading={loading} disabled={loading}>
                Kör enskild strategi
              </Button>
              <Button variant="outline" borderColor="brand.fg" color="brand.fg" onClick={compareAll} loading={loading} disabled={loading}>
                Jämför alla strategier
              </Button>
            </VStack>

            {error && <Text color="error.fg" fontSize="sm">{error}</Text>}
          </VStack>
        </Box>

        {/* Results */}
        {loading && !result && !compareResult && (
          <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
            <Skeleton height="24px" width="200px" mb="16px" />
            <VStack gap="12px" align="stretch">
              <Skeleton height="60px" />
              <Skeleton height="60px" />
              <Skeleton height="60px" />
            </VStack>
          </Box>
        )}

        {result && (
          <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
            <Text fontSize="lg" fontWeight="semibold" color="fg" mb="4px">{result.strategy_name}</Text>
            <Text fontSize="sm" color="fg.muted" mb="4px">{result.years} år ({result.start_date} till {result.end_date})</Text>
            <Text fontSize="xs" color="fg.subtle" mb="16px">Data: {result.data_source}</Text>
            
            <SimpleGrid columns={3} gap="12px" mb="16px">
              <Box p="12px" bg="bg.muted" borderRadius="6px" textAlign="center">
                <Text fontSize="xl" fontWeight="bold" color={result.cagr_pct >= 0 ? 'success.fg' : 'error.fg'} fontFamily="mono">
                  {result.cagr_pct.toFixed(1)}%
                </Text>
                <Text fontSize="xs" color="fg.muted">CAGR</Text>
              </Box>
              <Box p="12px" bg="bg.muted" borderRadius="6px" textAlign="center">
                <Text fontSize="xl" fontWeight="bold" color="fg" fontFamily="mono">{result.sharpe_ratio.toFixed(2)}</Text>
                <Text fontSize="xs" color="fg.muted">Sharpe</Text>
              </Box>
              <Box p="12px" bg="bg.muted" borderRadius="6px" textAlign="center">
                <Text fontSize="xl" fontWeight="bold" color="error.fg" fontFamily="mono">{result.max_drawdown_pct.toFixed(1)}%</Text>
                <Text fontSize="xs" color="fg.muted">Max DD</Text>
              </Box>
            </SimpleGrid>

            <VStack gap="8px" align="stretch" fontSize="sm">
              <Flex justify="space-between"><Text color="fg.muted">Slutvärde:</Text><Text color="fg" fontWeight="semibold">${result.final_value.toLocaleString()}</Text></Flex>
              <Flex justify="space-between"><Text color="fg.muted">Total avkastning:</Text><Text color="fg" fontWeight="semibold">{result.total_return_pct.toFixed(1)}%</Text></Flex>
              <Flex justify="space-between"><Text color="fg.muted">Vinstfrekvens:</Text><Text color="fg" fontWeight="semibold">{result.win_rate_pct.toFixed(0)}% positiva år</Text></Flex>
              <Flex justify="space-between"><Text color="fg.muted">Bästa år:</Text><Text color="success.fg" fontWeight="semibold">{result.best_year.year} ({result.best_year.return.toFixed(1)}%)</Text></Flex>
              <Flex justify="space-between"><Text color="fg.muted">Sämsta år:</Text><Text color="error.fg" fontWeight="semibold">{result.worst_year.year} ({result.worst_year.return.toFixed(1)}%)</Text></Flex>
              <Flex justify="space-between"><Text color="fg.muted">Ombalanseringar:</Text><Text color="fg" fontWeight="semibold">{result.rebalance_count}</Text></Flex>
            </VStack>
          </Box>
        )}
      </SimpleGrid>

      {/* Equity Curve */}
      {result?.equity_curve && (
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Värdeutveckling</Text>
          <BacktestChart values={result.equity_curve.map(e => e.value)} labels={[result.start_date, result.end_date]} />
        </Box>
      )}

      {/* Yearly Returns */}
      {result?.yearly_returns && (
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Årsavkastning</Text>
          <Flex gap="8px" flexWrap="wrap">
            {result.yearly_returns.map(yr => (
              <Box key={yr.year} p="8px" borderRadius="4px" bg={yr.return >= 0 ? 'success.subtle' : 'error.subtle'} textAlign="center" minW="60px">
                <Text fontSize="xs" fontWeight="semibold" color={yr.return >= 0 ? 'success.fg' : 'error.fg'}>{yr.year}</Text>
                <Text fontSize="xs" color={yr.return >= 0 ? 'success.fg' : 'error.fg'}>{yr.return.toFixed(1)}%</Text>
              </Box>
            ))}
          </Flex>
        </Box>
      )}

      {/* Strategy Comparison */}
      {compareResult && (
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="4px">Strategijämförelse</Text>
          <Text fontSize="sm" color="fg.muted" mb="16px">{compareResult.period}</Text>
          
          <Box overflowX="auto">
            <Box as="table" width="100%" fontSize="sm">
              <Box as="thead">
                <Box as="tr" borderBottom="1px solid" borderColor="border">
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Rank</Box>
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Strategi</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">CAGR</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Sharpe</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Max DD</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Vinstfrekvens</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {compareResult.summary.map((s, i) => (
                  <Box as="tr" key={s.strategy} borderBottom="1px solid" borderColor="border" _hover={{ bg: 'bg.muted' }}>
                    <Box as="td" p="12px"><Text color="fg.muted">{i + 1}</Text></Box>
                    <Box as="td" p="12px"><Text color="fg" fontWeight="medium">{s.strategy}</Text></Box>
                    <Box as="td" p="12px" textAlign="right"><Text color={s.cagr >= 0 ? 'success.fg' : 'error.fg'} fontFamily="mono">{s.cagr.toFixed(1)}%</Text></Box>
                    <Box as="td" p="12px" textAlign="right"><Text color="fg" fontFamily="mono">{s.sharpe.toFixed(2)}</Text></Box>
                    <Box as="td" p="12px" textAlign="right"><Text color="error.fg" fontFamily="mono">{s.max_dd.toFixed(1)}%</Text></Box>
                    <Box as="td" p="12px" textAlign="right"><Text color="fg" fontFamily="mono">{s.win_rate.toFixed(0)}%</Text></Box>
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
