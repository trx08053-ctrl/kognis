// Мотивация 2.0 (3/4): цифровые герои — спутник и наставники (SVG в едином стиле, светлая и тёмная
// тема, лёгкая анимация только без prefers-reduced-motion). Рядом с кризисным контентом героев нет.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { type Companion, getCompanion, markStageSeen, saveCompanion } from "../api";
import { isKey, type Key, useI18n } from "../i18n";
import { ErrorMessage } from "./ErrorMessage";
import { useOwnedAccessory, useOwnedBackground } from "./Sparks";

const APPEARANCES = ["fox", "owl", "turtle", "whale"] as const;
type Appearance = (typeof APPEARANCES)[number];
const ADDRESSES = ["ty", "vy"] as const;
type Address = (typeof ADDRESSES)[number];
const MAX_NAME = 24;

const BODY: Record<Appearance, string> = {
  fox: "#e07a2f",
  owl: "#8b6b4a",
  turtle: "#3f9b6b",
  whale: "#4a78c9",
};
const INK = "#1e1b3a";

export function useCompanion() {
  return useQuery({ queryKey: ["companion"], queryFn: getCompanion, retry: false });
}

function asAddress(value: string | null | undefined): Address {
  return value === "vy" ? "vy" : "ty";
}

function asAppearance(value: string | null | undefined): Appearance {
  return APPEARANCES.find((a) => a === value) ?? "fox";
}

function Ears({ kind }: { kind: Appearance }) {
  if (kind === "fox") {
    return (
      <>
        <polygon points="34,44 40,14 58,36" fill={BODY.fox} stroke={INK} strokeWidth="2" />
        <polygon points="86,44 80,14 62,36" fill={BODY.fox} stroke={INK} strokeWidth="2" />
      </>
    );
  }
  if (kind === "owl") {
    return (
      <>
        <polygon points="36,40 38,16 54,32" fill={BODY.owl} stroke={INK} strokeWidth="2" />
        <polygon points="84,40 82,16 66,32" fill={BODY.owl} stroke={INK} strokeWidth="2" />
      </>
    );
  }
  if (kind === "turtle") {
    return <ellipse cx="60" cy="38" rx="30" ry="18" fill="#2f7a54" stroke={INK} strokeWidth="2" />;
  }
  return (
    <path
      d="M60 26 q-6 -14 -14 -12 M60 26 q6 -14 14 -12"
      stroke={INK}
      fill="none"
      strokeWidth="2"
    />
  );
}

const ACCESSORIES = ["scarf", "hat", "backpack"] as const;
type Accessory = (typeof ACCESSORIES)[number];
const BACKGROUNDS = ["bg_stars", "bg_forest"] as const;
type Background = (typeof BACKGROUNDS)[number];

// купленные фоны из магазина искр: декор за спутником у любого облика
function BackgroundArt({ kind }: { kind: Background }) {
  if (kind === "bg_stars") {
    return (
      <g data-testid="companion-background">
        <circle cx="24" cy="22" r="1.5" fill="#fbbf24" />
        <circle cx="92" cy="18" r="1.2" fill="#fbbf24" />
        <circle cx="18" cy="86" r="1.6" fill="#e0f2fe" />
        <circle cx="100" cy="78" r="1.3" fill="#e0f2fe" />
        <circle cx="60" cy="12" r="1.1" fill="#fbbf24" />
      </g>
    );
  }
  return (
    <g data-testid="companion-background">
      <path d="M8 104 l20 -26 l16 20 l14 -18 l22 24z" fill="#2f7a54" opacity="0.45" />
      <path d="M60 104 l18 -22 l24 22z" fill="#22a06b" opacity="0.45" />
    </g>
  );
}

// аксессуары из магазина искр: рисуются поверх спутника у любого облика
function AccessoryArt({ kind }: { kind: Accessory }) {
  if (kind === "scarf") {
    return (
      <path
        d="M44 84 q16 8 32 0 l2 8 q-18 8 -36 0z"
        fill="#ef4444"
        stroke={INK}
        strokeWidth="1.5"
        data-testid="companion-accessory"
      />
    );
  }
  if (kind === "hat") {
    return (
      <g data-testid="companion-accessory">
        <path d="M38 40 q22 -26 44 0z" fill="#8b5cf6" stroke={INK} strokeWidth="1.5" />
        <circle cx="60" cy="16" r="4" fill="#fbbf24" stroke={INK} strokeWidth="1.5" />
      </g>
    );
  }
  return (
    <g data-testid="companion-accessory">
      <rect
        x="92"
        y="70"
        width="18"
        height="20"
        rx="4"
        fill="#0ea5e9"
        stroke={INK}
        strokeWidth="1.5"
      />
      <path d="M96 70 v-4 h10 v4" fill="none" stroke={INK} strokeWidth="1.5" />
    </g>
  );
}

