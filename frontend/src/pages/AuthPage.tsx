import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { ApiError, login, register } from "../api";
import { ErrorMessage } from "../components/ErrorMessage";
import { browserTimeZone } from "../dates";

const inputClass = "input";
const buttonClass = "btn";

export type AuthMode = "login" | "register";

// Режим можно вести снаружи (лендинг переключает форму на регистрацию кнопкой «Начать»)
export function AuthPage({
  mode: outerMode,
  onModeChange,
}: {
  mode?: AuthMode;
  onModeChange?: (mode: AuthMode) => void;
} = {}) {
  const client = useQueryClient();
  const [innerMode, setInnerMode] = useState<AuthMode>("login");
  const mode = outerMode ?? innerMode;
  const setMode = onModeChange ?? setInnerMode;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const auth = useMutation({
    mutationFn: async () => {
      if (mode === "login") return login(email, password);
      const zone = browserTimeZone();
      try {
        return await register(email, password, zone);
      } catch (error) {
        // браузерное имя пояса, которого нет в tzdata сервера, не должно ломать регистрацию:
        // повторяем без него (сервер возьмёт пояс по умолчанию), пояс можно сменить в профиле
        if (zone !== null && error instanceof ApiError && error.status === 422) {
          return register(email, password, null);
        }
        throw error;
      }
    },
    onSuccess: (user) => client.setQueryData(["me"], user),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    auth.mutate();
  }

  return (
    <form id="auth" className="space-y-4 card" onSubmit={submit}>
      <h2 className="text-xl font-semibold">{mode === "login" ? "Вход" : "Регистрация"}</h2>
      <div>
        <label htmlFor="email" className="mb-1 block font-semibold">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          className={inputClass}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="password" className="mb-1 block font-semibold">
          Пароль
        </label>
        <input
          id="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          required
          minLength={8}
          className={inputClass}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" className={buttonClass} data-testid="auth-submit">
          {mode === "login" ? "Войти" : "Зарегистрироваться"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            auth.reset();
            setMode(mode === "login" ? "register" : "login");
          }}
        >
          {mode === "login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}
        </button>
      </div>
      <ErrorMessage error={auth.error} />
    </form>
  );
}
