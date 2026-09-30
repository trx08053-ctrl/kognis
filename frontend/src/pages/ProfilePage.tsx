import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { saveSettings, type User } from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { Achievements } from "../components/Progress";
import { timeZoneNames } from "../dates";

const inputClass = "input";

// смена часового пояса профиля: по нему сервер и интерфейс считают «сегодня»
function TimezoneField({ user }: { user: User }) {
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: (timezone: string) => saveSettings({ timezone }),
    onSuccess: (saved) => {
      client.setQueryData(["me"], saved);
      return client.invalidateQueries({ queryKey: ["progress"] });
    },
  });
  const zones = timeZoneNames(user.timezone);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="timezone" className="font-semibold">
        Часовой пояс
      </label>
      <select
        id="timezone"
        data-testid="timezone-select"
        className={`${inputClass} !w-auto max-w-full`}
        value={user.timezone}
        onChange={(event) => save.mutate(event.target.value)}
      >
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone}
          </option>
        ))}
      </select>
      <ErrorMessage error={save.error} />
    </div>
  );
}

// профиль: настройки (режим Advanced, часовой пояс) и достижения
export function ProfilePage({ user }: { user: User }) {
  const client = useQueryClient();
  // переключатель откликается сразу (локальное состояние); при ошибке сервера возвращаем прежнее
  const [advanced, setAdvanced] = useState(user.advanced === true);
  const mode = useMutation({
    mutationFn: (next: boolean) => saveSettings({ advanced: next }),
    onMutate: (next) => client.setQueryData(["me"], { ...user, advanced: next }),
    onSuccess: (saved) => client.setQueryData(["me"], saved),
    onError: (_error, next) => {
      setAdvanced(!next);
      client.setQueryData(["me"], { ...user, advanced: !next });
    },
  });
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Профиль</h2>
      <section aria-labelledby="settings-title" className="card space-y-3">
        <h3 id="settings-title" className="text-lg font-semibold">
          Настройки
        </h3>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-5 w-5 accent-[var(--accent)]"
            data-testid="advanced-toggle"
            checked={advanced}
            onChange={(event) => {
              setAdvanced(event.target.checked);
              mode.mutate(event.target.checked);
            }}
          />
          Advanced
        </label>
        <p className="text-sm muted">Графики настроения и фильтры записей на странице «Дневник».</p>
        <ErrorMessage error={mode.error} />
        <TimezoneField user={user} />
        <LanguageSwitcher />
      </section>
      <Achievements />
    </div>
  );
}