// спутник: облик задаёт силуэт, стадия 1…5 добавляет детали (лист, шарф, звезда, сияние) и размер
export function CompanionArt({
  appearance,
  stage,
  label,
  accessory = null,
  background = null,
}: {
  appearance: Appearance;
  stage: number;
  label: string;
  accessory?: string | null;
  background?: string | null;
}) {
  const radius = 24 + stage * 3;
  const worn = ACCESSORIES.find((a) => a === accessory);
  const scene = BACKGROUNDS.find((b) => b === background);
  return (
    <svg
      viewBox="0 0 120 120"
      role="img"
      aria-label={label}
      className="hero-art hero-float"
      data-testid="companion-art"
      data-stage={stage}
      data-accessory={worn ?? "none"}
      data-background={scene ?? "none"}
    >
      {scene && <BackgroundArt kind={scene} />}
      {stage >= 5 && (
        <circle cx="60" cy="64" r="54" fill="none" stroke="#f59e0b" strokeWidth="3" opacity="0.7" />
      )}
      <Ears kind={appearance} />
      <circle cx="60" cy="68" r={radius} fill={BODY[appearance]} stroke={INK} strokeWidth="2" />
      <circle cx="49" cy="64" r="4" fill={INK} />
      <circle cx="71" cy="64" r="4" fill={INK} />
      <path d="M52 78 q8 7 16 0" stroke={INK} strokeWidth="2.5" fill="none" strokeLinecap="round" />
      {stage >= 2 && (
        <path
          d="M60 30 q10 -14 22 -8 q-8 12 -22 8z"
          fill="#22a06b"
          stroke={INK}
          strokeWidth="1.5"
        />
      )}
      {stage >= 3 && (
        <rect
          x="40"
          y="88"
          width="40"
          height="8"
          rx="4"
          fill="#d946ef"
          stroke={INK}
          strokeWidth="1.5"
        />
      )}
      {stage >= 4 && (
        <polygon
          points="96,30 99,38 108,38 101,43 104,52 96,47 88,52 91,43 84,38 93,38"
          fill="#fbbf24"
          stroke={INK}
          strokeWidth="1.2"
        />
      )}
      {worn && <AccessoryArt kind={worn} />}
    </svg>
  );
}

const MENTOR_SHAPES: Record<string, ReactNode> = {
  analyst: (
    <>
      <circle cx="20" cy="20" r="9" fill="none" />
      <line x1="27" y1="27" x2="36" y2="36" />
    </>
  ),
  guide: (
    <>
      <rect x="15" y="16" width="14" height="18" rx="3" fill="none" />
      <path d="M19 16 v-5 h6 v5" fill="none" />
      <line x1="22" y1="34" x2="22" y2="38" />
    </>
  ),
  gardener: (
    <>
      <path d="M22 38 v-16" fill="none" />
      <path d="M22 26 q-12 -2 -12 -14 q12 0 12 14z" fill="none" />
      <path d="M22 22 q12 -2 12 -12 q-12 0 -12 12z" fill="none" />
    </>
  ),
  mechanic: (
    <>
      <circle cx="22" cy="22" r="6" fill="none" />
      <path d="M22 8 v6 M22 30 v6 M8 22 h6 M30 22 h6 M12 12 l4 4 M28 28 l4 4 M32 12 l-4 4 M16 28 l-4 4" />
    </>
  ),
};

export function MentorArt({ code, label }: { code: string; label: string }) {
  return (
    <svg
      viewBox="0 0 44 44"
      role="img"
      aria-label={label}
      className="hero-mentor"
      data-testid="mentor-art"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
    >
      <circle cx="22" cy="22" r="21" fill="var(--accent-soft)" stroke="none" />
      {MENTOR_SHAPES[code]}
    </svg>
  );
}

function useText() {
  const { t } = useI18n();
  // ключи словаря собираются из кодов сервера: неизвестный код — пустая строка, не ошибка
  return (key: string, params?: Record<string, string | number>) =>
    isKey(key) ? t(key as Key, params) : "";
}

// наставник направления: короткая реплика, если направление открыто; при кризисе — ничего
export function MentorLine({ direction, crisis = false }: { direction: string; crisis?: boolean }) {
  const text = useText();
  const companion = useCompanion();
  if (crisis || !companion.data) return null;
  const mentor = companion.data.mentors.find((m) => m.direction === direction && m.unlocked);
  if (!mentor) return null;
  const name = text(`hero.mentor.${mentor.code}.name`);
  return (
    <aside
      className="hero-line card-sm flex items-center gap-3"
      data-testid="mentor-line"
      aria-label={text("hero.mentor.label", { name })}
    >
      <MentorArt code={mentor.code} label={text("hero.mentor.label", { name })} />
      <p>
        <span className="font-semibold">{name}. </span>
        {text(`hero.mentor.${mentor.code}.${asAddress(companion.data.address)}`)}
      </p>
    </aside>
  );
}

