import { Box, HStack, VStack, Text } from '@chakra-ui/react';
import { useState, useEffect } from 'react';
import { AnimatedNumber } from './FintechEffects';
import { useUIStyle } from '../contexts/UIStyleContext';

interface DailyStatsData {
  total_value: number;
  today_change: number;
  today_change_pct: number;
  week_change_pct: number;
  month_change_pct: number;
  best_performer: { ticker: string; change_pct: number } | null;
  worst_performer: { ticker: string; change_pct: number } | null;
}

export function DailyStats() {
  const [data, setData] = useState<DailyStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [greeting, setGreeting] = useState('');
  const { isModern } = useUIStyle();

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 10) setGreeting('God morgon');
    else if (hour < 17) setGreeting('God eftermiddag');
    else setGreeting('God kväll');
    
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('/v1/portfolio/daily-stats', { credentials: 'include' });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error('Failed to fetch daily stats:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box bg="bg" borderRadius="xl" p={5} borderWidth="1px" borderColor="border">
        <VStack gap={3}>
          <Box w="150px" h="20px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
          <Box w="200px" h="40px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
          <HStack gap={4} w="100%">
            <Box flex={1} h="60px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
            <Box flex={1} h="60px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
            <Box flex={1} h="60px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
          </HStack>
        </VStack>
      </Box>
    );
  }

  if (!data) return null;

  const isPositive = data.today_change >= 0;

  return (
    <Box bg="bg" borderRadius="xl" p={5} borderWidth="1px" borderColor="border" className={isModern ? 'glass shadow-soft-lg' : ''}>
      <VStack gap={4} align="stretch">
        {/* Greeting */}
        <Text color="fg.muted" fontSize="sm">{greeting}! 👋</Text>
        
        {/* Main value */}
        <VStack align="start" gap={1}>
          <HStack align="baseline" gap={2}>
            <Text fontSize="3xl" fontWeight="bold">
              <AnimatedNumber value={data.total_value} format="currency" />
            </Text>
          </HStack>
          <HStack gap={2}>
            <Text fontSize="lg" fontWeight="semibold">
              {isModern ? (
                <AnimatedNumber value={data.today_change} format="currency" showDirection colorize />
              ) : (
                <span style={{ color: isPositive ? '#4ade80' : '#f87171' }}>
                  {isPositive ? '+' : ''}{data.today_change.toLocaleString('sv-SE')} kr
                </span>
              )}
            </Text>
            <Text fontSize="xs" color="fg.muted" bg="gray.700" px={2} py={0.5} borderRadius="full">
              idag
            </Text>
          </HStack>
        </VStack>

        {/* Period stats */}
        <HStack gap={3} flexWrap="wrap">
          <StatBox label="Idag" value={data.today_change_pct} isModern={isModern} />
          <StatBox label="Vecka" value={data.week_change_pct} isModern={isModern} />
          <StatBox label="Månad" value={data.month_change_pct} isModern={isModern} />
        </HStack>

        {/* Best/Worst performers */}
        {(data.best_performer || data.worst_performer) && (
          <HStack gap={3}>
            {data.best_performer && (
              <Box flex={1} bg="rgba(72, 187, 120, 0.1)" p={3} borderRadius="lg" borderLeft="3px solid" borderColor="green.400">
                <Text fontSize="xs" color="fg.muted">🏆 Bäst idag</Text>
                <HStack justify="space-between">
                  <Text fontWeight="bold">{data.best_performer.ticker}</Text>
                  {isModern ? (
                    <AnimatedNumber value={data.best_performer.change_pct} format="percent" showDirection colorize />
                  ) : (
                    <Text color="green.400" fontWeight="bold">+{data.best_performer.change_pct.toFixed(1)}%</Text>
                  )}
                </HStack>
              </Box>
            )}
            {data.worst_performer && (
              <Box flex={1} bg="rgba(245, 101, 101, 0.1)" p={3} borderRadius="lg" borderLeft="3px solid" borderColor="red.400">
                <Text fontSize="xs" color="fg.muted">📉 Sämst idag</Text>
                <HStack justify="space-between">
                  <Text fontWeight="bold">{data.worst_performer.ticker}</Text>
                  {isModern ? (
                    <AnimatedNumber value={data.worst_performer.change_pct} format="percent" showDirection colorize />
                  ) : (
                    <Text color="red.400" fontWeight="bold">{data.worst_performer.change_pct.toFixed(1)}%</Text>
                  )}
                </HStack>
              </Box>
            )}
          </HStack>
        )}
      </VStack>
    </Box>
  );
}

function StatBox({ label, value, isModern }: { label: string; value: number; isModern: boolean }) {
  return (
    <Box flex={1} minW="80px" bg="gray.800" p={3} borderRadius="lg" textAlign="center" className={isModern ? 'shadow-soft-sm' : ''}>
      <Text fontSize="xs" color="fg.muted">{label}</Text>
      <Text fontWeight="bold">
        {isModern ? (
          <AnimatedNumber value={value} format="percent" showDirection colorize />
        ) : (
          <span style={{ color: value >= 0 ? '#4ade80' : '#f87171' }}>
            {value >= 0 ? '+' : ''}{value.toFixed(1)}%
          </span>
        )}
      </Text>
    </Box>
  );
}
