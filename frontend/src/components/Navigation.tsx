import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Box, Flex, Text, IconButton, VStack } from '@chakra-ui/react';
import { DataIntegrityIndicator } from './DataIntegrityBanner';

// SVG Icons
const MenuIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 12h18M3 6h18M3 18h18"/>
  </svg>
);
const CloseIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 6L6 18M6 6l12 12"/>
  </svg>
);
const HomeIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);
const TrendingIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
  </svg>
);
const ValueIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 3v4M8 3v4M12 11v6M9 14h6"/>
  </svg>
);
const DividendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10"/><path d="M12 6v12M8 10l4-4 4 4M8 14l4 4 4-4"/>
  </svg>
);
const QualityIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
  </svg>
);
const StrategyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18M10 4v18"/>
  </svg>
);
const AnalysisIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21 21H3V3"/><path d="M18 9l-5 5-4-4-3 3"/>
  </svg>
);
const LearnIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/>
  </svg>
);
const DataIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
  </svg>
);
const BellIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/>
  </svg>
);
const SettingsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
  </svg>
);
const RocketIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
  </svg>
);

const navLinks = [
  { to: '/', label: 'Dashboard', icon: <HomeIcon /> },
  { to: '/getting-started', label: 'Kom igång', icon: <RocketIcon /> },
  { to: '/rebalancing', label: 'Min Strategi', icon: <StrategyIcon /> },
  { to: '/strategies/momentum', label: 'Momentum', icon: <TrendingIcon /> },
  { to: '/strategies/value', label: 'Värde', icon: <ValueIcon /> },
  { to: '/strategies/dividend', label: 'Utdelning', icon: <DividendIcon /> },
  { to: '/strategies/quality', label: 'Kvalitet', icon: <QualityIcon /> },
  { to: '/backtesting/historical', label: 'Backtest', icon: <AnalysisIcon /> },
  { to: '/learn', label: 'Lär dig mer', icon: <LearnIcon /> },
  { to: '/data', label: 'Data', icon: <DataIcon /> },
  { to: '/alerts', label: 'Notiser', icon: <BellIcon /> },
  { to: '/settings', label: 'Inställningar', icon: <SettingsIcon /> },
];

const mobileLinks = [
  { to: '/', label: 'Hem', icon: <HomeIcon /> },
  { to: '/rebalancing', label: 'Min Strategi', icon: <StrategyIcon /> },
  { to: '/strategies/momentum', label: 'Strategier', icon: <TrendingIcon /> },
  { to: '/alerts', label: 'Notiser', icon: <BellIcon /> },
  { to: '/settings', label: 'Mer', icon: <SettingsIcon /> },
];

export function Navigation() {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
  }, []);

  return (
    <>
      {/* Desktop Sidebar - hidden below lg */}
      <Box
        as="nav"
        position="fixed"
        left={0}
        top={0}
        bottom={0}
        w="240px"
        bg="gray.700"
        borderRight="1px solid"
        borderColor="gray.600"
        hideBelow="lg"
        zIndex={40}
      >
        <Box p="24px" borderBottom="1px solid" borderColor="gray.600">
          <NavLink to="/">
            <Text fontSize="xl" fontWeight="semibold" color="brand.500">Börslabbet</Text>
          </NavLink>
          <Box mt="8px">
            <DataIntegrityIndicator />
          </Box>
        </Box>
        <VStack gap="4px" align="stretch" p="16px">
          {navLinks.map(link => (
            <NavLink key={link.to} to={link.to}>
              {({ isActive }) => (
                <Flex
                  align="center"
                  gap="12px"
                  px="16px"
                  py="10px"
                  borderRadius="8px"
                  bg={isActive ? 'brand.500' : 'transparent'}
                  color={isActive ? 'white' : 'gray.100'}
                  _hover={{ bg: isActive ? 'brand.600' : 'gray.600' }}
                  transition="all 150ms"
                >
                  {link.icon}
                  <Text fontSize="sm" fontWeight="medium">{link.label}</Text>
                </Flex>
              )}
            </NavLink>
          ))}
        </VStack>
      </Box>

      {/* Mobile/Tablet Header - hidden from lg */}
      <Box
        as="header"
        position="sticky"
        top={0}
        bg="gray.700"
        borderBottom="1px solid"
        borderColor="gray.600"
        zIndex={50}
        hideFrom="lg"
      >
        <Flex px="16px" py="12px" align="center" justify="space-between">
          <NavLink to="/">
            <Text fontSize="lg" fontWeight="semibold" color="brand.500">Börslabbet</Text>
          </NavLink>
          <IconButton
            aria-label="Menu"
            variant="ghost"
            size="sm"
            onClick={() => setMenuOpen(true)}
          >
            <MenuIcon />
          </IconButton>
        </Flex>
      </Box>

      {/* Mobile Drawer */}
      {menuOpen && (
        <Box position="fixed" inset={0} zIndex={60} hideFrom="lg">
          <Box position="absolute" inset={0} bg="blackAlpha.600" onClick={() => setMenuOpen(false)} />
          <Box
            position="absolute"
            top={0}
            left={0}
            bottom={0}
            w="280px"
            bg="gray.700"
            borderRight="1px solid"
            borderColor="gray.600"
          >
            <Flex p="24px" borderBottom="1px solid" borderColor="gray.600" justify="space-between" align="center">
              <Text fontSize="lg" fontWeight="semibold" color="brand.500">Börslabbet</Text>
              <IconButton aria-label="Close" variant="ghost" size="sm" onClick={() => setMenuOpen(false)}>
                <CloseIcon />
              </IconButton>
            </Flex>
            <VStack gap="4px" align="stretch" p="16px">
              {navLinks.map(link => (
                <NavLink key={link.to} to={link.to} onClick={() => setMenuOpen(false)}>
                  {({ isActive }) => (
                    <Flex
                      align="center"
                      gap="12px"
                      px="16px"
                      py="10px"
                      borderRadius="8px"
                      bg={isActive ? 'brand.500' : 'transparent'}
                      color={isActive ? 'white' : 'gray.100'}
                      _hover={{ bg: isActive ? 'brand.600' : 'gray.600' }}
                    >
                      {link.icon}
                      <Text fontSize="sm" fontWeight="medium">{link.label}</Text>
                    </Flex>
                  )}
                </NavLink>
              ))}
            </VStack>
          </Box>
        </Box>
      )}

      {/* Mobile Bottom Tab Bar - hidden from md */}
      <Box
        position="fixed"
        bottom={0}
        left={0}
        right={0}
        bg="gray.700"
        borderTop="1px solid"
        borderColor="gray.600"
        zIndex={40}
        hideFrom="md"
      >
        <Flex justify="space-around" py="8px">
          {mobileLinks.map(link => (
            <NavLink key={link.to} to={link.to}>
              {({ isActive }) => (
                <VStack gap="4px" minW="60px" color={isActive ? 'brand.500' : 'gray.200'}>
                  {link.icon}
                  <Text fontSize="xs" fontWeight="medium">{link.label}</Text>
                </VStack>
              )}
            </NavLink>
          ))}
        </Flex>
      </Box>
    </>
  );
}
