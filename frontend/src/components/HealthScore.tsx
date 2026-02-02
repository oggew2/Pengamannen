import { Box, HStack, Text, SimpleGrid } from '@chakra-ui/react';

interface HealthScoreProps {
  drift: number;
  holdingsCount: number;
  daysUntilRebalance: number;
  topRankCount: number;  // How many holdings are in top 10
}

export function HealthScore({ drift, holdingsCount, daysUntilRebalance, topRankCount }: HealthScoreProps) {
  // Calculate individual scores (0-100)
  const diversificationScore = Math.min(100, holdingsCount * 10);  // 10 holdings = 100
  const driftScore = Math.max(0, 100 - drift * 3);  // 0% drift = 100, 33% drift = 0
  const timingScore = daysUntilRebalance <= 7 ? 100 : daysUntilRebalance <= 30 ? 70 : 50;
  const qualityScore = Math.min(100, topRankCount * 10);  // All top 10 = 100
  
  const overallScore = Math.round((diversificationScore + driftScore + timingScore + qualityScore) / 4);
  
  const getColor = (score: number) => score >= 70 ? 'green.400' : score >= 40 ? 'yellow.400' : 'red.400';
  const getEmoji = (score: number) => score >= 70 ? '🟢' : score >= 40 ? '🟡' : '🔴';
  
  const scores = [
    { label: 'Diversifiering', score: diversificationScore, tip: `${holdingsCount}/10 positioner` },
    { label: 'Drift', score: driftScore, tip: `${drift.toFixed(1)}% avvikelse` },
    { label: 'Timing', score: timingScore, tip: `${daysUntilRebalance}d till ombalansering` },
    { label: 'Kvalitet', score: qualityScore, tip: `${topRankCount}/10 i topp 10` },
  ];

  return (
    <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
      <HStack justify="space-between" mb="12px">
        <Text fontSize="sm" fontWeight="semibold">📊 Portföljhälsa</Text>
        <HStack gap="4px">
          <Text fontSize="2xl" fontWeight="bold" color={getColor(overallScore)}>{overallScore}</Text>
          <Text fontSize="xs" color="fg.muted">/100</Text>
        </HStack>
      </HStack>
      
      <SimpleGrid columns={2} gap="8px">
        {scores.map(s => (
          <Box key={s.label} p="8px" bg="bg.subtle" borderRadius="6px">
            <HStack justify="space-between" mb="4px">
              <Text fontSize="xs" color="fg.muted">{s.label}</Text>
              <Text fontSize="xs" color={getColor(s.score)}>{getEmoji(s.score)} {s.score}</Text>
            </HStack>
            <Box w="100%" h="4px" bg="gray.700" borderRadius="full" overflow="hidden">
              <Box h="100%" w={`${s.score}%`} bg={getColor(s.score)} borderRadius="full" transition="width 0.3s" />
            </Box>
            <Text fontSize="xs" color="fg.muted" mt="4px">{s.tip}</Text>
          </Box>
        ))}
      </SimpleGrid>
    </Box>
  );
}
