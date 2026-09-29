import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router";
import { ApiError, getMe } from "./api";
import { ErrorMessage } from "./components/ErrorMessage";
import { Shell } from "./components/Shell";
import { AnalysisPage } from "./pages/AnalysisPage";
import { AuthPage } from "./pages/AuthPage";
import { DayReviewPage } from "./pages/DayReviewPage";
import { HomePage } from "./pages/HomePage";
import { ProfilePage } from "./pages/ProfilePage";
import { QuestsPage } from "./pages/QuestsPage";

export function App() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });
  const user = me.data;
  const anonymous = me.error instanceof ApiError && me.error.status === 401;

  let body = <p>Загрузка…</p>;
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  } else if (anonymous) {
    body = (
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  } else if (me.isError) {
    body = <ErrorMessage error={me.error} />;
  }

  return (
    <div className={user ? "layout" : ""}>
      <main className="mx-auto max-w-2xl space-y-6 px-4 pb-28 pt-6 md:pb-10">
        <h1 className="text-3xl font-bold">Kognis</h1>
        <p className="text-sm muted">Дневник переживаний.</p>
        {body}
      </main>
    </div>
  );
}
