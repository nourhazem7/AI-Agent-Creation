import { createContext, useCallback, useEffect, useState, type ReactNode } from "react";
import { fetchMe, login as loginRequest, registerAccount, type LoginPayload, type RegisterPayload } from "../api/auth";
import { getStoredToken, setStoredToken } from "../api/client";
import type { MeResponse } from "../types";

interface AuthContextValue {
  me: MeResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!getStoredToken()) {
      setMe(null);
      setIsLoading(false);
      return;
    }
    try {
      const result = await fetchMe();
      setMe(result);
    } catch {
      setStoredToken(null);
      setMe(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const token = await loginRequest(payload);
      setStoredToken(token);
      await loadMe();
    },
    [loadMe],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const token = await registerAccount(payload);
      setStoredToken(token);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(() => {
    setStoredToken(null);
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider value={{ me, isLoading, isAuthenticated: !!me, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
