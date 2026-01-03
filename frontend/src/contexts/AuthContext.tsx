import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  user_id: number;
  email: string;
  name: string;
  is_admin: boolean;
  invite_code: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, inviteCode: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const res = await fetch('/v1/auth/me', { credentials: 'include' });
      const data = await res.json();
      if (data.authenticated) {
        setUser({
          user_id: data.user_id,
          email: data.email,
          name: data.name,
          is_admin: data.is_admin,
          invite_code: data.invite_code,
        });
      }
    } catch {
      // Not authenticated
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const res = await fetch(`/v1/auth/login?email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    setUser({
      user_id: data.user_id,
      email: data.email,
      name: data.name,
      is_admin: data.is_admin,
      invite_code: data.invite_code,
    });
  };

  const register = async (email: string, password: string, inviteCode: string, name?: string) => {
    const params = new URLSearchParams({ email, password, invite_code: inviteCode });
    if (name) params.append('name', name);
    
    const res = await fetch(`/v1/auth/register?${params}`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Registration failed');
    }
    const data = await res.json();
    setUser({
      user_id: data.user_id,
      email: data.email,
      name: data.name,
      is_admin: data.is_admin,
      invite_code: data.invite_code,
    });
  };

  const logout = async () => {
    await fetch('/v1/auth/logout', { method: 'POST', credentials: 'include' });
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
