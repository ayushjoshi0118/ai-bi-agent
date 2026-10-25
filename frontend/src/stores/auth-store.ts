import { create } from "zustand";
import { Organization, User } from "../lib/types";
import { ApiClient } from "../lib/api";

interface AuthState {
  user: User | null;
  organizations: Organization[];
  activeOrg: Organization | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  loadSession: () => Promise<void>;
  setActiveOrg: (org: Organization) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  organizations: [],
  activeOrg: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const res = await ApiClient.login({ email, password });
      localStorage.setItem("access_token", res.tokens.access_token);
      localStorage.setItem("refresh_token", res.tokens.refresh_token);

      const orgs = await ApiClient.getOrganizations();
      const active = orgs[0] || null;
      if (active) {
        localStorage.setItem("active_org_id", active.id);
      }

      set({
        user: res.user,
        organizations: orgs,
        activeOrg: active,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
      throw err;
    }
  },

  signup: async (email, password, fullName) => {
    set({ isLoading: true, error: null });
    try {
      const res = await ApiClient.signup({ email, password, full_name: fullName });
      localStorage.setItem("access_token", res.tokens.access_token);
      localStorage.setItem("refresh_token", res.tokens.refresh_token);

      const orgs = await ApiClient.getOrganizations();
      const active = orgs[0] || null;
      if (active) {
        localStorage.setItem("active_org_id", active.id);
      }

      set({
        user: res.user,
        organizations: orgs,
        activeOrg: active,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err: any) {
      set({ error: err.message, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("active_org_id");
    set({
      user: null,
      organizations: [],
      activeOrg: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  loadSession: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }

    try {
      const [user, orgs] = await Promise.all([
        ApiClient.getMe(),
        ApiClient.getOrganizations(),
      ]);

      const savedOrgId = localStorage.getItem("active_org_id");
      const active = orgs.find((o) => o.id === savedOrgId) || orgs[0] || null;
      if (active) {
        localStorage.setItem("active_org_id", active.id);
      }

      set({
        user,
        organizations: orgs,
        activeOrg: active,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  setActiveOrg: (org) => {
    localStorage.setItem("active_org_id", org.id);
    set({ activeOrg: org });
    // Reload page to re-fetch org-scoped data
    if (typeof window !== "undefined") {
      window.location.reload();
    }
  },
}));
