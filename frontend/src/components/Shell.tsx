import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { NavLink } from "react-router";
import { logout, type User } from "../api";
import {
  BookIcon,
  FlagIcon,
  FlameIcon,
  LogoutIcon,
  MoonIcon,
  SparkIcon,
  SunIcon,
  UserIcon,
} from "../Icons";
import { useTheme } from "../theme";
import { ProgressWidget, useProgress } from "./Progress";

export function Shell({ user, children }: { user: User; children: ReactNode }) {
  const client = useQueryClient();
  const out = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      client.clear();
      return client.invalidateQueries({ queryKey: ["me"] });
    },
  });
  const [theme, toggleTheme] = useTheme();
  const progress = useProgress();
  return (
    <div className="space-y-6">
      <header className="card flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-lg font-bold text-[var(--accent-fg)]"
          >
            {user.email.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p data-testid="whoami" className="min-w-0 truncate font-semibold">
              {user.email}
            </p>
            {progress.data && (
              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                <span className="badge" data-testid="level">
                  Уровень {progress.data.level}
                </span>
                <span className="badge">
                  <FlameIcon />
                  <span data-testid="streak">Серия: {progress.data.streak} дн.</span>
                </span>
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="theme-toggle"
            className="btn-ghost"
            onClick={toggleTheme}
          >
            {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
          </button>
          <button type="button" className="btn-ghost" onClick={() => out.mutate()}>
            <LogoutIcon />
            Выйти
          </button>
        </div>
      </header>
      <ProgressWidget />
      <nav aria-label="Разделы" className="nav m-0">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end className="nav-link">
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>
      {children}
      <p className="border-t border-[var(--border)] pt-3 text-sm muted" data-testid="disclaimer">
        Kognis — не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните 112.
      </p>
    </div>
  );
}

const NAV = [
  { to: "/", label: "Дневник", Icon: BookIcon },
  { to: "/day", label: "Итог дня", Icon: SunIcon },
  { to: "/analysis", label: "Разбор", Icon: SparkIcon },
  { to: "/quests", label: "Квесты", Icon: FlagIcon },
  { to: "/profile", label: "Профиль", Icon: UserIcon },
];
