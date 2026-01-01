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

// Compact indicator for header/nav
export function DataIntegrityIndicator() {
  const [integrity, setIntegrity] = useState<IntegrityCheck | null>(null);

  useEffect(() => {
    api.get<IntegrityCheck>('/data/integrity/quick')
      .then(setIntegrity)
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

  return (
    <HStack gap={tokens.spacing.xs} fontSize={tokens.fontSizes.xs} color={tokens.colors.text.muted}>
      <Box w="8px" h="8px" borderRadius="50%" bg={color} />
      <Text>{label}</Text>
    </HStack>
  );
}
