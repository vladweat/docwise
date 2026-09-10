"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  ApiRequestError,
  fetchMe,
  login,
  loginWithGoogle,
  logout as apiLogout,
  register,
  switchOrganization,
} from "@/lib/api";
import { clearLegacyAuth } from "@/lib/auth-storage";
import { resetClientSessionState } from "@/lib/reset-client-state";
import type { UserResponse } from "@/types/auth";

interface AuthContextValue {
  user: UserResponse | null;
  loading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, organizationName: string, inviteToken?: string) => Promise<void>;
  loginGoogle: (idToken: string, extras?: { organization_name?: string }) => Promise<void>;
  switchOrganization: (organizationId: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const userIdRef = useRef<string | null>(null);
  const orgIdRef = useRef<string | null>(null);

  const applyUser = useCallback(
    (next: UserResponse | null) => {
      const nextId = next?.id ?? null;
      const nextOrg = next?.organization_id ?? null;
      if (userIdRef.current !== nextId || orgIdRef.current !== nextOrg) {
        resetClientSessionState(queryClient);
        userIdRef.current = nextId;
        orgIdRef.current = nextOrg;
      }
      setUser(next);
    },
    [queryClient],
  );

  const refreshUser = useCallback(async () => {
    try {
      const me = await fetchMe();
      applyUser(me);
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        applyUser(null);
      }
    }
  }, [applyUser]);

  useEffect(() => {
    let cancelled = false;
    clearLegacyAuth();

    const boot = async () => {
      for (let attempt = 0; attempt < 8; attempt += 1) {
        if (cancelled) return;
        try {
          const me = await fetchMe();
          if (!cancelled) applyUser(me);
          return;
        } catch (err) {
          if (err instanceof ApiRequestError && err.status === 401) {
            if (!cancelled) applyUser(null);
            return;
          }
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
    };

    boot().finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [applyUser]);

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const me = await login({ email, password });
        applyUser(me);
      } catch (err) {
        const message = err instanceof ApiRequestError ? err.message : "Login failed";
        setError(message);
        throw err;
      }
    },
    [applyUser],
  );

  const handleRegister = useCallback(
    async (email: string, password: string, organizationName: string, inviteToken?: string) => {
      setError(null);
      try {
        const me = await register({
          email,
          password,
          organization_name: inviteToken ? undefined : organizationName,
          invite_token: inviteToken || undefined,
        });
        applyUser(me);
      } catch (err) {
        const message = err instanceof ApiRequestError ? err.message : "Registration failed";
        setError(message);
        throw err;
      }
    },
    [applyUser],
  );

  const handleGoogleLogin = useCallback(
    async (idToken: string, extras: { organization_name?: string } = {}) => {
      setError(null);
      try {
        const me = await loginWithGoogle(idToken, extras);
        applyUser(me);
      } catch (err) {
        const message = err instanceof ApiRequestError ? err.message : "Google login failed";
        setError(message);
        throw err;
      }
    },
    [applyUser],
  );

  const handleSwitchOrganization = useCallback(
    async (organizationId: string) => {
      setError(null);
      const me = await switchOrganization(organizationId);
      applyUser(me);
    },
    [applyUser],
  );

  const handleLogout = useCallback(async () => {
    await apiLogout();
    applyUser(null);
    setError(null);
  }, [applyUser]);

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      isAuthenticated: user !== null,
      login: handleLogin,
      register: handleRegister,
      loginGoogle: handleGoogleLogin,
      switchOrganization: handleSwitchOrganization,
      logout: handleLogout,
      refreshUser,
      clearError: () => setError(null),
    }),
    [user, loading, error, handleLogin, handleRegister, handleGoogleLogin, handleSwitchOrganization, handleLogout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
