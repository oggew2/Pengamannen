import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Box, Text, VStack, HStack, Flex, Skeleton } from '@chakra-ui/react';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';

interface DividendEvent {
  ticker: string;
  ex_date: string;
  payment_date: string;
  amount: number;
  currency: string;
}

interface Holding {
  ticker: string;
  shares: number;
}

export default function DividendCalendarPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('myHoldings');
    if (saved) setHoldings(JSON.parse(saved));
  }, []);

  const { data: dividends = [], isLoading, isError } = useQuery({
    queryKey: queryKeys.dividends.upcoming(90),
    queryFn: () => api.get<DividendEvent[]>('/dividends/upcoming?days_ahead=90'),
  });

  const holdingTickers = new Set(holdings.map(h => h.ticker));
  const myDividends = dividends.filter(d => holdingTickers.has(d.ticker));
  const otherDividends = dividends.filter(d => !holdingTickers.has(d.ticker));
  const getShares = (ticker: string) => holdings.find(h => h.ticker === ticker)?.shares || 0;
  const formatSEK = (v: number) => new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(v);

  if (isError) {
    return (
      <VStack gap="24px" align="stretch">
        <Box bg="error.subtle" borderColor="error.fg" borderWidth="1px" borderRadius="8px" p="16px">
          <Text color="error.fg" fontWeight="semibold">Failed to load dividends</Text>
        </Box>
      </VStack>
    );
  }

  if (isLoading) {
    return (
      <VStack gap="24px" align="stretch">
        <Box>
          <Skeleton height="32px" width="200px" mb="8px" />
          <Skeleton height="20px" width="300px" />
        </Box>
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Skeleton height="24px" width="150px" mb="16px" />
          <VStack gap="12px" align="stretch">
            {[1, 2, 3, 4, 5].map(i => (
              <Skeleton key={i} height="40px" />
            ))}
          </VStack>
        </Box>
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Skeleton height="24px" width="200px" mb="16px" />
          <VStack gap="12px" align="stretch">
            {[1, 2, 3, 4, 5].map(i => (
              <Skeleton key={i} height="40px" />
            ))}
          </VStack>
        </Box>
      </VStack>
    );
  }

  return (
    <VStack gap="24px" align="stretch">
      <Box>
        <Text fontSize="2xl" fontWeight="bold" color="fg">Utdelningskalender</Text>
        <Text color="fg.muted" fontSize="sm">Kommande ex-datum (90 dagar)</Text>
      </Box>

      {myDividends.length > 0 && (
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Mina innehav</Text>
          <Box overflowX="auto">
            <Box as="table" width="100%" fontSize="sm">
              <Box as="thead">
                <Box as="tr" borderBottom="1px solid" borderColor="border">
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Ticker</Box>
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Ex-datum</Box>
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Utbetalning</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Belopp</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Antal</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Förväntat</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {myDividends.map((d, i) => {
                  const shares = getShares(d.ticker);
                  return (
                    <Box as="tr" key={i} borderBottom="1px solid" borderColor="border" _hover={{ bg: 'bg.muted' }}>
                      <Box as="td" p="12px"><Text color="fg" fontFamily="mono" fontWeight="medium">{d.ticker.replace('.ST', '')}</Text></Box>
                      <Box as="td" p="12px"><Text color="fg">{d.ex_date}</Text></Box>
                      <Box as="td" p="12px"><Text color="fg.muted">{d.payment_date || '—'}</Text></Box>
                      <Box as="td" p="12px" textAlign="right"><Text color="fg" fontFamily="mono">{d.amount?.toFixed(2)} {d.currency}</Text></Box>
                      <Box as="td" p="12px" textAlign="right"><Text color="fg.muted">{shares}</Text></Box>
                      <Box as="td" p="12px" textAlign="right"><Text color="success.fg" fontWeight="semibold" fontFamily="mono">{formatSEK(d.amount * shares)} {d.currency}</Text></Box>
                    </Box>
                  );
                })}
              </Box>
            </Box>
          </Box>
          <Flex justify="flex-end" mt="16px" pt="12px" borderTop="1px solid" borderColor="border">
            <HStack gap="8px">
              <Text color="fg.muted" fontSize="sm">Totalt förväntat:</Text>
              <Text color="success.fg" fontWeight="bold" fontSize="lg" fontFamily="mono">
                {formatSEK(myDividends.reduce((sum, d) => sum + d.amount * getShares(d.ticker), 0))} SEK
              </Text>
            </HStack>
          </Flex>
        </Box>
      )}

      {holdings.length === 0 && (
        <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center" borderColor="border" borderWidth="1px">
          <Text color="fg.muted">
            Lägg till innehav i <Link to="/rebalancing" style={{ color: 'var(--chakra-colors-brand-fg)' }}>Min Strategi</Link> för att se din utdelningskalender
          </Text>
        </Box>
      )}

      {otherDividends.length > 0 && (
        <Box bg="bg.subtle" borderRadius="8px" p="24px" borderColor="border" borderWidth="1px">
          <Text fontSize="lg" fontWeight="semibold" color="fg" mb="16px">Alla kommande utdelningar</Text>
          <Box overflowX="auto">
            <Box as="table" width="100%" fontSize="sm">
              <Box as="thead">
                <Box as="tr" borderBottom="1px solid" borderColor="border">
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Ticker</Box>
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Ex-datum</Box>
                  <Box as="th" p="12px" textAlign="left" color="fg.muted" fontWeight="medium">Utbetalning</Box>
                  <Box as="th" p="12px" textAlign="right" color="fg.muted" fontWeight="medium">Belopp</Box>
                </Box>
              </Box>
              <Box as="tbody">
                {otherDividends.slice(0, 20).map((d, i) => (
                  <Box as="tr" key={i} borderBottom="1px solid" borderColor="border" _hover={{ bg: 'bg.muted' }}>
                    <Box as="td" p="12px"><Text color="fg" fontFamily="mono">{d.ticker.replace('.ST', '')}</Text></Box>
                    <Box as="td" p="12px"><Text color="fg">{d.ex_date}</Text></Box>
                    <Box as="td" p="12px"><Text color="fg.muted">{d.payment_date || '—'}</Text></Box>
                    <Box as="td" p="12px" textAlign="right"><Text color="fg" fontFamily="mono">{d.amount?.toFixed(2)} {d.currency}</Text></Box>
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </Box>
      )}

      {dividends.length === 0 && !isLoading && (
        <Box bg="bg.subtle" borderRadius="8px" p="48px" textAlign="center" borderColor="border" borderWidth="1px">
          <Text color="fg.muted">Inga kommande utdelningar hittades</Text>
        </Box>
      )}
    </VStack>
  );
}
