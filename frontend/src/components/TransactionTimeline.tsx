import { Box, VStack, HStack, Text } from '@chakra-ui/react';

interface Transaction {
  date: string;
  type: 'buy' | 'sell';
  ticker: string;
  shares: number;
  price: number;
  currentPrice?: number;
}

interface TransactionTimelineProps {
  transactions: Transaction[];
}

export function TransactionTimeline({ transactions }: TransactionTimelineProps) {
  if (transactions.length === 0) {
    return (
      <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
        <Text fontSize="sm" fontWeight="semibold" mb="8px">📅 Transaktionshistorik</Text>
        <Text fontSize="xs" color="fg.muted">Ingen historik ännu. Importera din portfölj för att börja.</Text>
      </Box>
    );
  }

  return (
    <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
      <Text fontSize="sm" fontWeight="semibold" mb="12px">📅 Transaktionshistorik</Text>
      <VStack gap="0" align="stretch" position="relative">
        {/* Timeline line */}
        <Box position="absolute" left="8px" top="8px" bottom="8px" w="2px" bg="border" />
        
        {transactions.slice(0, 10).map((t, i) => {
          const returnPct = t.currentPrice ? ((t.currentPrice - t.price) / t.price) * 100 : null;
          const isPositive = returnPct && returnPct > 0;
          
          return (
            <HStack key={`${t.ticker}-${t.date}-${i}`} gap="12px" py="8px" position="relative">
              {/* Timeline dot */}
              <Box
                w="16px"
                h="16px"
                borderRadius="full"
                bg={t.type === 'buy' ? 'green.500' : 'red.500'}
                borderWidth="3px"
                borderColor="bg"
                zIndex={1}
                flexShrink={0}
              />
              
              {/* Content */}
              <Box flex="1" bg="bg.subtle" p="8px" borderRadius="6px">
                <HStack justify="space-between" mb="4px">
                  <HStack gap="8px">
                    <Text fontSize="sm" fontWeight="medium">{t.ticker}</Text>
                    <Text fontSize="xs" color={t.type === 'buy' ? 'green.400' : 'red.400'}>
                      {t.type === 'buy' ? 'Köp' : 'Sälj'}
                    </Text>
                  </HStack>
                  <Text fontSize="xs" color="fg.muted">{t.date}</Text>
                </HStack>
                <HStack justify="space-between" fontSize="xs" color="fg.muted">
                  <Text>{t.shares} st × {t.price.toFixed(2)} kr</Text>
                  {returnPct !== null && (
                    <Text color={isPositive ? 'green.400' : 'red.400'}>
                      {isPositive ? '+' : ''}{returnPct.toFixed(1)}% sedan köp
                    </Text>
                  )}
                </HStack>
              </Box>
            </HStack>
          );
        })}
        
        {transactions.length > 10 && (
          <Text fontSize="xs" color="fg.muted" textAlign="center" mt="8px">
            +{transactions.length - 10} fler transaktioner
          </Text>
        )}
      </VStack>
    </Box>
  );
}
