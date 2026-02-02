import { useEffect, useState, useRef } from 'react';
import { Box, Text } from '@chakra-ui/react';

// Confetti animation component
export function Confetti({ active, onComplete }: { active: boolean; onComplete?: () => void }) {
  const [particles, setParticles] = useState<Array<{ id: number; x: number; color: string; delay: number }>>([]);

  useEffect(() => {
    if (active) {
      const colors = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'];
      const newParticles = Array.from({ length: 50 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        color: colors[Math.floor(Math.random() * colors.length)],
        delay: Math.random() * 0.5,
      }));
      setParticles(newParticles);
      
      // Haptic feedback if available
      if ('vibrate' in navigator) {
        navigator.vibrate([50, 30, 50]);
      }
      
      const timer = setTimeout(() => {
        setParticles([]);
        onComplete?.();
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [active, onComplete]);

  if (!particles.length) return null;

  return (
    <Box position="fixed" top="0" left="0" right="0" bottom="0" pointerEvents="none" zIndex="9999" overflow="hidden">
      {particles.map(p => (
        <Box
          key={p.id}
          position="absolute"
          left={`${p.x}%`}
          top="-20px"
          w="10px"
          h="10px"
          bg={p.color}
          borderRadius="2px"
          animation={`confetti-fall 2s ease-out ${p.delay}s forwards`}
          transform="rotate(0deg)"
        />
      ))}
      <style>{`
        @keyframes confetti-fall {
          0% { transform: translateY(0) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
        }
      `}</style>
    </Box>
  );
}

// Animated number that counts up
export function AnimatedNumber({ 
  value, 
  format = 'currency',
  duration = 600 
}: { 
  value: number; 
  format?: 'currency' | 'percent' | 'number';
  duration?: number;
}) {
  const [displayValue, setDisplayValue] = useState(value);
  const prevValue = useRef(value);
  const animationRef = useRef<number>();

  useEffect(() => {
    const startValue = prevValue.current;
    const endValue = value;
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = startValue + (endValue - startValue) * eased;
      setDisplayValue(current);

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        prevValue.current = endValue;
      }
    };

    animationRef.current = requestAnimationFrame(animate);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [value, duration]);

  const formatted = (() => {
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(displayValue);
      case 'percent':
        return `${displayValue >= 0 ? '+' : ''}${displayValue.toFixed(1)}%`;
      case 'number':
        return Math.round(displayValue).toLocaleString('sv-SE');
      default:
        return displayValue.toString();
    }
  })();

  return <>{formatted}</>;
}

// Portfolio health badge
export function HealthBadge({ 
  drift, 
  holdingsCount,
  daysUntilRebalance 
}: { 
  drift: number;
  holdingsCount: number;
  daysUntilRebalance: number;
}) {
  // Calculate health score (0-100)
  const driftScore = Math.max(0, 100 - drift * 5); // -5 points per % drift
  const diversificationScore = holdingsCount >= 10 ? 100 : holdingsCount * 10;
  const timingScore = daysUntilRebalance <= 7 ? 60 : daysUntilRebalance <= 30 ? 80 : 100;
  
  const healthScore = Math.round((driftScore + diversificationScore + timingScore) / 3);
  
  const getColor = () => {
    if (healthScore >= 80) return 'green';
    if (healthScore >= 60) return 'yellow';
    return 'red';
  };
  
  const getLabel = () => {
    if (healthScore >= 80) return 'Utmärkt';
    if (healthScore >= 60) return 'Bra';
    return 'Behöver åtgärd';
  };

  const color = getColor();

  return (
    <Box 
      display="inline-flex" 
      alignItems="center" 
      gap="6px" 
      px="10px" 
      py="4px" 
      borderRadius="full"
      bg={`${color}.900/30`}
      borderWidth="1px"
      borderColor={`${color}.500`}
    >
      <Box w="8px" h="8px" borderRadius="full" bg={`${color}.400`} />
      <Text fontSize="xs" fontWeight="medium" color={`${color}.400`}>
        {healthScore} • {getLabel()}
      </Text>
    </Box>
  );
}

// Pull to refresh hook
export function usePullToRefresh(onRefresh: () => Promise<void>) {
  const [refreshing, setRefreshing] = useState(false);
  const startY = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleTouchStart = (e: TouchEvent) => {
      if (window.scrollY === 0) {
        startY.current = e.touches[0].clientY;
      }
    };

    const handleTouchMove = async (e: TouchEvent) => {
      if (refreshing || window.scrollY > 0) return;
      
      const currentY = e.touches[0].clientY;
      const diff = currentY - startY.current;
      
      if (diff > 80) {
        setRefreshing(true);
        if ('vibrate' in navigator) navigator.vibrate(30);
        await onRefresh();
        setRefreshing(false);
      }
    };

    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: true });

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
    };
  }, [onRefresh, refreshing]);

  return { containerRef, refreshing };
}
