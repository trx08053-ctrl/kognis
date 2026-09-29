interface ScaleFieldProps {
  id: string;
  label: string;
  low: string;
  high: string;
  value: string;
  onChange: (value: string) => void;
}

// шкала 1–10: ползунок с подписями концов и текущим значением
export function ScaleField({ id, label, low, high, value, onChange }: ScaleFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 flex items-baseline justify-between font-semibold">
        {label}
        <output htmlFor={id} className="text-2xl text-[var(--accent-text)]">
          {value}
        </output>
      </label>
      <input
        id={id}
        type="range"
        min={1}
        max={10}
        step={1}
        className="w-full accent-[var(--accent)]"
        aria-describedby={`${id}-hint`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div id={`${id}-hint`} className="flex justify-between text-sm muted">
        <span>1 · {low}</span>
        <span>{high} · 10</span>
      </div>
    </div>
  );
}
