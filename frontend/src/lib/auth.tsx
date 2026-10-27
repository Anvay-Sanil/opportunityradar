import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { api, ApiError, getErrorMessage } from './api';

interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  email_verified: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  sessionError: string | null;
  retrySession: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retrySession = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    setSessionError(null);
    if (token) {
      setLoading(true);
      api.auth.me()
        .then((currentUser) => { if (active) setUser(currentUser); })
        .catch((error) => {
          if (!active) return;
          if (error instanceof ApiError && error.status === 401) {
            localStorage.removeItem('token');
            setToken(null);
            setUser(null);
          } else {
            setSessionError(getErrorMessage(error));
          }
        })
        .finally(() => { if (active) setLoading(false); });
    } else {
      setUser(null);
      setLoading(false);
    }
    return () => { active = false; };
  }, [token, attempt]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login({ email, password });
    localStorage.setItem('token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (email: string, password: string, full_name: string) => {
    const res = await api.auth.register({ email, password, full_name });
    localStorage.setItem('token', res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
    setSessionError(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, sessionError, retrySession, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
