/** Unknown hash route or missing run. */
export function NotFound({ message = "That page was not found." }: { message?: string }) {
  return (
    <div className="pt-8">
      <p className="text-sm text-muted">
        {message}{" "}
        <a href="#/" className="text-ink underline-offset-2 hover:underline">
          Back home
        </a>
        .
      </p>
    </div>
  );
}
