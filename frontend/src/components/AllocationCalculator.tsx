import { useState } from 'react';
import { Box, Text, Button, VStack, HStack, Input, Textarea } from '@chakra-ui/react';
import { api, type AllocationResponse, type AllocationStock, type RebalanceResponse } from '../api/client';

type Mode = 'fresh' | 'banding';

export function AllocationCalculator() {
  const [mode, setMode] = useState<Mode>('fresh');
  const [amount, setAmount] = useState<string>('100000');
  const [holdingsText, setHoldingsText] = useState<string>('');
  const [result, setResult] = useState<AllocationResponse | null>(null);
  const [rebalanceResult, setRebalanceResult] = useState<RebalanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [excluded, setExcluded] = useState<Set<string>>(new Set());
  const [forceInclude, setForceInclude] = useState<Set<string>>(new Set());

  const parseHoldings = (text: string): { ticker: string; shares: number }[] => {
    return text.split('\n')
      .map(line => line.trim())
      .filter(line => line)
      .map(line => {
        const parts = line.split(/[\s,;]+/);
        return { ticker: parts[0]?.toUpperCase() || '', shares: parseInt(parts[1]) || 0 };
      })
      .filter(h => h.ticker && h.shares > 0);
  };

  const calculate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setRebalanceResult(null);

    try {
      if (mode === 'fresh') {
        const numAmount = parseFloat(amount);
        if (isNaN(numAmount) || numAmount <= 0) {
          setError('Ange ett giltigt belopp');
          return;
        }
        const res = await api.calculateAllocation(numAmount, Array.from(excluded), Array.from(forceInclude));
        setResult(res);
      } else {
        const holdings = parseHoldings(holdingsText);
        const newInvestment = parseFloat(amount) || 0;
        if (holdings.length === 0 && newInvestment <= 0) {
          setError('Ange innehav eller nytt kapital');
          return;
        }
        const res = await api.calculateRebalance(holdings, newInvestment);
        setRebalanceResult(res);
      }
    } catch {
      setError('Kunde inte beräkna');
    } finally {
      setLoading(false);
    }
  };

  const toggleStock = (ticker: string, tooExpensive: boolean) => {
    if (tooExpensive) {
      // Toggle force include for expensive stocks
      const newForce = new Set(forceInclude);
      newForce.has(ticker) ? newForce.delete(ticker) : newForce.add(ticker);
      setForceInclude(newForce);
    } else {
      // Toggle exclude for normal stocks
      const newExcluded = new Set(excluded);
      newExcluded.has(ticker) ? newExcluded.delete(ticker) : newExcluded.add(ticker);
      setExcluded(newExcluded);
    }
  };

  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', maximumFractionDigits: 0 }).format(v);

  return (
    <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
      <Text fontSize="lg" fontWeight="semibold" mb="16px">Portföljallokering</Text>
      
      {/* Mode toggle */}
      <HStack gap="8px" mb="16px">
        <Button size="sm" variant={mode === 'fresh' ? 'solid' : 'outline'} onClick={() => setMode('fresh')}>
          Ny portfölj
        </Button>
        <Button size="sm" variant={mode === 'banding' ? 'solid' : 'outline'} onClick={() => setMode('banding')}>
          Ombalansering
        </Button>
      </HStack>

      {mode === 'fresh' ? (
        <HStack gap="12px" mb="16px">
          <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Belopp" width="200px" bg="bg" />
          <Text color="fg.muted">SEK</Text>
          <Button onClick={calculate} loading={loading} colorScheme="blue" size="sm">Beräkna</Button>
        </HStack>
      ) : (
        <VStack align="stretch" gap="12px" mb="16px">
          <Box>
            <Text fontSize="sm" color="fg.muted" mb="4px">Nuvarande innehav (TICKER ANTAL per rad)</Text>
            <Textarea
              value={holdingsText}
              onChange={(e) => setHoldingsText(e.target.value)}
              placeholder="BITTI 100&#10;GOMX 50&#10;SANION 75"
              rows={5}
              bg="bg"
              fontFamily="mono"
              fontSize="sm"
            />
          </Box>
          <HStack gap="12px">
            <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Nytt kapital (valfritt)" width="200px" bg="bg" />
            <Text color="fg.muted">SEK</Text>
            <Button onClick={calculate} loading={loading} colorScheme="blue" size="sm">Beräkna</Button>
          </HStack>
        </VStack>
      )}

      {error && <Text color="red.400" mb="12px">{error}</Text>}

      {/* Fresh mode result */}
      {result && (
        <VStack align="stretch" gap="16px">
          <HStack gap="24px" flexWrap="wrap">
            <Box><Text fontSize="xs" color="fg.muted">Investerat</Text><Text fontWeight="semibold">{formatSEK(result.summary.total_invested)}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Kvar</Text><Text fontWeight="semibold">{formatSEK(result.summary.cash_remaining)}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Utnyttjande</Text><Text fontWeight="semibold">{result.summary.utilization}%</Text></Box>
          </HStack>

          {result.warnings.length > 0 && (
            <Box bg="yellow.900/20" borderColor="yellow.500" borderWidth="1px" borderRadius="md" p="12px">
              <Text fontSize="sm" color="yellow.400" fontWeight="medium">Varningar:</Text>
              {result.warnings.slice(0, 3).map((w, i) => <Text key={i} fontSize="xs" color="yellow.300">• {w}</Text>)}
            </Box>
          )}

          <Box overflowX="auto">
            <Box as="table" width="100%" fontSize="sm">
              <Box as="thead">
                <Box as="tr" borderBottom="1px solid" borderColor="border">
                  <Box as="th" textAlign="left" py="8px" px="4px" color="fg.muted">#</Box>
                  <Box as="th" textAlign="left" py="8px" px="4px" color="fg.muted">Aktie</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Pris</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Antal</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Belopp</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Vikt</Box>
                  <Box as="th" textAlign="center" py="8px" px="4px" color="fg.muted">Inkl.</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {result.allocations.map((a: AllocationStock) => (
                  <Box as="tr" key={a.ticker} borderBottom="1px solid" borderColor="border" opacity={a.too_expensive || excluded.has(a.ticker) ? 0.5 : 1}>
                    <Box as="td" py="8px" px="4px">{a.rank}</Box>
                    <Box as="td" py="8px" px="4px"><Text fontWeight="medium">{a.ticker}</Text><Text fontSize="xs" color="fg.muted">{a.name.slice(0, 20)}</Text></Box>
                    <Box as="td" py="8px" px="4px" textAlign="right">{formatSEK(a.price)}</Box>
                    <Box as="td" py="8px" px="4px" textAlign="right" fontWeight="semibold">{a.shares}</Box>
                    <Box as="td" py="8px" px="4px" textAlign="right">{formatSEK(a.actual_amount)}</Box>
                    <Box as="td" py="8px" px="4px" textAlign="right">
                      <Text color={Math.abs(a.deviation) < 1 ? 'green.400' : Math.abs(a.deviation) < 2 ? 'yellow.400' : 'red.400'}>{a.actual_weight}%</Text>
                    </Box>
                    <Box as="td" py="8px" px="4px" textAlign="center">
                      <Button 
                        size="xs" 
                        variant={a.too_expensive ? (forceInclude.has(a.ticker) ? 'solid' : 'outline') : excluded.has(a.ticker) ? 'outline' : 'solid'} 
                        colorScheme={a.too_expensive ? 'orange' : excluded.has(a.ticker) ? 'gray' : 'green'} 
                        onClick={() => toggleStock(a.ticker, a.too_expensive)}
                        title={a.too_expensive ? 'Klicka för att köpa 1 aktie ändå' : 'Klicka för att exkludera'}
                      >
                        {a.too_expensive ? (forceInclude.has(a.ticker) ? '1st' : '⚠️') : excluded.has(a.ticker) ? '✗' : '✓'}
                      </Button>
                    </Box>
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
          {excluded.size > 0 && <Button size="sm" variant="outline" onClick={() => { setExcluded(new Set()); calculate(); }}>Återställ alla</Button>}
        </VStack>
      )}

      {/* Banding mode result */}
      {rebalanceResult && (
        <VStack align="stretch" gap="16px">
          <HStack gap="24px" flexWrap="wrap">
            <Box><Text fontSize="xs" color="fg.muted">Behåll</Text><Text fontWeight="semibold" color="blue.400">{rebalanceResult.summary.stocks_held}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Sälj</Text><Text fontWeight="semibold" color="red.400">{rebalanceResult.summary.stocks_sold}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Köp</Text><Text fontWeight="semibold" color="green.400">{rebalanceResult.summary.stocks_bought}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Portföljvärde</Text><Text fontWeight="semibold">{formatSEK(rebalanceResult.summary.final_portfolio_value)}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Kvar</Text><Text fontWeight="semibold">{formatSEK(rebalanceResult.summary.cash_remaining)}</Text></Box>
          </HStack>

          {/* Sell section */}
          {rebalanceResult.sell.length > 0 && (
            <Box bg="red.900/20" borderColor="red.500" borderWidth="1px" borderRadius="md" p="12px">
              <Text fontSize="sm" color="red.400" fontWeight="medium" mb="8px">SÄLJ ({formatSEK(rebalanceResult.summary.sell_proceeds)})</Text>
              {rebalanceResult.sell.map(s => (
                <HStack key={s.ticker} justify="space-between" fontSize="sm">
                  <Text>{s.ticker} <Text as="span" color="fg.muted">({s.reason === 'below_threshold' ? `rank ${s.rank}` : 'ej i universum'})</Text></Text>
                  <Text>{s.shares} st = {formatSEK(s.value)}</Text>
                </HStack>
              ))}
            </Box>
          )}

          {/* Buy section */}
          {rebalanceResult.buy.length > 0 && (
            <Box bg="green.900/20" borderColor="green.500" borderWidth="1px" borderRadius="md" p="12px">
              <Text fontSize="sm" color="green.400" fontWeight="medium" mb="8px">KÖP ({formatSEK(rebalanceResult.summary.total_cash_used)})</Text>
              {rebalanceResult.buy.map(b => (
                <HStack key={b.ticker} justify="space-between" fontSize="sm">
                  <Text>{b.ticker} <Text as="span" color="fg.muted">(rank {b.rank})</Text></Text>
                  <Text fontWeight="semibold">{b.shares} st = {formatSEK(b.value)}</Text>
                </HStack>
              ))}
            </Box>
          )}

          {/* Final portfolio */}
          <Box>
            <Text fontSize="sm" fontWeight="medium" mb="8px">Slutportfölj ({rebalanceResult.summary.final_stock_count} aktier)</Text>
            <Box overflowX="auto">
              <Box as="table" width="100%" fontSize="sm">
                <Box as="thead">
                  <Box as="tr" borderBottom="1px solid" borderColor="border">
                    <Box as="th" textAlign="left" py="6px" px="4px" color="fg.muted">Rank</Box>
                    <Box as="th" textAlign="left" py="6px" px="4px" color="fg.muted">Aktie</Box>
                    <Box as="th" textAlign="right" py="6px" px="4px" color="fg.muted">Antal</Box>
                    <Box as="th" textAlign="right" py="6px" px="4px" color="fg.muted">Värde</Box>
                    <Box as="th" textAlign="right" py="6px" px="4px" color="fg.muted">Vikt</Box>
                    <Box as="th" textAlign="center" py="6px" px="4px" color="fg.muted">Åtgärd</Box>
                  </Box>
                </Box>
                <Box as="tbody">
                  {rebalanceResult.final_portfolio.map(p => (
                    <Box as="tr" key={p.ticker} borderBottom="1px solid" borderColor="border">
                      <Box as="td" py="6px" px="4px">{p.rank}</Box>
                      <Box as="td" py="6px" px="4px" fontWeight="medium">{p.ticker}</Box>
                      <Box as="td" py="6px" px="4px" textAlign="right">{p.shares}</Box>
                      <Box as="td" py="6px" px="4px" textAlign="right">{formatSEK(p.value)}</Box>
                      <Box as="td" py="6px" px="4px" textAlign="right">{p.weight}%</Box>
                      <Box as="td" py="6px" px="4px" textAlign="center">
                        <Text fontSize="xs" color={p.action === 'BUY' ? 'green.400' : 'blue.400'}>{p.action === 'BUY' ? 'KÖP' : 'BEHÅLL'}</Text>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            </Box>
          </Box>
        </VStack>
      )}
    </Box>
  );
}
