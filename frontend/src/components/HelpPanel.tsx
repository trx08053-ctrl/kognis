import type { HelpBlock } from "../api";

export function HelpPanel({ help }: { help: HelpBlock }) {
  return (
    <section
      role="alert"
      aria-labelledby="help-title"
      data-testid="help-block"
      className="rounded-2xl border-2 border-[var(--danger-border)] bg-[var(--danger-bg)] p-4 text-[var(--danger-text)]"
    >
      <h3 id="help-title" className="text-lg font-bold">
        Вам может понадобиться помощь
      </h3>
      <p className="mt-1">{help.message}</p>
      <ul className="mt-2 space-y-1">
        {help.contacts.map((contact) => (
          <li key={`${contact.name}-${contact.phone}`}>
            {contact.name}:{" "}
            <a href={`tel:${contact.phone}`} className="text-xl font-bold underline">
              {contact.phone}
            </a>
            {contact.note && <span> — {contact.note}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