function ChooseForm({ onDone, initial }: { onDone: () => void; initial: Companion }) {
  const { t } = useI18n();
  const client = useQueryClient();
  const [appearance, setAppearance] = useState<Appearance>(asAppearance(initial.appearance));
  const [name, setName] = useState(initial.name ?? "");
  const [address, setAddress] = useState<Address>(asAddress(initial.address));
  const save = useMutation({
    mutationFn: saveCompanion,
    onSuccess: (saved) => {
      client.setQueryData(["companion"], saved);
      onDone();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({ appearance, name, address });
  };
  return (
    <form className="space-y-3" onSubmit={submit} data-testid="companion-form">
      <fieldset className="space-y-1">
        <legend className="font-semibold">{t("hero.choose.appearance")}</legend>
        <div className="flex flex-wrap gap-3">
          {APPEARANCES.map((kind) => (
            <label key={kind} className="flex items-center gap-1">
              <input
                type="radio"
                name="appearance"
                checked={appearance === kind}
                onChange={() => setAppearance(kind)}
              />
              {t(`hero.appearance.${kind}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor="companion-name" className="font-semibold">
          {t("hero.choose.name")}
        </label>
        <input
          id="companion-name"
          className="input"
          maxLength={MAX_NAME}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <fieldset className="space-y-1">
        <legend className="font-semibold">{t("hero.choose.address")}</legend>
        <div className="flex flex-wrap gap-3">
          {ADDRESSES.map((form) => (
            <label key={form} className="flex items-center gap-1">
              <input
                type="radio"
                name="address"
                checked={address === form}
                onChange={() => setAddress(form)}
              />
              {t(`hero.choose.${form}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <button type="submit" className="btn" disabled={name.trim() === "" || save.isPending}>
        {t("hero.choose.save")}
      </button>
      <ErrorMessage error={save.error} />
    </form>
  );
}

function Stage({ data }: { data: Companion }) {
  const { t } = useI18n();
  const text = useText();
  const accessory = useOwnedAccessory();
  const background = useOwnedBackground();
  const name = data.name ?? "";
  const title = text(`hero.stage.${data.stage}`);
  return (
    <div className="flex items-center gap-4">
      <CompanionArt
        appearance={asAppearance(data.appearance)}
        stage={data.stage}
        accessory={accessory}
        background={background}
        label={t("hero.art.label", {
          name,
          appearance: text(`hero.appearance.${asAppearance(data.appearance)}`),
          stage: data.stage,
        })}
      />
      <div className="space-y-1">
        <p className="text-lg font-semibold">{name}</p>
        <p className="text-sm muted" data-testid="companion-stage">
          {t("hero.stage.label", { stage: data.stage, title })}
        </p>
        <p className="text-sm muted">{t("hero.days", { count: data.days_total })}</p>
        <p className="text-sm muted">
          {data.days_to_next === null
            ? t("hero.next.max")
            : t("hero.next", { count: data.days_to_next })}
        </p>
        {data.resting && <p className="text-sm">{t("hero.resting", { name })}</p>}
      </div>
    </div>
  );
}

// спутник на главной; `crisis` — на экране есть кризисный контент: ни героя, ни реплики, ни открытки
export function CompanionCard({ crisis = false }: { crisis?: boolean }) {
  const { t } = useI18n();
  const text = useText();
  const companion = useCompanion();
  const [editing, setEditing] = useState(false);
  const [pinned, setPinned] = useState<NonNullable<Companion["line"]> | null>(null);
  const seen = useMutation({ mutationFn: markStageSeen });
  const line = companion.data?.line ?? null;
  useEffect(() => {
    if (crisis || !line) return;
    setPinned((current) => current ?? line);
    if (line.situation === "new_stage") seen.mutate();
  }, [crisis, line, seen.mutate]);
  if (crisis || !companion.data) return null;
  const data = companion.data;
  if (!data.chosen || editing) {
    return (
      <section
        aria-labelledby="companion-title"
        className="card space-y-3"
        data-testid="companion-intro"
      >
        <h2 id="companion-title" className="text-xl font-semibold">
          {t("hero.intro.title")}
        </h2>
        <p>{t("hero.intro.text")}</p>
        <ChooseForm initial={data} onDone={() => setEditing(false)} />
      </section>
    );
  }
  const shown = pinned ?? line;
  const address = asAddress(data.address);
  return (
    <section aria-labelledby="companion-title" className="card space-y-3" data-testid="companion">
      <h2 id="companion-title" className="text-xl font-semibold">
        {t("hero.companion.title")}
      </h2>
      <Stage data={data} />
      {shown && (
        <p className="hero-line" data-testid="companion-line">
          {text(`hero.line.${shown.situation}.${address}`, { name: data.name ?? "" })}
        </p>
      )}
      {data.postcard && (
        <aside className="card-sm space-y-1" data-testid="postcard">
          <p className="font-semibold">{t("hero.postcard.title", { name: data.name ?? "" })}</p>
          <p>{text(`hero.postcard.${data.postcard.code}`)}</p>
        </aside>
      )}
      <button type="button" className="link" onClick={() => setEditing(true)}>
        {t("hero.choose.change")}
      </button>
    </section>
  );
}
