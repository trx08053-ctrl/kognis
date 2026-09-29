import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { createEntry } from "../../api";
import { addUnique, ChipToggleGroup, CustomChipInput, splitList } from "../../components/Chips";
import { ErrorMessage } from "../../components/ErrorMessage";
import { HelpPanel } from "../../components/HelpPanel";
import { encryptText, MIN_PRIVATE_PASSWORD } from "../../privateCrypto";

const inputClass = "input";
const buttonClass = "btn";

const EMOTION_DICTIONARY = [
  "радость",
  "спокойствие",
  "благодарность",
  "интерес",
  "надежда",
  "усталость",
  "тревога",
  "грусть",
  "злость",
  "стыд",
  "одиночество",
  "растерянность",
];

type Protection = "plain" | "locked" | "private";

const PROTECTION_HINT: Record<Protection, string> = {
  plain: "Текст хранится на сервере и доступен ИИ-разбору, если вы дали согласие.",
  locked: "Текст закрыт паролем: без пароля его не увидит никто, ИИ его не читает.",
  private: "Текст шифруется на этом устройстве: сервер и ИИ его не прочитают.",
};

const PROTECTION_LABEL: Record<Protection, string> = {
  plain: "Обычная",
  locked: "Под замком",
  private: "Приватная",
};
export function EntryForm() {
  const client = useQueryClient();
  const [text, setText] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [pendingTag, setPendingTag] = useState("");
  const [emotions, setEmotions] = useState<string[]>([]);
  const [pendingEmotion, setPendingEmotion] = useState("");
  const [protection, setProtection] = useState<Protection>("plain");
  const [lockPassword, setLockPassword] = useState("");
  const [privatePassword, setPrivatePassword] = useState("");
  const [privateRepeat, setPrivateRepeat] = useState("");
  const locked = protection === "locked";
  const isPrivate = protection === "private";
  const add = useMutation({
    mutationFn: async () => {
      const labels = {
        tags: addUnique(tags, splitList(pendingTag)),
        emotions: addUnique(emotions, splitList(pendingEmotion)),
      };
      if (!isPrivate) {
        return createEntry({
          text,
          ...labels,
          ...(locked ? { protection: "locked", lock_password: lockPassword } : {}),
        });
      }
      if (privatePassword !== privateRepeat) throw new Error("Пароли не совпадают");
      // шифруем здесь: открытый текст и пароль не покидают устройство
      const cipher = await encryptText(privatePassword, text.trim());
      return createEntry({ text: "", ...labels, protection: "private", cipher });
    },
    onSuccess: () => {
      setText("");
      setTags([]);
      setPendingTag("");
      setEmotions([]);
      setPendingEmotion("");
      setProtection("plain");
      setLockPassword("");
      setPrivatePassword("");
      setPrivateRepeat("");
      void client.invalidateQueries({ queryKey: ["progress"] });
      return client.invalidateQueries({ queryKey: ["entries"] });
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    add.mutate();
  }

  return (
    <form className="space-y-4 card" onSubmit={submit}>
      <h2 className="text-xl font-semibold">Новая запись</h2>
      <div>
        <label htmlFor="text" className="mb-1 block font-semibold">
          Что произошло и что вы чувствуете
        </label>
        <textarea
          id="text"
          required
          rows={4}
          className={inputClass}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
      <ChipToggleGroup
        legend="Как вы себя чувствуете"
        options={addUnique(EMOTION_DICTIONARY, emotions)}
        selected={emotions}
        onToggle={(value) =>
          setEmotions(
            emotions.includes(value) ? emotions.filter((e) => e !== value) : [...emotions, value],
          )
        }
      />
      <CustomChipInput
        id="emotions"
        label="Своя эмоция"
        chips={[]}
        pending={pendingEmotion}
        onPending={setPendingEmotion}
        onCommit={(values) => setEmotions(addUnique(emotions, values))}
        onRemove={() => undefined}
        removeLabel="Убрать эмоцию"
      />
      <CustomChipInput
        id="tags"
        label="Теги"
        chips={tags}
        pending={pendingTag}
        onPending={setPendingTag}
        onCommit={(values) => setTags(addUnique(tags, values))}
        onRemove={(value) => setTags(tags.filter((t) => t !== value))}
        removeLabel="Убрать тег"
      />
      <fieldset className="space-y-2">
        <legend className="mb-1 font-semibold">Защита записи</legend>
        <div className="segmented" role="radiogroup" aria-label="Режим защиты">
          {(Object.keys(PROTECTION_LABEL) as Protection[]).map((value) => (
            <label key={value}>
              <input
                type="radio"
                name="protection"
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                checked={protection === value}
                onChange={() => setProtection(value)}
              />
              {PROTECTION_LABEL[value]}
            </label>
          ))}
        </div>
        <p className="text-sm muted">{PROTECTION_HINT[protection]}</p>
        {isPrivate && (
          <div className="mt-2 space-y-2">
            <p className="notice" data-testid="private-warning">
              Текст зашифруется в браузере, сервер и ИИ его не прочитают. Пароль нигде не хранится и
              восстановить его нельзя: забудете пароль — запись будет потеряна навсегда. Теги,
              эмоции и дата не шифруются — не пишите в них ничего личного.
            </p>
            <label htmlFor="private-password" className="mb-1 block">
              Пароль записи (от {MIN_PRIVATE_PASSWORD} символов)
            </label>
            <input
              id="private-password"
              type="password"
              required
              minLength={MIN_PRIVATE_PASSWORD}
              autoComplete="new-password"
              className={inputClass}
              value={privatePassword}
              onChange={(event) => setPrivatePassword(event.target.value)}
            />
            <label htmlFor="private-repeat" className="mb-1 block">
              Повторите пароль
            </label>
            <input
              id="private-repeat"
              type="password"
              required
              autoComplete="new-password"
              className={inputClass}
              value={privateRepeat}
              onChange={(event) => setPrivateRepeat(event.target.value)}
            />
          </div>
        )}
        {locked && (
          <div className="mt-2">
            <label htmlFor="lock-password" className="mb-1 block">
              Пароль замка (от 8 символов). Забытый пароль восстановить нельзя.
            </label>
            <input
              id="lock-password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className={inputClass}
              value={lockPassword}
              onChange={(event) => setLockPassword(event.target.value)}
            />
          </div>
        )}
      </fieldset>
      <button type="submit" className={buttonClass} data-testid="save-entry">
        Сохранить
      </button>
      <ErrorMessage error={add.error} />
      {add.data?.help && <HelpPanel help={add.data.help} />}
    </form>
  );
}
