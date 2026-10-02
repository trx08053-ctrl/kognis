import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";
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
import { APP_NAME, type Key, useI18n } from "../i18n";
import { useTheme } from "../theme";
import { ProgressWidget, useProgress } from "./Progress";

export function Shell({ user, children }: { user: User; children: ReactNode }) {
  const { t } = useI18n();
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
        <Link
          to="/welcome"
          data-testid="logo"
          aria-label={t("shell.logo")}
          className="text-xl font-bold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
        >
          {APP_NAME}
        </Link>
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
                  {t("shell.level", { level: progress.data.level })}
                </span>
                <span className="badge">
                  <FlameIcon />
                  {progress.data.streak > 0 ? (
                    <span data-testid="streak">
                      {t("shell.streak", { days: progress.data.streak })}
                    </span>
                  ) : (
                    <span data-testid="days-30-badge">
                      {t("shell.days_30", { count: progress.data.days_30 })}
                    </span>
                  )}
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
            {theme === "dark" ? t("shell.theme_light") : t("shell.theme_dark")}
          </button>
          <button type="button" className="btn-ghost" onClick={() => out.mutate()}>
            <LogoutIcon />
            {t("shell.logout")}
          </button>
        </div>
      </header>
      <ProgressWidget />
      <nav aria-label={t("shell.nav")} className="nav m-0">
        {NAV.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} end className="nav-link">
            <Icon />
            {t(label)}
          </NavLink>
        ))}
      </nav>
      {children}
      <p className="border-t border-[var(--border)] pt-3 text-sm muted" data-testid="disclaimer">
        {t("shell.disclaimer")}
      </p>
    </div>
  );
}

const NAV: { to: string; label: Key; Icon: () => ReactNode }[] = [
  { to: "/", label: "shell.nav.diary", Icon: BookIcon },
  { to: "/day", label: "shell.nav.day", Icon: SunIcon },
  { to: "/analysis", label: "shell.nav.analysis", Icon: SparkIcon },
  { to: "/quests", label: "shell.nav.quests", Icon: FlagIcon },
  { to: "/archive", label: "shell.nav.archive", Icon: BookIcon },
  { to: "/profile", label: "shell.nav.profile", Icon: UserIcon },
];
