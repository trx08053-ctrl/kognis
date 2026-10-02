import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { ApiError, getMe } from "./api";
import { ErrorMessage } from "./components/ErrorMessage";
import { Shell } from "./components/Shell";
import { APP_NAME, useI18n } from "./i18n";
import { AnalysisPage } from "./pages/AnalysisPage";
import { ArchivePage } from "./pages/ArchivePage";
import { DayReviewPage } from "./pages/DayReviewPage";
import { HomePage } from "./pages/HomePage";
import { LandingPage } from "./pages/LandingPage";
import { ProfilePage } from "./pages/ProfilePage";
import { QuestsPage } from "./pages/QuestsPage";

export function App() {
  const { t, locales, setLocale } = useI18n();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });
  const user = me.data;
  const { pathname } = useLocation();
  // язык из профиля после входа: он важнее языка браузера (docs/I18N.md, правило 5)
  const profileLocale = user?.locale;
  // применяется один раз на значение профиля: ручной выбор языка потом не перебивается
  const applied = useRef<string | null>(null);
  useEffect(() => {
    if (!profileLocale || applied.current === profileLocale) return;
    applied.current = profileLocale;
    if (locales.includes(profileLocale)) setLocale(profileLocale);
  }, [profileLocale, locales, setLocale]);
  const anonymous = me.error instanceof ApiError && me.error.status === 401;

  let body = <p>{t("app.loading")}</p>;
  if (user && pathname === "/welcome") {
    // главная страница сайта для вошедшего: свой макет, без форм входа, с переходом в дневник
    return <LandingPage signedIn />;
  }
  if (user) {
    body = (
      <Routes>
        <Route
          path="/"
          element={
            <Shell user={user}>
              <HomePage advanced={user.advanced === true} />
            </Shell>
          }
        />
        <Route
          path="/day"
          element={
            <Shell user={user}>
              <DayReviewPage />
            </Shell>
          }
        />
        <Route
          path="/analysis"
          element={
            <Shell user={user}>
              <AnalysisPage />
            </Shell>
          }
        />
        <Route
          path="/profile"
          element={
            <Shell user={user}>
              <ProfilePage user={user} />
            </Shell>
          }
        />
        <Route path="/achievements" element={<Navigate to="/profile" replace />} />
        <Route
          path="/quests"
          element={
            <Shell user={user}>
              <QuestsPage />
            </Shell>
          }
        />
        <Route
          path="/archive"
          element={
            <Shell user={user}>
              <ArchivePage />
            </Shell>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  } else if (anonymous) {
    // гость: лендинг с формой входа на главной, остальные адреса ведут на неё
    return (
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  } else if (me.isError) {
    body = <ErrorMessage error={me.error} />;
  }

  return (
    <div className={user ? "layout" : ""}>
      <main className="mx-auto max-w-2xl space-y-6 px-4 pb-28 pt-6 md:pb-10">
        <h1 className="text-3xl font-bold">{APP_NAME}</h1>
        <p className="text-sm muted">{t("app.tagline")}</p>
        {body}
      </main>
    </div>
  );
}
