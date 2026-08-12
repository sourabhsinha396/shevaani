"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  credits: number;
  refresh: () => Promise<void>;
  signIn: (
    email: string,
    password: string,
    recaptchaToken?: string,
  ) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = React.createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [credits, setCredits] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const router = useRouter();

  const refresh = React.useCallback(async () => {
    try {
      const me = await api.me();
      setUser(me);
      const { balance } = await api.creditBalance();
      setCredits(balance);
    } catch (error) {
      // A 401 here is the normal signed-out case, not a failure worth surfacing.
      if (!(error instanceof ApiError && error.status === 401)) {
        console.error("Failed to load session", error);
      }
      setUser(null);
      setCredits(0);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = React.useCallback(
    async (email: string, password: string, recaptchaToken?: string) => {
      await api.login({ email, password, recaptcha_token: recaptchaToken });
      await refresh();
    },
    [refresh],
  );

  const signOut = React.useCallback(async () => {
    await api.logout();
    setUser(null);
    setCredits(0);
    router.push("/");
    router.refresh();
  }, [router]);

  const value = React.useMemo(
    () => ({ user, loading, credits, refresh, signIn, signOut }),
    [user, loading, credits, refresh, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
