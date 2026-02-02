import { Box, VStack, HStack, Text, SimpleGrid } from '@chakra-ui/react';
import { useState, useEffect } from 'react';

// Achievement definitions - good, bad, and fun
export const ACHIEVEMENTS = [
  // 🏆 GOOD - Strategy & Discipline
  { id: 'first_import', icon: '🎯', name: 'Första steget', desc: 'Importerade din första portfölj', category: 'good' },
  { id: 'first_rebalance', icon: '🔄', name: 'Ombalanserare', desc: 'Genomförde din första ombalansering', category: 'good' },
  { id: 'streak_2', icon: '🔥', name: 'På rätt spår', desc: 'Följde strategin 2 kvartal i rad', category: 'good' },
  { id: 'streak_4', icon: '🔥', name: 'Konsekvent', desc: 'Följde strategin 4 kvartal i rad', category: 'good' },
  { id: 'streak_8', icon: '👑', name: 'Mästare', desc: 'Följde strategin 8 kvartal i rad', category: 'good' },
  { id: 'full_top10', icon: '🎯', name: 'Sharpshooter', desc: 'Äger alla topp 10 aktier', category: 'good' },
  { id: 'beat_index_10', icon: '📈', name: 'Indexkrossare', desc: 'Slog index med 10% på ett år', category: 'good' },
  { id: 'beat_index_20', icon: '🚀', name: 'Raket', desc: 'Slog index med 20% på ett år', category: 'good' },
  { id: 'diversified', icon: '🌈', name: 'Diversifierad', desc: 'Äger aktier i 5+ sektorer', category: 'good' },
  { id: 'patient', icon: '🧘', name: 'Tålmodig', desc: 'Höll en aktie i 12+ månader', category: 'good' },
  
  // 📉 BAD - Learning experiences
  { id: 'first_loss', icon: '📉', name: 'Läropengar', desc: 'Första aktien med förlust', category: 'bad' },
  { id: 'drop_5', icon: '😰', name: 'Skakig dag', desc: 'Portföljen föll 5% på en dag', category: 'bad' },
  { id: 'drop_10', icon: '😱', name: 'Blodbad', desc: 'Portföljen föll 10% på en dag', category: 'bad' },
  { id: 'missed_rebalance', icon: '⏰', name: 'Glömsk', desc: 'Missade en ombalansering', category: 'bad' },
  { id: 'sold_winner', icon: '🤦', name: 'Sålde för tidigt', desc: 'Sålde en aktie som sedan steg 20%', category: 'bad' },
  { id: 'bought_loser', icon: '💸', name: 'Dålig timing', desc: 'Köpte en aktie som föll 20%', category: 'bad' },
  { id: 'panic_sell', icon: '😨', name: 'Panikförsäljare', desc: 'Sålde allt på en röd dag', category: 'bad' },
  
  // 🎉 FUN - Milestones & quirky
  { id: 'portfolio_100k', icon: '💰', name: 'Sex siffror', desc: 'Portföljen nådde 100,000 kr', category: 'fun' },
  { id: 'portfolio_500k', icon: '💎', name: 'Halvmiljonär', desc: 'Portföljen nådde 500,000 kr', category: 'fun' },
  { id: 'portfolio_1m', icon: '🏆', name: 'Miljonär', desc: 'Portföljen nådde 1,000,000 kr', category: 'fun' },
  { id: 'profit_10k', icon: '🎉', name: 'Första tian', desc: 'Tjänade 10,000 kr totalt', category: 'fun' },
  { id: 'profit_50k', icon: '🥳', name: 'Femtiolansen', desc: 'Tjänade 50,000 kr totalt', category: 'fun' },
  { id: 'early_bird', icon: '🐦', name: 'Morgonpigg', desc: 'Kollade portföljen före kl 7', category: 'fun' },
  { id: 'night_owl', icon: '🦉', name: 'Nattuggla', desc: 'Kollade portföljen efter midnatt', category: 'fun' },
  { id: 'weekend_warrior', icon: '📅', name: 'Helgkrigare', desc: 'Kollade portföljen på en lördag', category: 'fun' },
  { id: 'lucky_7', icon: '🍀', name: 'Lucky 7', desc: '7 gröna dagar i rad', category: 'fun' },
  { id: 'comeback', icon: '💪', name: 'Comeback', desc: 'Gick från -10% till +10%', category: 'fun' },
  { id: 'diamond_hands', icon: '💎', name: 'Diamanthänder', desc: 'Höll under en 20% nedgång', category: 'fun' },
  { id: 'saab_owner', icon: '✈️', name: 'Flygplansfantast', desc: 'Ägde SAAB B', category: 'fun' },
  { id: 'volvo_owner', icon: '🚗', name: 'Bilentusiast', desc: 'Ägde VOLV B', category: 'fun' },
  { id: 'perfect_timing', icon: '⏱️', name: 'Perfekt timing', desc: 'Köpte på årets lägsta', category: 'fun' },
];

