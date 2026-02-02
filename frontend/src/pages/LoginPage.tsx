import { useState } from 'react';
import { Box, Flex, Text, VStack, Input, Button, HStack } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

export function LoginPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password, inviteCode, name || undefined);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Flex minH="100vh" align="center" justify="center" bg="bg">
      <Box
        bg="bg.subtle"
        borderColor="border"
        borderWidth="1px"
        borderRadius="xl"
        p="40px"
        w="100%"
        maxW="400px"
        boxShadow="xl"
      >
        <VStack gap="24px" align="stretch">
          <VStack gap="8px">
            <Text fontSize="2xl" fontWeight="bold" color="fg">
              Börslabbet
            </Text>
            <Text fontSize="sm" color="fg.muted">
              {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
            </Text>
          </VStack>

          <form onSubmit={handleSubmit}>
            <VStack gap="16px" align="stretch">
              {mode === 'register' && (
                <Box>
                  <Text fontSize="sm" color="fg.muted" mb="4px">Name</Text>
                  <Input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Your name"
                    bg="bg.muted"
                    borderColor="border"
                    color="fg"
                    _placeholder={{ color: 'fg.subtle' }}
                  />
                </Box>
              )}
              
              <Box>
                <Text fontSize="sm" color="fg.muted" mb="4px">Email</Text>
                <Input
                  type="email"
                  name="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  bg="bg.muted"
                  borderColor="border"
                  color="fg"
                  _placeholder={{ color: 'fg.subtle' }}
                />
              </Box>
              
              <Box>
                <Text fontSize="sm" color="fg.muted" mb="4px">Password</Text>
                <Input
                  type="password"
                  name="password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  bg="bg.muted"
                  borderColor="border"
                  color="fg"
                  _placeholder={{ color: 'fg.subtle' }}
                />
              </Box>
              
              {mode === 'register' && (
                <Box>
                  <Text fontSize="sm" color="fg.muted" mb="4px">Invite Code</Text>
                  <Input
                    type="text"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)}
                    placeholder="Enter invite code"
                    required
                    bg="bg.muted"
                    borderColor="border"
                    color="fg"
                    _placeholder={{ color: 'fg.subtle' }}
                  />
                  <Text fontSize="xs" color="fg.subtle" mt="4px">
                    Ask an existing user for their invite code
                  </Text>
                </Box>
              )}

              {error && (
                <Text fontSize="sm" color="error.fg" textAlign="center">
                  {error}
                </Text>
              )}

              <Button
                type="submit"
                bg="brand.solid"
                color="white"
                _hover={{ bg: 'brand.emphasized' }}
                loading={loading}
                w="100%"
              >
                {mode === 'login' ? 'Sign In' : 'Create Account'}
              </Button>
            </VStack>
          </form>

          <HStack justify="center" gap="4px">
            <Text fontSize="sm" color="fg.muted">
              {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
            </Text>
            <Button
              variant="ghost"
              size="sm"
              color="brand.fg"
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
            >
              {mode === 'login' ? 'Register' : 'Sign In'}
            </Button>
          </HStack>
        </VStack>
      </Box>
    </Flex>
  );
}
