import { LOCALE_NAMES, useI18n } from "../i18n";

// переключатель языка: при единственном языке не показывается
export function LanguageSwitcher() {
  const { t, locale, locales, setLocale } = useI18n();
  if (locales.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="language" className="font-semibold">
        {t("lang.label")}
      </label>
      <select
        id="language"
        data-testid="language-select"
        className="input !w-auto max-w-full"
        value={locale}
        onChange={(event) => setLocale(event.target.value)}
      >
        {locales.map((code) => (
          <option key={code} value={code}>
            {LOCALE_NAMES[code] ?? code}
          </option>
        ))}
      </select>
    </div>
  );
}
