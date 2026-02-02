import { Box, VStack, HStack, Text, Input } from '@chakra-ui/react';
import { useState, useEffect } from 'react';

interface ThemeSettings {
  mode: 'dark' | 'light' | 'auto';
  accentColor: string;
  portfolioName: string;
}

const DEFAULT_THEME: ThemeSettings = {
  mode: 'dark',
  accentColor: '#3182ce',
  portfolioName: '',
};

const ACCENT_COLORS = [
  { color: '#3182ce', name: 'Blå' },
  { color: '#38a169', name: 'Grön' },
  { color: '#805ad5', name: 'Lila' },
  { color: '#dd6b20', name: 'Orange' },
  { color: '#e53e3e', name: 'Röd' },
  { color: '#d69e2e', name: 'Guld' },
];

export function ThemeCustomization() {
  const [theme, setTheme] = useState<ThemeSettings>(DEFAULT_THEME);
  
  useEffect(() => {
    const saved = localStorage.getItem('theme_settings');
    if (saved) setTheme(JSON.parse(saved));
  }, []);
  
  const updateTheme = (updates: Partial<ThemeSettings>) => {
    const updated = { ...theme, ...updates };
    setTheme(updated);
    localStorage.setItem('theme_settings', JSON.stringify(updated));
  };

  return (
    <Box bg="bg" borderRadius="8px" p="16px" borderWidth="1px" borderColor="border">
      <Text fontSize="sm" fontWeight="semibold" mb="12px">🎨 Utseende</Text>
      <VStack gap="16px" align="stretch">
        {/* Theme mode */}
        <Box>
          <Text fontSize="xs" color="fg.muted" mb="8px">Tema</Text>
          <HStack gap="8px">
            {(['dark', 'light', 'auto'] as const).map(mode => (
              <Box
                key={mode}
                px="12px"
                py="6px"
                bg={theme.mode === mode ? 'blue.600' : 'bg.subtle'}
                color={theme.mode === mode ? 'white' : 'fg.muted'}
                borderRadius="6px"
                cursor="pointer"
                fontSize="sm"
                onClick={() => updateTheme({ mode })}
                transition="all 0.15s"
              >
                {mode === 'dark' ? '🌙 Mörkt' : mode === 'light' ? '☀️ Ljust' : '🔄 Auto'}
              </Box>
            ))}
          </HStack>
        </Box>
        
        {/* Accent color */}
        <Box>
          <Text fontSize="xs" color="fg.muted" mb="8px">Accentfärg</Text>
          <HStack gap="8px">
            {ACCENT_COLORS.map(c => (
              <Box
                key={c.color}
                w="32px"
                h="32px"
                bg={c.color}
                borderRadius="full"
                cursor="pointer"
                borderWidth="3px"
                borderColor={theme.accentColor === c.color ? 'white' : 'transparent'}
                onClick={() => updateTheme({ accentColor: c.color })}
                title={c.name}
                transition="all 0.15s"
                _hover={{ transform: 'scale(1.1)' }}
              />
            ))}
          </HStack>
        </Box>
        
        {/* Portfolio nickname */}
        <Box>
          <Text fontSize="xs" color="fg.muted" mb="8px">Portföljnamn</Text>
          <Input
            placeholder="Min portfölj"
            value={theme.portfolioName}
            onChange={e => updateTheme({ portfolioName: e.target.value })}
            size="sm"
            bg="bg.subtle"
            maxLength={20}
          />
        </Box>
      </VStack>
    </Box>
  );
}
