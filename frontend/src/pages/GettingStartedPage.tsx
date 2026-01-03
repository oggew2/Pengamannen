import { Box, Text, VStack, HStack, Flex, SimpleGrid } from '@chakra-ui/react';
import { Link } from 'react-router-dom';
import { StrategyQuiz } from '../components/StrategyQuiz';
import { CostCalculator } from '../components/CostCalculator';

const steps = [
  {
    number: '1',
    title: 'Välj strategier',
    description: 'Välj vilka aktiestrategier du vill investera i. Våra fyra strategier är baserade på beprövade principer: värde, kvalitet, momentum och utdelning.',
    tip: 'Bäst resultat får du genom att investera i alla fyra strategier - det sprider riskerna och ger jämnare avkastning över tid.',
    link: '/strategies/momentum',
    linkText: 'Se strategierna →'
  },
  {
    number: '2',
    title: 'Välj antal aktier',
    description: 'Bestäm hur många aktier du vill ha i varje strategi. Standardrekommendationen är 10 aktier per strategi, vilket ger totalt 40 aktier.',
    tip: 'Med mindre kapital kan du börja med färre aktier (t.ex. 5 per strategi). Det viktiga är att komma igång.',
    link: null,
    linkText: null
  },
  {
    number: '3',
    title: 'Investera systematiskt',
    description: 'Köp de aktier som rankas högst i varje strategi. Använd ett ISK (investeringssparkonto) för skattefördelar. Mellan ombalanseringar kan du öka i befintliga innehav.',
    tip: 'Investera samma belopp i varje aktie (likaviktad portfölj). Med 100 000 kr och 10 aktier blir det 10 000 kr per aktie.',
    link: '/rebalancing',
    linkText: 'Se rebalansering →'
  },
  {
    number: '4',
    title: 'Följ upp kvartalsvis',
    description: 'Momentum-strategin ombalanseras kvartalsvis (mars, juni, september, december). Övriga strategier ombalanseras årligen i mars.',
    tip: 'Sälj aktier som fallit ur listan och köp in de nya. Låt inte känslor styra - följ systemet.',
    link: '/alerts',
    linkText: 'Sätt påminnelser →'
  },
  {
    number: '5',
    title: 'Lev livet',
    description: 'Det stora syftet med systematiskt sparande är att det kräver minimal tid. När du investerat arbetar pengarna åt dig medan du kan fokusera på annat.',
    tip: 'Undvik att kolla portföljen dagligen. Kvartalsvis uppföljning räcker.',
    link: null,
    linkText: null
  }
];

const strategies = [
  { name: 'Sammansatt Momentum', path: '/strategies/momentum', rebalance: 'Kvartalsvis', description: 'Aktier med starkast kursutveckling' },
  { name: 'Trendande Värde', path: '/strategies/value', rebalance: 'Årligen', description: 'Undervärderade aktier med momentum' },
  { name: 'Trendande Utdelning', path: '/strategies/dividend', rebalance: 'Årligen', description: 'Hög direktavkastning med momentum' },
  { name: 'Trendande Kvalitet', path: '/strategies/quality', rebalance: 'Årligen', description: 'Högkvalitativa bolag med momentum' },
];

