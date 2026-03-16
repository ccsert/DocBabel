import { useEffect, useState, type ReactNode } from 'react';
import { authApi } from './api';
import { AuthContext, type User } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const initialToken = localStorage.getItem('token');
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(initialToken);
  const [loading, setLoading] = useState(Boolean(initialToken));

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;

    authApi.me()
      .then((res) => {
        if (!cancelled) {
          setUser(res.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setToken(null);
          localStorage.removeItem('token');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = async (username: string, password: string) => {
    const res = await authApi.login(username, password);
    const t = res.data.access_token;
    localStorage.setItem('token', t);
    setToken(t);
    const me = await authApi.me();
    setUser(me.data);
  };

  const register = async (username: string, email: string, password: string) => {
    await authApi.register(username, email, password);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isAdmin: user?.role === 'admin', loading }}>
      {children}
    </AuthContext.Provider>
  );
}
