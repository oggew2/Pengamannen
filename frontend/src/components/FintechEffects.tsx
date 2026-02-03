import { useEffect, useState, useRef, createContext, useContext, useCallback, ReactNode } from 'react';
import { Box, Text } from '@chakra-ui/react';

// ============================================
// CELEBRATION CONTEXT - Trigger confetti on achievements
// ============================================
type CelebrationReason = 'first_import' | 'rebalance_executed' | 'goal_reached' | 'first_month' | 'custom';

interface CelebrationContextType {
  celebrate: (reason?: CelebrationReason) => void;
  isActive: boolean;
}

const CelebrationContext = createContext<CelebrationContextType | null>(null);

export function CelebrationProvider({ children }: { children: ReactNode }) {
  const [isActive, setIsActive] = useState(false);

  const celebrate = useCallback((_reason?: CelebrationReason) => {
    setIsActive(true);
    // Haptic feedback
    if ('vibrate' in navigator) {
      navigator.vibrate([50, 30, 50]);
    }
    // Auto-dismiss after animation
    setTimeout(() => setIsActive(false), 2500);
  }, []);

  return (
    <CelebrationContext.Provider value={{ celebrate, isActive }}>
      {children}
      <Confetti active={isActive} />
    </CelebrationContext.Provider>
  );
}

export function useCelebration() {
  const context = useContext(CelebrationContext);
  if (!context) {
    // Return no-op if used outside provider
    return { celebrate: () => {}, isActive: false };
  }
  return context;
}

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

// Animated number that counts up with optional color + direction arrows
export function AnimatedNumber({ 
  value, 
  format = 'currency',
  duration = 600,
  showDirection = false,
  colorize = false,
}: { 
  value: number; 
  format?: 'currency' | 'percent' | 'number';
  duration?: number;
  showDirection?: boolean;
  colorize?: boolean;
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

  const arrow = showDirection ? (value > 0 ? ' ↑' : value < 0 ? ' ↓' : ' →') : '';
  const color = colorize ? (value > 0 ? 'var(--color-green-400)' : value < 0 ? 'var(--color-red-400)' : 'var(--color-gray-400)') : 'inherit';

  return <span style={{ color }}>{formatted}{arrow}</span>;
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

// ============================================
// SKELETON LOADING COMPONENTS
// ============================================

// Stock card skeleton - matches StockCard layout
export function StockCardSkeleton() {
  return (
    <Box className="skeleton-card" p="16px" borderRadius="12px" bg="bg.subtle">
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb="12px">
        <Box>
          <Box className="skeleton" w="80px" h="20px" borderRadius="4px" mb="6px" />
          <Box className="skeleton" w="120px" h="14px" borderRadius="4px" />
        </Box>
        <Box className="skeleton" w="60px" h="24px" borderRadius="6px" />
      </Box>
      <Box display="flex" gap="16px">
        <Box className="skeleton" w="70px" h="14px" borderRadius="4px" />
        <Box className="skeleton" w="70px" h="14px" borderRadius="4px" />
      </Box>
    </Box>
  );
}

// Chart skeleton - matches chart area
export function ChartSkeleton({ height = 200 }: { height?: number }) {
  return (
    <Box className="skeleton-card" p="16px" borderRadius="12px" bg="bg.subtle">
      <Box display="flex" justifyContent="space-between" mb="16px">
        <Box className="skeleton" w="100px" h="16px" borderRadius="4px" />
        <Box display="flex" gap="8px">
          <Box className="skeleton" w="40px" h="24px" borderRadius="4px" />
          <Box className="skeleton" w="40px" h="24px" borderRadius="4px" />
        </Box>
      </Box>
      <Box className="skeleton" w="100%" h={`${height}px`} borderRadius="8px" />
    </Box>
  );
}

// Table skeleton - matches data table layout
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <Box className="skeleton-card" borderRadius="12px" bg="bg.subtle" overflow="hidden">
      {/* Header */}
      <Box display="flex" gap="16px" p="12px 16px" borderBottomWidth="1px" borderColor="border.subtle">
        <Box className="skeleton" w="30%" h="14px" borderRadius="4px" />
        <Box className="skeleton" w="20%" h="14px" borderRadius="4px" />
        <Box className="skeleton" w="20%" h="14px" borderRadius="4px" />
        <Box className="skeleton" w="20%" h="14px" borderRadius="4px" />
      </Box>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <Box key={i} display="flex" gap="16px" p="12px 16px" borderBottomWidth={i < rows - 1 ? '1px' : '0'} borderColor="border.subtle">
          <Box className="skeleton" w="30%" h="16px" borderRadius="4px" />
          <Box className="skeleton" w="20%" h="16px" borderRadius="4px" />
          <Box className="skeleton" w="20%" h="16px" borderRadius="4px" />
          <Box className="skeleton" w="20%" h="16px" borderRadius="4px" />
        </Box>
      ))}
    </Box>
  );
}

// Stats card skeleton
export function StatsCardSkeleton() {
  return (
    <Box className="skeleton-card" p="20px" borderRadius="12px" bg="bg.subtle">
      <Box className="skeleton" w="80px" h="12px" borderRadius="4px" mb="8px" />
      <Box className="skeleton" w="120px" h="32px" borderRadius="4px" mb="4px" />
      <Box className="skeleton" w="60px" h="14px" borderRadius="4px" />
    </Box>
  );
}