export default function GettingStartedPage() {
  return (
    <VStack gap="32px" align="stretch">
      <Box>
        <Text fontSize="2xl" fontWeight="bold" color="fg">Kom igång</Text>
        <Text color="fg.subtle" mt="4px">Hitta rätt strategi och förstå kostnaderna</Text>
      </Box>

      {/* Strategy Quiz */}
      <StrategyQuiz />

      {/* Cost Calculator */}
      <CostCalculator />

      {/* Steps */}
      <Box>
        <Text fontSize="xl" fontWeight="semibold" color="fg" mb="16px">5 steg för att börja</Text>
        <VStack gap="16px" align="stretch">
        {steps.map((step) => (
          <Box key={step.number} bg="bg.subtle" borderRadius="8px" p="20px" border="1px solid" borderColor="border">
            <Flex gap="16px" align="flex-start">
              <Flex
                w="36px"
                h="36px"
                borderRadius="full"
                bg="brand.500"
                align="center"
                justify="center"
                flexShrink={0}
              >
                <Text fontWeight="bold" color="white">{step.number}</Text>
              </Flex>
              <Box flex="1">
                <Text fontSize="lg" fontWeight="semibold" color="fg">{step.title}</Text>
                <Text color="fg.muted" mt="8px" lineHeight="1.6">{step.description}</Text>
                <Box bg="border" borderRadius="6px" p="12px" mt="12px">
                  <Text fontSize="sm" color="fg.muted">{step.tip}</Text>
                </Box>
                {step.link && (
                  <Link to={step.link}>
                    <Text color="brand.400" fontSize="sm" mt="12px" _hover={{ textDecoration: 'underline' }}>
                      {step.linkText}
                    </Text>
                  </Link>
                )}
              </Box>
            </Flex>
          </Box>
        ))}
        </VStack>
      </Box>

      {/* Strategy Overview */}
      <Box>
        <Text fontSize="xl" fontWeight="semibold" color="fg" mb="16px">Våra strategier</Text>
        <SimpleGrid columns={{ base: 1, md: 2 }} gap="12px">
          {strategies.map((s) => (
            <Link key={s.path} to={s.path}>
              <Box
                bg="bg.subtle"
                borderRadius="8px"
                p="16px"
                border="1px solid"
                borderColor="border"
                _hover={{ borderColor: 'brand.500', bg: 'bg.hover' }}
                transition="all 150ms"
              >
                <Text fontWeight="semibold" color="fg">{s.name}</Text>
                <Text fontSize="sm" color="fg.subtle" mt="4px">{s.description}</Text>
                <HStack mt="8px" gap="8px">
                  <Box bg="border" px="8px" py="2px" borderRadius="4px">
                    <Text fontSize="xs" color="fg.muted">{s.rebalance}</Text>
                  </Box>
                </HStack>
              </Box>
            </Link>
          ))}
        </SimpleGrid>
      </Box>

      {/* Quick Tips */}
      <Box bg="bg.subtle" borderRadius="8px" p="20px" border="1px solid" borderColor="border">
        <Text fontSize="lg" fontWeight="semibold" color="fg" mb="12px">Viktigt att tänka på</Text>
        <VStack align="stretch" gap="8px">
          <HStack align="flex-start" gap="8px">
            <Text color="brand.400">•</Text>
            <Text fontSize="sm" color="fg.muted">Använd ISK för skattefördelar - du betalar bara ~0.9% årlig skatt istället för 30% på vinster</Text>
          </HStack>
          <HStack align="flex-start" gap="8px">
            <Text color="brand.400">•</Text>
            <Text fontSize="sm" color="fg.muted">Investera långsiktigt - strategierna fungerar bäst över 5+ år</Text>
          </HStack>
          <HStack align="flex-start" gap="8px">
            <Text color="brand.400">•</Text>
            <Text fontSize="sm" color="fg.muted">Följ systemet - låt inte känslor styra dina beslut</Text>
          </HStack>
          <HStack align="flex-start" gap="8px">
            <Text color="brand.400">•</Text>
            <Text fontSize="sm" color="fg.muted">Historisk avkastning är ingen garanti för framtida resultat</Text>
          </HStack>
        </VStack>
      </Box>

      {/* Disclaimer */}
      <Box bg="bg.muted" borderRadius="8px" p="16px" border="1px solid" borderColor="bg.subtle">
        <Text fontSize="xs" color="fg0" lineHeight="1.6">
          <Text as="span" fontWeight="semibold">Ansvarsbegränsning:</Text> Informationen på denna sida är endast för utbildningsändamål och ska inte ses som köp- eller säljrekommendationer eller individuell rådgivning. Historisk avkastning är ingen garanti för framtida avkastning. Finansiella tillgångar kan både öka och minska i värde och det finns risk att du inte får tillbaka investerat kapital.
        </Text>
      </Box>
    </VStack>
  );
}
