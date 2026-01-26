import { useState, useEffect, useRef } from 'react';
import { Box, Text, Button, VStack, HStack, Input, Textarea } from '@chakra-ui/react';
import { api, type AllocationResponse, type AllocationStock, type RebalanceResponse } from '../api/client';
import { useLockInPortfolio } from './PortfolioTracker';

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
  const [shareAdjustments, setShareAdjustments] = useState<Record<string, number>>({});
  const [lockedIn, setLockedIn] = useState(false);
  const { lockIn } = useLockInPortfolio();
  const hasCalculated = useRef(false);

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
    setShareAdjustments({});
    setLockedIn(false);

    try {
      if (mode === 'fresh') {
        const numAmount = parseFloat(amount);
        if (isNaN(numAmount) || numAmount <= 0) {
          setError('Ange ett giltigt belopp');
          return;
        }
        const res = await api.calculateAllocation(numAmount, Array.from(excluded), Array.from(forceInclude));
        setResult(res);
        hasCalculated.current = true;
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
      const newForce = new Set(forceInclude);
      newForce.has(ticker) ? newForce.delete(ticker) : newForce.add(ticker);
      setForceInclude(newForce);
    } else {
      const newExcluded = new Set(excluded);
      newExcluded.has(ticker) ? newExcluded.delete(ticker) : newExcluded.add(ticker);
      setExcluded(newExcluded);
    }
  };

  // Auto-recalculate when exclusions change (after initial calculation)
  useEffect(() => {
    if (hasCalculated.current && mode === 'fresh' && result) {
      const numAmount = parseFloat(amount);
      if (!isNaN(numAmount) && numAmount > 0) {
        setLoading(true);
        api.calculateAllocation(numAmount, Array.from(excluded), Array.from(forceInclude))
          .then(res => { setResult(res); setShareAdjustments({}); })
          .catch(() => {})
          .finally(() => setLoading(false));
      }
    }
  }, [excluded, forceInclude]);

  const adjustShares = (ticker: string, delta: number) => {
    setShareAdjustments(prev => {
      const current = prev[ticker] || 0;
      const newVal = current + delta;
      return { ...prev, [ticker]: newVal };
    });
  };

  const getAdjustedAllocation = (a: AllocationStock) => {
    const adj = shareAdjustments[a.ticker] || 0;
    const shares = Math.max(0, a.shares + adj);
    const amount = shares * a.price;
    const investmentAmount = result?.investment_amount || 1;
    const weight = (amount / investmentAmount) * 100;
    return { shares, amount, weight };
  };

  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(v) + ' kr';
  const formatPrice = (priceSek: number, currency: string = 'SEK', priceLocal?: number | null) => {
    if (currency === 'SEK' || !priceLocal) {
      return new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(priceSek) + ' kr';
    }
    // Show local price with SEK equivalent
    const localFormatted = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(priceLocal);
    const sekFormatted = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(priceSek);
    return `${localFormatted} ${currency} (≈${sekFormatted} kr)`;
  };

  const copyToClipboard = () => {
    let text = '';
    if (result) {
      text = result.allocations.filter(a => a.included || (shareAdjustments[a.ticker] || 0) > 0)
        .map(a => { const adj = getAdjustedAllocation(a); return `${a.ticker}\t${adj.shares}\t${formatSEK(adj.amount)}`; }).join('\n');
    } else if (rebalanceResult) {
      const lines = [];
      if (rebalanceResult.sell.length) lines.push('SÄLJ:', ...rebalanceResult.sell.map(s => `${s.ticker}\t${s.shares}`));
      if (rebalanceResult.buy.length) lines.push('KÖP:', ...rebalanceResult.buy.map(b => `${b.ticker}\t${b.shares}`));
      text = lines.join('\n');
    }
    navigator.clipboard.writeText(text);
  };

  // Calculate adjusted totals
  const getAdjustedSummary = () => {
    if (!result) return null;
    let total = 0;
    result.allocations.forEach(a => {
      if (a.included || (shareAdjustments[a.ticker] || 0) > 0) {
        const { amount } = getAdjustedAllocation(a);
        total += amount;
      }
    });
    const remaining = result.investment_amount - total;
    return { total, remaining, utilization: (total / result.investment_amount) * 100 };
  };

  return (
    <Box bg="bg.subtle" borderColor="border" borderWidth="1px" borderRadius="lg" p="20px">
      <Text fontSize="lg" fontWeight="semibold" mb="16px">Portföljallokering</Text>
      
      {/* Mode toggle */}
      <HStack gap="8px" mb="16px">
        <Button size="sm" variant={mode === 'fresh' ? 'solid' : 'outline'} colorPalette="blue" onClick={() => setMode('fresh')}>
          Ny portfölj
        </Button>
        <Button size="sm" variant={mode === 'banding' ? 'solid' : 'outline'} colorPalette="blue" onClick={() => setMode('banding')}>
          Ombalansering
        </Button>
      </HStack>

      {mode === 'fresh' ? (
        <HStack gap="12px" mb="16px">
          <Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Belopp" width="200px" bg="bg" />
          <Text color="fg.muted">SEK</Text>
          <Button onClick={calculate} loading={loading} colorPalette="blue" size="sm">Beräkna</Button>
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
            <Button onClick={calculate} loading={loading} colorPalette="blue" size="sm">Beräkna</Button>
          </HStack>
        </VStack>
      )}

      {error && <Text color="red.400" mb="12px">{error}</Text>}

      {/* Fresh mode result */}
      {result && (
        <VStack align="stretch" gap="16px">
          {(() => {
            const adjSummary = getAdjustedSummary();
            const hasAdj = Object.keys(shareAdjustments).length > 0;
            const isOverspent = hasAdj && (adjSummary?.remaining || 0) < 0;
            return (
            <>
          <HStack gap="24px" flexWrap="wrap">
            <Box><Text fontSize="xs" color="fg.muted">Investerat</Text><Text fontWeight="semibold" color={isOverspent ? 'red.400' : hasAdj ? 'blue.400' : undefined}>{formatSEK(adjSummary?.total || result.summary.total_invested)}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Kvar</Text><Text fontWeight="semibold" color={isOverspent ? 'red.400' : hasAdj ? 'blue.400' : undefined}>{formatSEK(adjSummary?.remaining ?? result.summary.cash_remaining)}</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Utnyttjande</Text><Text fontWeight="semibold" color={isOverspent ? 'red.400' : undefined}>{(adjSummary?.utilization || result.summary.utilization).toFixed(1)}%</Text></Box>
            <Box><Text fontSize="xs" color="fg.muted">Max avvikelse</Text><Text fontWeight="semibold" color={result.summary.max_deviation > 5 ? 'red.400' : result.summary.max_deviation > 2 ? 'yellow.400' : 'green.400'}>{result.summary.max_deviation}%</Text></Box>
            {result.summary.commission_start && <Box><Text fontSize="xs" color="fg.muted">Courtage (Avanza)</Text><Text fontWeight="semibold" fontSize="xs">{result.summary.commission_start} kr <Text as="span" color="fg.muted">(Start)</Text></Text><Text fontSize="xs" color="fg.muted">{result.summary.commission_mini} kr (Mini) · {result.summary.commission_small} kr (Small)</Text></Box>}
            <Button size="xs" variant="outline" colorPalette="gray" onClick={copyToClipboard}>📋 Kopiera</Button>
            <Button size="xs" variant={lockedIn ? 'solid' : 'outline'} colorPalette={lockedIn ? 'green' : 'blue'} onClick={async () => {
              const allocations = result.allocations.filter(a => a.included || (shareAdjustments[a.ticker] || 0) > 0).map(a => ({
                ticker: a.ticker,
                shares: shareAdjustments[a.ticker] ?? a.shares,
                price: a.price,
                rank: a.rank
              }));
              await lockIn(allocations);
              setLockedIn(true);
            }}>{lockedIn ? '✓ Inlåst' : '🔒 Lås in portfölj'}</Button>
            {hasAdj && <Button size="xs" variant="outline" colorPalette="gray" onClick={() => setShareAdjustments({})}>Återställ</Button>}
          </HStack>
          {isOverspent && (
            <Box bg="red.900/30" borderColor="red.500" borderWidth="1px" borderRadius="md" p="8px">
              <Text fontSize="sm" color="red.400" fontWeight="medium">⚠️ Överskrider budget med {formatSEK(Math.abs(adjSummary?.remaining || 0))}</Text>
            </Box>
          )}
          {result.optimal_amounts && result.optimal_amounts.length > 0 && result.summary.max_deviation > 1 && (
            <Box bg="green.900/20" borderColor="green.500" borderWidth="1px" borderRadius="md" p="8px">
              <Text fontSize="xs" color="green.400" fontWeight="medium" mb="4px">Optimala belopp för jämnare fördelning:</Text>
              <HStack gap="8px" flexWrap="wrap">
                {result.optimal_amounts.map((opt: {amount: number; max_deviation: number}) => (
                  <Button key={opt.amount} size="xs" variant="outline" colorPalette="green" onClick={() => { setAmount(String(opt.amount)); setShareAdjustments({}); }}>
                    {formatSEK(opt.amount)} ({opt.max_deviation}%)
                  </Button>
                ))}
              </HStack>
            </Box>
          )}
            </>
            );
          })()}

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
                  <Box as="th" textAlign="center" py="8px" px="4px" color="fg.muted">Antal</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Belopp</Box>
                  <Box as="th" textAlign="right" py="8px" px="4px" color="fg.muted">Vikt</Box>
                  <Box as="th" textAlign="center" py="8px" px="4px" color="fg.muted">Inkl.</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {result.allocations.map((a: AllocationStock) => {
                  const adj = getAdjustedAllocation(a);
                  const deviation = adj.weight - a.target_weight;
                  const isExcluded = excluded.has(a.ticker);
                  const hasAdjustment = (shareAdjustments[a.ticker] || 0) !== 0;
                  
                  return (
                  <Box as="tr" key={a.ticker} borderBottom="1px solid" borderColor="border" opacity={a.too_expensive && !forceInclude.has(a.ticker) || isExcluded ? 0.5 : 1}>
                    <Box as="td" py="8px" px="4px">{a.rank}</Box>
                    <Box as="td" py="8px" px="4px"><Text fontWeight="medium">{a.ticker}</Text><Text fontSize="xs" color="fg.muted">{a.name.slice(0, 20)}</Text></Box>
                    <Box as="td" py="8px" px="4px" textAlign="right" fontSize="xs">{formatPrice(a.price, a.currency, a.price_local)}</Box>
                    <Box as="td" py="6px" px="2px" textAlign="center">
                      <HStack gap="2px" justify="center">
                        <Button size="xs" variant="ghost" onClick={() => adjustShares(a.ticker, -1)} disabled={adj.shares <= 0}>−</Button>
                        <Text fontWeight="semibold" minW="30px" textAlign="center" color={hasAdjustment ? 'blue.400' : undefined}>{adj.shares}</Text>
                        <Button size="xs" variant="ghost" onClick={() => adjustShares(a.ticker, 1)}>+</Button>
                      </HStack>
                    </Box>
                    <Box as="td" py="8px" px="4px" textAlign="right">{formatSEK(adj.amount)}</Box>
                    <Box as="td" py="8px" px="4px" textAlign="right">
                      <Text color={Math.abs(deviation) < 2 ? 'green.400' : Math.abs(deviation) < 5 ? 'yellow.400' : 'red.400'}>
                        {adj.weight.toFixed(1)}%
                        {Math.abs(deviation) >= 5 && <Text as="span" fontSize="xs"> ⚠️</Text>}
                      </Text>
                    </Box>
                    <Box as="td" py="8px" px="4px" textAlign="center">
                      {a.too_expensive ? (
                        <Button 
                          size="xs" 
                          variant={forceInclude.has(a.ticker) ? 'solid' : 'outline'} 
                          colorPalette="orange"
                          onClick={() => toggleStock(a.ticker, true)}
                          title="Klicka för att köpa 1 aktie ändå"
                        >
                          {forceInclude.has(a.ticker) ? '1st' : '⚠️'}
                        </Button>
                      ) : isExcluded ? (
                        <Button size="xs" variant="outline" colorPalette="gray" onClick={() => toggleStock(a.ticker, false)}>
                          ✗
                        </Button>
                      ) : (
                        <HStack gap="1px" justify="center">
                          <Text color="green.400" fontWeight="bold">✓</Text>
                          <Button size="xs" variant="ghost" colorPalette="red" onClick={() => toggleStock(a.ticker, false)} title="Exkludera">
                            ✕
                          </Button>
                        </HStack>
                      )}
                    </Box>
                  </Box>
                  );
                })}
              </Box>
            </Box>
          </Box>
          
          {/* Candidates (rank 11-20) - always visible, shadowed */}
          {result.substitutes && result.substitutes.length > 0 && (
            <Box 
              bg="bg" 
              borderRadius="md" 
              p="12px" 
              borderWidth="1px" 
              borderColor="border"
              opacity={0.6}
              _hover={{ opacity: 0.9 }}
              transition="opacity 0.2s"
            >
              <Text fontSize="xs" color="fg.muted" fontWeight="medium" mb="8px">
                📋 Kandidater (rank 11-{10 + result.substitutes.length}) — exkludera ovan för att byta in
              </Text>
              <HStack gap="8px" flexWrap="wrap">
                {result.substitutes.map((s: {rank: number; ticker: string; name: string; price: number}) => (
                  <Box 
                    key={s.ticker} 
                    px="8px" 
                    py="4px" 
                    bg="bg.subtle" 
                    borderRadius="4px"
                    borderWidth="1px"
                    borderColor="border"
                    fontSize="xs"
                  >
                    <Text fontWeight="medium" display="inline">#{s.rank} {s.ticker}</Text>
                    <Text color="fg.muted" display="inline" ml="4px">{formatSEK(s.price)}</Text>
                  </Box>
                ))}
              </HStack>
            </Box>
          )}
          
          {(excluded.size > 0 || forceInclude.size > 0) && <Button size="sm" variant="outline" colorPalette="gray" onClick={() => { setExcluded(new Set()); setForceInclude(new Set()); }}>Återställ alla</Button>}
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
            <Button size="xs" variant="outline" colorPalette="gray" onClick={copyToClipboard}>📋 Kopiera</Button>
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
