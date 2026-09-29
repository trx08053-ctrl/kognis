export function ErrorMessage({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <p className="mt-2 font-semibold text-[var(--danger-text)]" role="alert">
      {error.message}
    </p>
  );
}
