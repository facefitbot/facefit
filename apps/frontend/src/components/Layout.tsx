import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Bot,
  Brain,
  Database,
  FileText,
  Home,
  Images,
  Link as LinkIcon,
  LogOut,
  Megaphone,
  MessageSquareText,
  Settings,
  Sparkles,
  Tags,
  ShieldCheck,
  Users,
  Gauge
} from "lucide-react";

import { Button } from "./ui";
import { useAuthStore } from "../shared/authStore";
import { apiRequest } from "../api/client";
import { useQuery } from "@tanstack/react-query";

const links = [
  { to: "/admin/dashboard", label: "Dashboard", icon: Home, minRole: "viewer" },
  { to: "/admin/crm", label: "CRM", icon: Users, minRole: "manager" },
  { to: "/admin/bases", label: "Базы", icon: Database, minRole: "manager" },
  { to: "/admin/broadcasts", label: "Рассылки", icon: Megaphone, minRole: "manager" },
  { to: "/admin/leads", label: "Пользователи", icon: Users, minRole: "admin" },
  { to: "/admin/analysis", label: "Анализы", icon: Images, minRole: "admin" },
  { to: "/admin/reports", label: "Отчеты", icon: FileText, minRole: "admin" },
  { to: "/admin/links", label: "Ссылки", icon: LinkIcon, minRole: "admin" },
  { to: "/admin/ai-performance", label: "AI latency", icon: Gauge, minRole: "admin" },
  { to: "/admin/campaigns", label: "UTM", icon: Tags, minRole: "admin" },
  { to: "/admin/knowledge", label: "База знаний", icon: Brain, minRole: "owner" },
  { to: "/admin/prompts", label: "Промпты", icon: MessageSquareText, minRole: "owner" },
  { to: "/admin/settings", label: "Настройки", icon: Settings, minRole: "owner" },
  { to: "/admin/managers", label: "Менеджеры", icon: ShieldCheck, minRole: "admin" }
];

const roleLevels: Record<string, number> = { viewer: 0, manager: 1, admin: 2, owner: 3 };

export function Layout() {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: () => apiRequest<any>("/api/auth/me") });
  const visibleLinks = links.filter((link) => (roleLevels[me?.role || "owner"] ?? 3) >= roleLevels[link.minRole]);
  return (
    <div className="min-h-screen overflow-x-hidden bg-milk text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-pearl bg-white/75 p-5 backdrop-blur lg:block">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-card bg-rose text-white">
            <Sparkles size={21} />
          </div>
          <div>
            <p className="font-bold">Bella Vladi</p>
            <p className="text-xs text-clay">Face Protocol Admin</p>
          </div>
        </div>
        <nav className="mt-8 space-y-1">
          {visibleLinks.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `flex h-11 items-center gap-3 rounded-card px-3 text-sm font-semibold transition ${
                    isActive ? "bg-pearl text-ink" : "text-clay hover:bg-milk"
                  }`
                }
              >
                <Icon size={18} />
                {link.label}
              </NavLink>
            );
          })}
        </nav>
      </aside>
      <main className="min-w-0 overflow-x-hidden lg:pl-72">
        <header className="sticky top-0 z-20 flex min-h-16 items-center justify-between gap-3 border-b border-pearl bg-milk/88 px-3 py-3 backdrop-blur sm:px-5">
          <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-clay">
            <Bot size={18} />
            <span className="truncate">{me?.name || me?.email || "Production-ready MVP"}</span>
          </div>
          <Button
            className="shrink-0 px-3 sm:px-4"
            variant="ghost"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOut size={17} />
            Выйти
          </Button>
        </header>
        <nav className="sticky top-16 z-10 flex gap-2 overflow-x-auto border-b border-pearl bg-milk/92 px-3 py-2 backdrop-blur lg:hidden">
          {visibleLinks.map((link) => {
            const Icon = link.icon;
            return (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `inline-flex h-10 shrink-0 items-center gap-2 rounded-card px-3 text-sm font-semibold transition ${
                    isActive ? "bg-pearl text-ink" : "text-clay hover:bg-white"
                  }`
                }
              >
                <Icon size={16} />
                {link.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="mx-auto w-full max-w-7xl min-w-0 p-3 sm:p-5 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export function MiniChartIcon() {
  return <BarChart3 size={20} />;
}
