import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { type Entry, openEntry } from "../../api";
import { ErrorMessage } from "../../components/ErrorMessage";
import { decryptText } from "../../privateCrypto";

const inputClass = "input";
const buttonClass = "btn";

export function LockedEntryBody({ entry }: { entry: Entry }) {
  // текст открытой записи живёт только в состоянии компонента — не в кэше запросов
  const [password, setPassword] = useState("");
  const [opened, setOpened] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () => openEntry(entry.id, password),
    onSuccess: (result) => {
      setOpened(result.text);
      setPassword("");
    },
  });

  if (opened !== null) {
    return (
      <>
        <p className="whitespace-pre-wrap" data-testid="opened-text">
          {opened}
        </p>
        <button type="button" className="mt-2 link" onClick={() => setOpened(null)}>
          Скрыть
        </button>
      </>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        open.mutate();
      }}
    >
      <p data-testid="locked-stub">🔒 Запись закрыта замком</p>
      <label htmlFor={`open-${entry.id}`} className="block text-sm">
        Пароль замка
      </label>
      <input
        id={`open-${entry.id}`}
        type="password"
        required
        autoComplete="off"
        className={inputClass}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" className={buttonClass}>
        Открыть
      </button>
      <ErrorMessage error={open.error} />
    </form>
  );
}

export function PrivateEntryBody({ entry }: { entry: Entry }) {
  // расшифровка целиком в браузере; открытый текст — только в состоянии компонента
  const [password, setPassword] = useState("");
  const [opened, setOpened] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () => {
      if (!entry.cipher) throw new Error("В записи нет шифртекста");
      return decryptText(password, entry.cipher);
    },
    onSuccess: (text) => {
      setOpened(text);
      setPassword("");
    },
  });

  if (opened !== null) {
    return (
      <>
        <p className="whitespace-pre-wrap" data-testid="private-text">
          {opened}
        </p>
        <button type="button" className="mt-2 link" onClick={() => setOpened(null)}>
          Скрыть
        </button>
      </>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        open.mutate();
      }}
    >
      <p data-testid="private-stub">🔐 Приватная запись — расшифровывается на этом устройстве</p>
      <label htmlFor={`private-open-${entry.id}`} className="block text-sm">
        Пароль записи
      </label>
      <input
        id={`private-open-${entry.id}`}
        type="password"
        required
        autoComplete="off"
        className={inputClass}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" className={buttonClass}>
        Расшифровать
      </button>
      <ErrorMessage error={open.error} />
    </form>
  );
}