interface Achievement {
  id: string;
  icon: string;
  name: string;
  desc: string;
  category: string;
  unlocked?: boolean;
  progress?: number;
  unlocked_at?: string;
}

interface AchievementsData {
  unlocked: string[];
  progress: Record<string, number>;
  streak: number;
}

export function Achievements() {
  const [data, setData] = useState<AchievementsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAchievements();
  }, []);

  const fetchAchievements = async () => {
    try {
      const res = await fetch('/v1/portfolio/achievements', { credentials: 'include' });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (e) {
      console.error('Failed to fetch achievements:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box bg="bg" borderRadius="xl" p={5} borderWidth="1px" borderColor="border">
        <VStack gap={3}>
          <Box w="150px" h="24px" bg="gray.700" borderRadius="md" className="skeleton-pulse" />
          <SimpleGrid columns={2} gap={3} w="100%">
            {[1,2,3,4].map(i => <Box key={i} h="80px" bg="gray.700" borderRadius="lg" className="skeleton-pulse" />)}
          </SimpleGrid>
        </VStack>
      </Box>
    );
  }

  const unlocked = data?.unlocked || [];
  const progress = data?.progress || {};
  const unlockedCount = unlocked.length;
  const totalCount = ACHIEVEMENTS.length;

  // Merge achievement definitions with user data
  const achievements = ACHIEVEMENTS.map(a => ({
    ...a,
    unlocked: unlocked.includes(a.id),
    progress: progress[a.id] || 0,
  }));

  // Sort: unlocked first, then by progress
  const sorted = [...achievements].sort((a, b) => {
    if (a.unlocked && !b.unlocked) return -1;
    if (!a.unlocked && b.unlocked) return 1;
    return (b.progress || 0) - (a.progress || 0);
  });

  return (
    <Box bg="bg" borderRadius="xl" p={5} borderWidth="1px" borderColor="border">
      <VStack gap={4} align="stretch">
        <HStack justify="space-between">
          <Text fontSize="lg" fontWeight="bold">🏆 Prestationer</Text>
          <Text color="fg.muted" fontSize="sm">{unlockedCount}/{totalCount}</Text>
        </HStack>

        {/* Streak display */}
        {data?.streak && data.streak > 0 && (
          <Box bg="orange.900" p={3} borderRadius="lg" textAlign="center">
            <Text fontSize="2xl">🔥 {data.streak}</Text>
            <Text fontSize="sm" color="orange.200">kvartal i rad</Text>
          </Box>
        )}

        {/* Achievement grid */}
        <SimpleGrid columns={{ base: 1, md: 2 }} gap={3}>
          {sorted.slice(0, 8).map(a => (
            <AchievementCard key={a.id} achievement={a} />
          ))}
        </SimpleGrid>

        {sorted.length > 8 && (
          <Text fontSize="sm" color="fg.muted" textAlign="center">
            +{sorted.length - 8} fler prestationer
          </Text>
        )}
      </VStack>
    </Box>
  );
}

function AchievementCard({ achievement }: { achievement: Achievement }) {
  const { icon, name, desc, unlocked, progress, category } = achievement;
  
  const bgColor = unlocked 
    ? category === 'bad' ? 'rgba(245, 101, 101, 0.1)' : 'rgba(72, 187, 120, 0.1)'
    : 'gray.800';
  
  const borderColor = unlocked
    ? category === 'bad' ? 'red.400' : category === 'fun' ? 'purple.400' : 'green.400'
    : 'transparent';

  return (
    <Box 
      bg={bgColor} 
      p={3} 
      borderRadius="lg" 
      borderLeft="3px solid" 
      borderColor={borderColor}
      opacity={unlocked ? 1 : 0.6}
    >
      <HStack gap={3}>
        <Text fontSize="2xl">{unlocked ? icon : '🔒'}</Text>
        <VStack align="start" gap={0} flex={1}>
          <Text fontWeight="bold" fontSize="sm">{name}</Text>
          <Text fontSize="xs" color="fg.muted">{desc}</Text>
          {!unlocked && progress !== undefined && progress > 0 && (
            <Box w="100%" h="4px" bg="gray.700" borderRadius="full" mt={1} overflow="hidden">
              <Box h="100%" w={`${progress}%`} bg="green.400" borderRadius="full" />
            </Box>
          )}
        </VStack>
      </HStack>
    </Box>
  );
}
