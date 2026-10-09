"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { api, GITHUB_URL, setOwnerToken, useOwner } from "@/lib/api";

const links = [
  { href: "/chat", label: "Ask the bot" },
  { href: "/runs", label: "Test runs" },
  { href: "/compare", label: "Compare" },
  { href: "/review", label: "Human review" },
];

export default function Nav() {
  const path = usePathname();
  const owner = useOwner();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function signIn() {
    setErr(null);
    setOwnerToken(value);
    try { await api("/admin/check", { owner: true }); setOpen(false); setValue(""); }
    catch { setOwnerToken(null); setErr("That token wasn't accepted."); }
  }

  return (
    <header className="border-b border-rule bg-sheet/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-5 py-4 sm:px-8">
        <Link href="/" className="font-display text-xl font-bold tracking-tight">Aarogya</Link>
        <nav className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {links.map((l) => {
            const active = path === l.href || (l.href !== "/" && path.startsWith(l.href));
            return (
              <Link key={l.href} href={l.href}
                className={`py-1 ${active ? "text-ink border-b-2 border-pass" : "text-ink-soft hover:text-ink"}`}>
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-sm">
          {GITHUB_URL && <a href={GITHUB_URL} className="text-ink-soft hover:text-ink" target="_blank" rel="noreferrer">Source code</a>}
          {owner ? (
            <button onClick={() => setOwnerToken(null)} className="text-ink-soft hover:text-ink">Sign out</button>
          ) : (
            <button onClick={() => setOpen((o) => !o)} className="text-ink-soft hover:text-ink">Owner sign-in</button>
          )}
        </div>
      </div>
      {open && !owner && (
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 pb-4 sm:px-8">
          <label htmlFor="tok" className="text-sm text-ink-soft">Admin token</label>
          <input id="tok" type="password" value={value} onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && signIn()}
            className="w-64 rounded border border-rule bg-sheet px-3 py-1.5 text-sm" />
          <button onClick={signIn} className="rounded bg-ink px-3 py-1.5 text-sm text-sheet">Sign in</button>
          {err && <span className="text-sm text-fail">{err}</span>}
        </div>
      )}
    </header>
  );
}
