import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Box, Flex, Text, IconButton, VStack } from '@chakra-ui/react';
import { DataIntegrityIndicator } from './DataIntegrityBanner';

const MenuIcon = () => <Text fontSize="lg">☰</Text>;
const CloseIcon = () => <Text fontSize="lg">✕</Text>;
const HomeIcon = () => <Text fontSize="sm">🏠</Text>;
const ChartIcon = () => <Text fontSize="sm">📊</Text>;
const CalendarIcon = () => <Text fontSize="sm">📅</Text>;
const BellIcon = () => <Text fontSize="sm">🔔</Text>;
const SettingsIcon = () => <Text fontSize="sm">⚙️</Text>;

const navLinks = [
  { to: '/', label: 'Dashboard', icon: <HomeIcon /> },
  { to: '/getting-started', label: 'Kom igång', icon: <ChartIcon /> },
  { to: '/strategies/momentum', label: 'Momentum', icon: <ChartIcon /> },
  { to: '/strategies/value', label: 'Värde', icon: <ChartIcon /> },
  { to: '/strategies/dividend', label: 'Utdelning', icon: <ChartIcon /> },
  { to: '/strategies/quality', label: 'Kvalitet', icon: <ChartIcon /> },
  { to: '/rebalancing', label: 'Min Strategi', icon: <CalendarIcon /> },
  { to: '/portfolio/my', label: 'Portfölj', icon: <ChartIcon /> },
  { to: '/portfolio/analysis', label: 'Analys', icon: <ChartIcon /> },
  { to: '/learn', label: 'Lär dig mer', icon: <ChartIcon /> },
  { to: '/data', label: 'Data', icon: <ChartIcon /> },
  { to: '/alerts', label: 'Notiser', icon: <BellIcon /> },
  { to: '/settings', label: 'Inställningar', icon: <SettingsIcon /> },
];

const mobileLinks = [
  { to: '/', label: 'Hem', icon: <HomeIcon /> },
  { to: '/strategies/momentum', label: 'Strategier', icon: <ChartIcon /> },
  { to: '/rebalancing', label: 'Rebalans', icon: <CalendarIcon /> },
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
