const inputClass = "input";

export function splitList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item !== "");
}

// список чипов: выбор из словаря/своих значений, кнопка-чип переключает выбор
export function ChipToggleGroup({
  legend,
  options,
  selected,
  onToggle,
}: {
  legend: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-1 font-semibold">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className="chip"
            aria-pressed={selected.includes(option)}
            onClick={() => onToggle(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

// поле «добавить своё»: значения через запятую или Enter становятся чипами; недописанное
// значение попадает в запись при сохранении
export function CustomChipInput({
  id,
  label,
  chips,
  pending,
  onPending,
  onCommit,
  onRemove,
  removeLabel,
}: {
  id: string;
  label: string;
  chips: string[];
  pending: string;
  onPending: (value: string) => void;
  onCommit: (values: string[]) => void;
  onRemove: (value: string) => void;
  removeLabel: string;
}) {
  const commit = (raw: string) => {
    onCommit(splitList(raw));
    onPending("");
  };
  return (
    <div>
      <label htmlFor={id} className="mb-1 block font-semibold">
        {label}
      </label>
      {chips.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <li key={chip}>
              <button
                type="button"
                className="chip chip-on"
                aria-label={`${removeLabel}: ${chip}`}
                onClick={() => onRemove(chip)}
              >
                {chip} <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <input
        id={id}
        className={inputClass}
        value={pending}
        onChange={(event) => {
          const value = event.target.value;
          if (value.includes(",")) commit(value);
          else onPending(value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && pending.trim() !== "") {
            event.preventDefault();
            commit(pending);
          }
        }}
        onBlur={() => pending.trim() !== "" && commit(pending)}
      />
    </div>
  );
}

export function addUnique(list: string[], values: string[]): string[] {
  return [...list, ...values.filter((value) => !list.includes(value))];
}
