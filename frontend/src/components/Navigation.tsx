import { NavLink } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Box, Flex, Text, IconButton, VStack } from '@chakra-ui/react';
import { DataIntegrityIndicator } from './DataIntegrityBanner';
import { useAuth } from '../contexts/AuthContext';

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
const SettingsIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>
  </svg>
);
const DataIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
  </svg>
);

const navLinks = [
  { to: '/', label: 'Portfölj', icon: <HomeIcon /> },
  { to: '/settings', label: 'Inställningar', icon: <SettingsIcon /> },
];

const mobileLinks = [
  { to: '/', label: 'Portfölj', icon: <HomeIcon /> },
  { to: '/settings', label: 'Inställningar', icon: <SettingsIcon /> },
];

export function Navigation() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const isAdmin = user?.is_admin ?? false;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark');
  }, []);

  return (
    <>
      {/* Desktop Sidebar */}
      <Box
        as="nav"
        display={{ base: 'none', lg: 'flex' }}
        flexDirection="column"
        position="fixed"
        left="0"
        top="0"
        bottom="0"
        w="240px"
        bg="bg.subtle"
        borderRightWidth="1px"
        borderColor="border"
        p="16px"
        zIndex="100"
      >
        <Flex align="center" gap="12px" mb="32px" px="8px">
          <Box w="32px" h="32px" borderRadius="8px" bg="brand.solid" display="flex" alignItems="center" justifyContent="center">
            <Text fontSize="lg" fontWeight="bold" color="white">B</Text>
          </Box>
          <Text fontSize="lg" fontWeight="bold" color="fg">Börslabbet</Text>
        </Flex>

        <VStack gap="4px" align="stretch" flex="1">
          {navLinks.map(link => (
            <NavLink key={link.to} to={link.to}>
              {({ isActive }) => (
                <Flex
                  align="center"
                  gap="12px"
                  px="16px"
                  py="10px"
                  borderRadius="8px"
                  bg={isActive ? 'brand.solid' : 'transparent'}
                  color={isActive ? 'white' : 'fg.muted'}
                  _hover={{ bg: isActive ? 'brand.solid' : 'bg.muted' }}
                  transition="all 150ms"
                >
                  {link.icon}
                  <Text fontSize="sm" fontWeight="medium">{link.label}</Text>
                </Flex>
              )}
            </NavLink>
          ))}

          {isAdmin && (
            <NavLink to="/data">
              {({ isActive }) => (
                <Flex
                  align="center"
                  gap="12px"
                  px="16px"
                  py="10px"
                  borderRadius="8px"
                  bg={isActive ? 'brand.solid' : 'transparent'}
                  color={isActive ? 'white' : 'fg.muted'}
                  _hover={{ bg: isActive ? 'brand.solid' : 'bg.muted' }}
                  transition="all 150ms"
                >
                  <DataIcon />
                  <Text fontSize="sm" fontWeight="medium">Data</Text>
                </Flex>
              )}
            </NavLink>
          )}
        </VStack>

        <Box mt="auto" pt="16px" borderTopWidth="1px" borderColor="border">
          <DataIntegrityIndicator />
          <Flex align="center" gap="8px" px="8px" mt="12px">
            <Box w="28px" h="28px" borderRadius="full" bg="brand.solid/20" display="flex" alignItems="center" justifyContent="center">
              <Text fontSize="xs" fontWeight="bold" color="brand.fg">{user?.email?.[0]?.toUpperCase() || 'U'}</Text>
            </Box>
            <Text fontSize="xs" color="fg.muted" flex="1" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap">{user?.email}</Text>
            <Box as="button" onClick={logout} color="fg.subtle" _hover={{ color: 'fg.muted' }} title="Logga ut">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </Box>
          </Flex>
        </Box>
      </Box>

      {/* Mobile Header */}
      <Box
        display={{ base: 'flex', lg: 'none' }}
        position="fixed"
        top="0"
        left="0"
        right="0"
        h="56px"
        bg="bg.subtle"
        borderBottomWidth="1px"
        borderColor="border"
        px="16px"
        alignItems="center"
        justifyContent="space-between"
        zIndex="100"
      >
        <Flex align="center" gap="8px">
          <Box w="28px" h="28px" borderRadius="6px" bg="brand.solid" display="flex" alignItems="center" justifyContent="center">
            <Text fontSize="md" fontWeight="bold" color="white">B</Text>
          </Box>
          <Text fontSize="md" fontWeight="bold" color="fg">Börslabbet</Text>
        </Flex>
        <IconButton
          aria-label="Menu"
          variant="ghost"
          size="sm"
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? <CloseIcon /> : <MenuIcon />}
        </IconButton>
      </Box>

      {/* Mobile Menu Overlay */}
      {menuOpen && (
        <Box
          display={{ base: 'block', lg: 'none' }}
          position="fixed"
          top="56px"
          left="0"
          right="0"
          bottom="0"
          bg="bg"
          zIndex="99"
          p="16px"
        >
          <VStack gap="8px" align="stretch">
            {navLinks.map(link => (
              <NavLink key={link.to} to={link.to} onClick={() => setMenuOpen(false)}>
                {({ isActive }) => (
                  <Flex
                    align="center"
                    gap="12px"
                    px="16px"
                    py="12px"
                    borderRadius="8px"
                    bg={isActive ? 'brand.solid' : 'transparent'}
                    color={isActive ? 'white' : 'fg'}
                  >
                    {link.icon}
                    <Text fontSize="md" fontWeight="medium">{link.label}</Text>
                  </Flex>
                )}
              </NavLink>
            ))}
            {isAdmin && (
              <NavLink to="/data" onClick={() => setMenuOpen(false)}>
                {({ isActive }) => (
                  <Flex
                    align="center"
                    gap="12px"
                    px="16px"
                    py="12px"
                    borderRadius="8px"
                    bg={isActive ? 'brand.solid' : 'transparent'}
                    color={isActive ? 'white' : 'fg'}
                  >
                    <DataIcon />
                    <Text fontSize="md" fontWeight="medium">Data</Text>
                  </Flex>
                )}
              </NavLink>
            )}
            <Box pt="16px" borderTopWidth="1px" borderColor="border" mt="8px">
              <Flex align="center" justify="space-between" px="16px">
                <Text fontSize="sm" color="fg.muted">{user?.email}</Text>
                <Box as="button" onClick={logout} color="fg.subtle" _hover={{ color: 'fg.muted' }}>
                  <Text fontSize="sm">Logga ut</Text>
                </Box>
              </Flex>
            </Box>
          </VStack>
        </Box>
      )}

      {/* Mobile Bottom Nav */}
      <Box
        display={{ base: 'flex', lg: 'none' }}
        position="fixed"
        bottom="0"
        left="0"
        right="0"
        h="64px"
        bg="bg.subtle"
        borderTopWidth="1px"
        borderColor="border"
        justifyContent="space-around"
        alignItems="center"
        zIndex="100"
        px="8px"
      >
        {mobileLinks.map(link => (
          <NavLink key={link.to} to={link.to}>
            {({ isActive }) => (
              <Flex
                direction="column"
                align="center"
                gap="4px"
                py="8px"
                px="16px"
                color={isActive ? 'brand.fg' : 'fg.muted'}
              >
                {link.icon}
                <Text fontSize="xs">{link.label}</Text>
              </Flex>
            )}
          </NavLink>
        ))}
      </Box>

      {/* Spacer for mobile header */}
      <Box display={{ base: 'block', lg: 'none' }} h="56px" />
    </>
  );
}
