import { Box, Text, HStack } from '@chakra-ui/react';
import { useState } from 'react';

const TOOLTIPS: Record<string, { title: string; content: string }> = {
  momentum: {
    title: 'Vad är Momentum?',
    content: 'Momentum mäter hur mycket en aktie stigit senaste 3, 6 och 12 månaderna. Aktier som gått bra tenderar fortsätta gå bra på kort sikt.'
  },
  rank: {
    title: 'Vad betyder rank?',
    content: 'Rank 1-10 = Köp, 11-20 = Behåll, >20 = Sälj. Rankningen baseras på sammansatt momentum (snitt av 3m, 6m, 12m avkastning).'
  },
  rebalance: {
    title: 'Varför ombalansera?',
    content: 'Kvartalsvis ombalansering (mars, juni, sep, dec) håller portföljen i linje med strategin. Sälj aktier som fallit ur topp 20, köp nya topp 10.'
  },
  drift: {
    title: 'Vad är drift?',
    content: 'Drift visar hur mycket portföljen avviker från målvikterna (10% per aktie). Hög drift (>20%) = dags att ombalansera.'
  },
  costs: {
    title: 'Transaktionskostnader',
    content: 'Courtage (Avanza): 0.069% min 1kr. Spread: ~0.3% för nordiska aktier. Undvik onödig handel för att spara avgifter.'
  },
  marketCap: {
    title: 'Börsvärde',
    content: 'Strategin kräver minst 2 miljarder SEK börsvärde för att undvika illikvida småbolag med hög spread.'
  },
};

interface InfoTooltipProps {
  id: keyof typeof TOOLTIPS;
  children?: React.ReactNode;
}

export function InfoTooltip({ id, children }: InfoTooltipProps) {
  const [show, setShow] = useState(false);
  const tip = TOOLTIPS[id];
  if (!tip) return <>{children}</>;

  return (
    <Box position="relative" display="inline-block">
      <HStack
        gap="4px"
        cursor="help"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow(!show)}
      >
        {children}
        <Text color="blue.400" fontSize="xs">ⓘ</Text>
      </HStack>
      {show && (
        <Box
          position="absolute"
          bottom="100%"
          left="50%"
          transform="translateX(-50%)"
          mb="8px"
          p="12px"
          bg="gray.800"
          borderRadius="8px"
          borderWidth="1px"
          borderColor="blue.500"
          boxShadow="lg"
          zIndex={100}
          minW="240px"
          maxW="300px"
        >
          <Text fontSize="sm" fontWeight="semibold" color="blue.400" mb="4px">{tip.title}</Text>
          <Text fontSize="xs" color="fg.muted">{tip.content}</Text>
          <Box
            position="absolute"
            bottom="-6px"
            left="50%"
            transform="translateX(-50%)"
            w="0"
            h="0"
            borderLeft="6px solid transparent"
            borderRight="6px solid transparent"
            borderTop="6px solid"
            borderTopColor="blue.500"
          />
        </Box>
      )}
    </Box>
  );
}

export function InfoIcon({ id }: { id: keyof typeof TOOLTIPS }) {
  return <InfoTooltip id={id} />;
}
