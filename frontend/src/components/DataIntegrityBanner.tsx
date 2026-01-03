import { useState, useEffect } from 'react';
import { Box, Flex, Text, Button, VStack, HStack } from '@chakra-ui/react';
import { api } from '../api/client';
import { tokens } from '../theme/tokens';

interface IntegrityCheck {
  safe_to_trade: boolean;
  status: 'OK' | 'WARNING' | 'CRITICAL';
  recommendation: string;
  critical_issues: Array<{ type: string; message: string }>;
  warning_count: number;
}

export function DataIntegrityBanner() {
  const [integrity, setIntegrity] = useState<IntegrityCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api.get<IntegrityCheck>('/data/integrity/quick')
      .then(data => {
        setIntegrity(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // Don't show if loading, dismissed, or data is OK
  if (loading || dismissed || !integrity || integrity.status === 'OK') {
    return null;
  }

  const isCritical = integrity.status === 'CRITICAL';
  const bgColor = isCritical ? tokens.colors.semantic.errorLight : tokens.colors.semantic.warningLight;
  const borderColor = isCritical ? tokens.colors.semantic.error : tokens.colors.semantic.warning;
  const iconColor = isCritical ? tokens.colors.semantic.error : tokens.colors.semantic.warning;

  return (
    <Box
      bg={bgColor}
      borderWidth="1px"
      borderColor={borderColor}
      borderRadius={tokens.radii.lg}
      p={tokens.spacing.md}
      mb={tokens.spacing.lg}
    >
      <Flex justify="space-between" align="start">
        <HStack align="start" gap={tokens.spacing.sm}>
          <Text fontSize="xl" color={iconColor}>
            {isCritical ? '🚨' : '⚠️'}
          </Text>
          <VStack align="start" gap={tokens.spacing.xs}>
            <Text
              fontSize={tokens.fontSizes.sm}
              fontWeight={tokens.fontWeights.semibold}
              color={tokens.colors.text.primary}
            >
              {isCritical ? 'Data Integrity Issue - Do Not Trade' : 'Data Warning'}
            </Text>
            <Text fontSize={tokens.fontSizes.xs} color={tokens.colors.text.secondary}>
              {integrity.recommendation}
            </Text>
          </VStack>
        </HStack>
        
        <HStack gap={tokens.spacing.sm}>
          {integrity.critical_issues.length > 0 && (
            <Button
              size="xs"
              variant="ghost"
              color={tokens.colors.text.secondary}
              onClick={() => setExpanded(!expanded)}
              _hover={{ bg: 'transparent', color: tokens.colors.text.primary }}
            >
              {expanded ? 'Hide Details' : 'Show Details'}
            </Button>
          )}
          {!isCritical && (
            <Button
              size="xs"
              variant="ghost"
              color={tokens.colors.text.muted}
              onClick={() => setDismissed(true)}
              _hover={{ bg: 'transparent', color: tokens.colors.text.primary }}
              aria-label="Dismiss warning"
            >
              ✕
            </Button>
          )}
        </HStack>
      </Flex>

      {expanded && integrity.critical_issues.length > 0 && (
        <VStack align="start" gap={tokens.spacing.xs} mt={tokens.spacing.md} pl="28px">
          {integrity.critical_issues.map((issue, i) => (
            <Text key={i} fontSize={tokens.fontSizes.xs} color={tokens.colors.text.secondary}>
              • {issue.message}
            </Text>
          ))}
        </VStack>
      )}
    </Box>
  );
}

// Compact indicator for header/nav with click-to-expand details
export function DataIntegrityIndicator() {
  const [integrity, setIntegrity] = useState<IntegrityCheck | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [syncInfo, setSyncInfo] = useState<{last_sync: string | null, fresh_pct: number} | null>(null);

  useEffect(() => {
    api.get<IntegrityCheck>('/data/integrity/quick')
      .then(setIntegrity)
      .catch(() => {});
    
    // Also fetch freshness info
    api.get<{summary?: {fresh_percentage: number, fresh_count: number, total_stocks: number}}>('/data/status/detailed')
      .then(data => {
        if (data.summary) {
          setSyncInfo({ last_sync: null, fresh_pct: data.summary.fresh_percentage });
        }
      })
      .catch(() => {});
    
    api.get<{last_successful_sync: string | null}>('/data/sync-history?days=1')
      .then(data => {
        setSyncInfo(prev => prev ? {...prev, last_sync: data.last_successful_sync} : null);
      })
      .catch(() => {});
  }, []);

  if (!integrity) return null;

  const color = integrity.status === 'OK' 
    ? tokens.colors.semantic.success 
    : integrity.status === 'WARNING'
    ? tokens.colors.semantic.warning
    : tokens.colors.semantic.error;

  const label = integrity.status === 'OK' 
    ? 'Data OK' 
    : integrity.status === 'WARNING'
    ? 'Data Warning'
    : 'Data Issue';

  const formatTimeAgo = (dateStr: string) => {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  return (
    <Box position="relative">
      <HStack 
        gap={tokens.spacing.xs} 
        fontSize={tokens.fontSizes.xs} 
        color={tokens.colors.text.muted}
        cursor="pointer"
        onClick={() => setShowDetails(!showDetails)}
        _hover={{ color: tokens.colors.text.primary }}
        transition="color 0.15s"
      >
        <Box w="8px" h="8px" borderRadius="50%" bg={color} />
        <Text>{label}</Text>
        {syncInfo?.last_sync && (
          <Text color={tokens.colors.text.muted}>· {formatTimeAgo(syncInfo.last_sync)}</Text>
        )}
      </HStack>
      
      {showDetails && (
        <>
          <Box 
            position="fixed" 
            inset={0} 
            zIndex={40} 
            onClick={() => setShowDetails(false)}
          />
          <Box
            position="absolute"
            top="100%"
            left={0}
            mt={tokens.spacing.sm}
            p={tokens.spacing.md}
            bg="gray.700"
            border="1px solid"
            borderColor="gray.600"
            borderRadius={tokens.radii.md}
            boxShadow="lg"
            fontSize={tokens.fontSizes.xs}
            minW="200px"
            zIndex={50}
          >
            <VStack align="stretch" gap={tokens.spacing.xs}>
              <HStack justify="space-between">
                <Text color={tokens.colors.text.muted}>Status</Text>
                <HStack gap={tokens.spacing.xs}>
                  <Box w="8px" h="8px" borderRadius="50%" bg={color} />
                  <Text fontWeight="500">{label}</Text>
                </HStack>
              </HStack>
              {syncInfo && (
                <>
                  <HStack justify="space-between">
                    <Text color={tokens.colors.text.muted}>Freshness</Text>
                    <Text fontWeight="500" color={syncInfo.fresh_pct >= 80 ? tokens.colors.semantic.success : tokens.colors.semantic.warning}>
                      {syncInfo.fresh_pct.toFixed(0)}%
                    </Text>
                  </HStack>
                  {syncInfo.last_sync && (
                    <HStack justify="space-between">
                      <Text color={tokens.colors.text.muted}>Last sync</Text>
                      <Text fontWeight="500">{formatTimeAgo(syncInfo.last_sync)}</Text>
                    </HStack>
                  )}
                </>
              )}
              {integrity.warning_count > 0 && (
                <Box mt={tokens.spacing.xs} pt={tokens.spacing.xs} borderTop="1px solid" borderColor="gray.600">
                  <Text color={tokens.colors.semantic.warning} fontSize="11px">
                    {integrity.warning_count} warning{integrity.warning_count > 1 ? 's' : ''}
                  </Text>
                </Box>
              )}
            </VStack>
          </Box>
        </>
      )}
    </Box>
  );
}
