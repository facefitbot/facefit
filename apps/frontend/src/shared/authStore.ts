import { create } from "zustand";

type AuthState = {
  token: string | null;
  setToken: (token: string) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem("bella_admin_token"),
  setToken: (token) => {
    localStorage.setItem("bella_admin_token", token);
    set({ token });
  },
  logout: () => {
    localStorage.removeItem("bella_admin_token");
    set({ token: null });
  }
}));

