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

// Compact indicator for header/nav - mirrors DataFreshnessIndicator from Dashboard
export function DataIntegrityIndicator() {
  const [showDetails, setShowDetails] = useState(false);
  const [status, setStatus] = useState<{summary?: {total_stocks: number, fresh_count: number, fresh_percentage: number}} | null>(null);
  const [syncHistory, setSyncHistory] = useState<{last_successful_sync: string | null, next_scheduled_sync: string, total_syncs: number, successful_syncs: number} | null>(null);

  useEffect(() => {
    api.get<{summary?: {total_stocks: number, fresh_count: number, fresh_percentage: number}}>('/data/status/detailed')
      .then(setStatus)
      .catch(() => {});
    api.get<{last_successful_sync: string | null, next_scheduled_sync: string, total_syncs: number, successful_syncs: number}>('/data/sync-history?days=1')
      .then(setSyncHistory)
      .catch(() => {});
  }, []);

  if (!status?.summary) return null;

  const { fresh_percentage, total_stocks, fresh_count } = status.summary;
  const color = fresh_percentage >= 80 ? tokens.colors.semantic.success : fresh_percentage >= 50 ? tokens.colors.semantic.warning : tokens.colors.semantic.error;
  const statusLabel = fresh_percentage >= 80 ? 'OK' : fresh_percentage >= 50 ? 'Stale' : 'Outdated';

  const formatTimeAgo = (dateStr: string) => {
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
  };

  const formatTimeUntil = (dateStr: string) => {
    const diffMs = new Date(dateStr).getTime() - Date.now();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    if (diffMins < 1) return 'now';
    if (diffMins < 60) return `in ${diffMins}m`;
    return `in ${diffHours}h ${diffMins % 60}m`;
  };

  const lastSync = syncHistory?.last_successful_sync;
  const lastSyncRelative = lastSync ? formatTimeAgo(lastSync) : 'Never';

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
        <Text>Data {statusLabel} · {lastSyncRelative}</Text>
      </HStack>
      
      {showDetails && (
        <>
          <Box position="fixed" inset={0} zIndex={40} onClick={() => setShowDetails(false)} />
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
            minW="220px"
            zIndex={50}
          >
            <HStack gap={tokens.spacing.xs} fontWeight="600" mb={tokens.spacing.sm}>
              <Box w="8px" h="8px" borderRadius="50%" bg={color} />
              <Text>Data {statusLabel}</Text>
            </HStack>
            
            <VStack align="stretch" gap={tokens.spacing.xs}>
              <HStack justify="space-between">
                <Text color={tokens.colors.text.muted}>Coverage</Text>
                <Text fontWeight="500" color={color}>{fresh_count}/{total_stocks} ({fresh_percentage.toFixed(0)}%)</Text>
              </HStack>
              <HStack justify="space-between">
                <Text color={tokens.colors.text.muted}>Last sync</Text>
                <Text fontWeight="500">{lastSyncRelative}</Text>
              </HStack>
              <HStack justify="space-between">
                <Text color={tokens.colors.text.muted}>Next sync</Text>
                <Text fontWeight="500">{syncHistory?.next_scheduled_sync ? formatTimeUntil(syncHistory.next_scheduled_sync) : '—'}</Text>
              </HStack>
              {syncHistory && syncHistory.total_syncs > 0 && (
                <HStack justify="space-between" mt={tokens.spacing.xs} pt={tokens.spacing.xs} borderTop="1px solid" borderColor="gray.600">
                  <Text color={tokens.colors.text.muted}>24h syncs</Text>
                  <Text fontWeight="500">{syncHistory.successful_syncs}/{syncHistory.total_syncs} OK</Text>
                </HStack>
              )}
            </VStack>

            {fresh_percentage < 80 && (
              <Box mt={tokens.spacing.sm} p={tokens.spacing.sm} bg="yellow.900" borderRadius={tokens.radii.sm} fontSize="11px" color="yellow.200">
                Data may be outdated. Check Data Management.
              </Box>
            )}
          </Box>
        </>
      )}
    </Box>
  );
}
