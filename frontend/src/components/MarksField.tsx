import { useI18n } from "../i18n";

export const MARKS = ["step", "good", "reframe", "insight"] as const;
export type Mark = (typeof MARKS)[number];

// отметки рефлексии ставит сам пользователь: бонус опыта не зависит от длины и тона текста
export function MarksField({
  value,
  onChange,
}: {
  value: Mark[];
  onChange: (value: Mark[]) => void;
}) {
  const { t } = useI18n();
  return (
    <fieldset data-testid="marks">
      <legend className="mb-1 block font-semibold">{t("marks.title")}</legend>
      <p className="text-sm muted">{t("marks.hint")}</p>
      <div className="flex flex-wrap gap-3">
        {MARKS.map((mark) => (
          <label key={mark} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={value.includes(mark)}
              onChange={() =>
                onChange(value.includes(mark) ? value.filter((m) => m !== mark) : [...value, mark])
              }
            />
            {t(`marks.${mark}`)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
