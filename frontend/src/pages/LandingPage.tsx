// Лендинг для гостя: что такое Kognis и зачем он, с формой входа/регистрации на первом экране.
import { useState } from "react";
import calm from "../assets/landing/calm.webp";
import hero from "../assets/landing/hero.webp";
import { ArrowIcon, FlameIcon, MoonIcon, ShieldIcon, SparkIcon, SunIcon } from "../Icons";
import { useTheme } from "../theme";
import { type AuthMode, AuthPage } from "./AuthPage";
import { Articles, Faq, Stories } from "./landing/Library";
import { Features, HowItWorks, Results, Stats } from "./landing/Sections";
import "./landing/landing.css";

export function LandingPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [theme, toggleTheme] = useTheme();

  function openAuth(next: AuthMode) {
    setMode(next);
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    document
      .getElementById("auth")
      ?.scrollIntoView?.({ behavior: reduced ? "auto" : "smooth", block: "center" });
    // после перерисовки формы — фокус в первое поле
    requestAnimationFrame(() => document.getElementById("email")?.focus({ preventScroll: true }));
  }

  return (
    <div className="lp">
      <a href="#main" className="lp-skip">
        К содержанию
      </a>
      <header className="lp-header">
        <div className="lp-container flex items-center justify-between gap-4">
          <a href="#top" className="lp-logo" aria-label="Kognis — наверх">
            <span className="lp-logo-mark" aria-hidden="true">
              K
            </span>
            Kognis
          </a>
          <nav aria-label="Разделы лендинга" className="lp-nav">
            {/* адреса — только якоря этой страницы */}
            <a href="#features">Возможности</a>
            <a href="#how">Как это работает</a>
            <a href="#results">Результаты</a>
            <a href="#stories">Истории</a>
            <a href="#articles">Статьи</a>
            <a href="#faq">Вопросы</a>
          </nav>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="lp-round"
              data-testid="theme-toggle"
              aria-label={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
              onClick={toggleTheme}
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
            <button
              type="button"
              className="btn-ghost max-sm:hidden"
              onClick={() => openAuth("login")}
            >
              Войти
            </button>
            <button
              type="button"
              className="btn lp-btn"
              data-testid="cta-header"
              onClick={() => openAuth("register")}
            >
              Начать
            </button>
          </div>
        </div>
      </header>

      <main id="main">
        <section id="top" aria-labelledby="hero-title" className="lp-hero">
          <div className="lp-blob lp-blob-1" aria-hidden="true" />
          <div className="lp-blob lp-blob-2" aria-hidden="true" />
          <div className="lp-container lp-hero-grid">
            <div className="lp-hero-text">
              <p className="lp-pill">
                <SparkIcon /> Дневник переживаний с ИИ-разбором
              </p>
              <h1 id="hero-title" className="lp-h1">
                Понимать себя — <span className="lp-gradient-text">первый шаг к спокойствию</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg muted">
                Kognis помогает замечать эмоции, находить повторяющиеся мысли с помощью проверенных
                подходов психологии и превращать заботу о себе в маленькие ежедневные шаги.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="btn lp-btn lp-btn-lg"
                  data-testid="cta-hero"
                  onClick={() => openAuth("register")}
                >
                  Начать вести дневник <ArrowIcon />
                </button>
                <a href="#how" className="btn-ghost lp-btn-lg">
                  Как это работает
                </a>
              </div>
              <ul className="lp-trust">
                <li>
                  <ShieldIcon /> Приватные записи шифруются в браузере
                </li>
                <li>
                  <FlameIcon /> 3 минуты в день
                </li>
              </ul>
            </div>
            <div className="lp-hero-visual">
              <div className="lp-hero-photo">
                <img
                  src={hero}
                  alt="Девушка у окна с чашкой чая пишет в дневник"
                  width={1200}
                  height={800}
                  fetchPriority="high"
                />
                <div className="lp-float lp-float-mood" aria-hidden="true">
                  <p className="text-xs muted">Пример · настроение за неделю</p>
                  <p className="text-lg font-bold">
                    6,8 <span className="lp-up">▲ 1,2</span>
                  </p>
                  <svg
                    viewBox="0 0 120 36"
                    className="lp-spark"
                    aria-hidden="true"
                    focusable="false"
                  >
                    <polyline points="0,30 20,26 40,28 60,18 80,16 100,10 120,6" />
                  </svg>
                </div>
                <div className="lp-float lp-float-insight" aria-hidden="true">
                  <p className="text-xs muted">Пример инсайта · КПТ</p>
                  <p className="text-sm font-semibold">«Прогноз — ещё не факт»</p>
                </div>
              </div>
              <div className="lp-auth">
                <AuthPage mode={mode} onModeChange={setMode} />
              </div>
            </div>
          </div>
        </section>

        <Stats />
        <Features />
        <HowItWorks />
        <Results />
        <Stories />
        <Articles />
        <Faq />

        <section aria-labelledby="cta-title" className="lp-container lp-section">
          <div className="lp-cta">
            <img src={calm} alt="" loading="lazy" className="lp-cta-bg" />
            <div className="lp-cta-body">
              <h2 id="cta-title" className="lp-h2 text-white">
                Начните с одной записи сегодня
              </h2>
              <p className="mt-4 max-w-xl text-lg text-white/90">
                Пара строк о том, что вы чувствуете, — и завтра станет чуть понятнее, чем вчера.
              </p>
              <button
                type="button"
                className="lp-btn-light mt-8"
                data-testid="cta-final"
                onClick={() => openAuth("register")}
              >
                Создать аккаунт <ArrowIcon />
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-container flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="lp-logo">
              <span className="lp-logo-mark" aria-hidden="true">
                K
              </span>
              Kognis
            </p>
            <p className="mt-2 max-w-md text-sm muted" data-testid="landing-disclaimer">
              Kognis — не медицинская помощь и не заменяет специалиста. В кризисной ситуации звоните{" "}
              <a className="link" href="tel:112">
                112
              </a>
              .
            </p>
          </div>
          <p className="text-sm muted">© 2026 Kognis</p>
        </div>
      </footer>
    </div>
  );
}
