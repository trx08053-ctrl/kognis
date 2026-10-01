import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { listDayReviews } from "../api";
import { MoodChart } from "../components/Charts";
import { ErrorMessage } from "../components/ErrorMessage";
import { CompanionCard } from "../components/Heroes";
import { useToday } from "../dates";
import { PencilIcon } from "../Icons";
import { EntryForm } from "./home/EntryForm";
import { EntryList } from "./home/EntryList";

const buttonClass = "btn";

const ONBOARDING_KEY = "kognis-onboarded";

// первый вход: короткое объяснение (дисклеймер — в подвале); закрытие запоминается в браузере
function Onboarding() {
  const [hidden, setHidden] = useState(() => {
    try {
      return window.localStorage.getItem(ONBOARDING_KEY) === "1";
    } catch {
      return false;
    }
  });
  if (hidden) return null;
  const close = () => {
    try {
      window.localStorage.setItem(ONBOARDING_KEY, "1");
    } catch {
      // без хранилища подсказка вернётся при следующем входе
    }
    setHidden(true);
  };
  return (
    <section
      aria-labelledby="onboarding-title"
      data-testid="onboarding"
      className="notice space-y-2"
    >
      <h2 id="onboarding-title" className="text-xl font-semibold">
        Добро пожаловать в Kognis
      </h2>
      <p>
        Записывайте мысли и переживания, подводите итог дня, получайте опыт и уровни. Режим Advanced
        (в разделе «Профиль») открывает графики и фильтры записей.
      </p>
      <button type="button" className={buttonClass} data-testid="onboarding-close" onClick={close}>
        Понятно
      </button>
    </section>
  );
}

function DaySummary() {
  const todayDate = useToday();
  // итог за сегодня — самый свежий: хватает первой страницы
  const reviews = useQuery({
    queryKey: ["day-reviews", "recent"],
    queryFn: () => listDayReviews({ limit: 1 }),
  });
  if (reviews.isError) return <ErrorMessage error={reviews.error} />;
  if (!reviews.data) return null;
  const today = reviews.data.items.find((review) => review.date === todayDate);
  return (
    <section
      aria-labelledby="day-summary-title"
      data-testid="day-summary"
      className="space-y-1 card"
    >
      <h2 id="day-summary-title" className="text-xl font-semibold">
        Итог дня
      </h2>
      {today ? (
        <p>
          Самочувствие: {today.wellbeing} из 10 · Настроение: {today.mood} из 10
        </p>
      ) : (
        <p>
          Сегодня итог ещё не подведён.{" "}
          <Link to="/day" className="link">
            Заполнить за сегодня
          </Link>
        </p>
      )}
    </section>
  );
}

export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return "Доброе утро";
  if (hour >= 12 && hour < 18) return "Добрый день";
  if (hour >= 18 && hour < 23) return "Добрый вечер";
  return "Доброй ночи";
}

export function HomePage({ advanced }: { advanced: boolean }) {
  const [crisis, setCrisis] = useState(false);
  return (
    <div className="space-y-6">
      <Onboarding />
      <h2 className="text-2xl font-bold" data-testid="greeting">
        {greeting(new Date().getHours())}
      </h2>
      <DaySummary />
      <CompanionCard crisis={crisis} />
      <button
        type="button"
        data-testid="write-cta"
        className="btn flex w-full items-center justify-center gap-2 !py-4 text-xl"
        onClick={() => {
          const field = document.getElementById("text");
          field?.scrollIntoView({ block: "center" });
          field?.focus();
        }}
      >
        <PencilIcon />
        Записать
      </button>
      <EntryForm onCrisis={setCrisis} />
      {advanced && <MoodChart />}
      <section aria-labelledby="entries-title" className="space-y-3">
        <h2 id="entries-title" className="text-xl font-semibold">
          {advanced ? "Мои записи" : "Последние записи"}
        </h2>
        <EntryList advanced={advanced} />
      </section>
    </div>
  );
}
