export function Loading({ slow, what }: { slow?: boolean; what: string }) {
  return (
    <div className="py-12 text-ink-soft" role="status">
      <p>Loading {what}…</p>
      {slow && (
        <p className="mt-2 max-w-prose text-sm">
          The API runs on free hosting that sleeps when idle. Waking it takes up to a minute; this page will fill in on its own.
        </p>
      )}
    </div>
  );
}

export function ErrorNote({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="my-6 rounded border border-fail/30 bg-fail-tint px-4 py-3 text-sm">
      <p>{message}</p>
      {retry && <button onClick={retry} className="mt-2 underline">Try again</button>}
    </div>
  );
}

export function Pill({ tone, children }: { tone: "pass" | "fail" | "watch" | "plain"; children: React.ReactNode }) {
  const cls = {
    pass: "bg-pass-tint text-pass", fail: "bg-fail-tint text-fail",
    watch: "bg-watch-tint text-watch", plain: "bg-paper text-ink-soft border border-rule",
  }[tone];
  return <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}
