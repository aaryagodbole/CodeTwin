"use client";

import { Activity, FolderTree, GitBranch, LayoutDashboard, ListChecks, Moon, Network, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

const links = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/map/", label: "Dependency graph", icon: Network },
  { href: "/repository/", label: "Repository", icon: FolderTree },
  { href: "/decisions/", label: "Decisions", icon: ListChecks },
  { href: "/results/", label: "Results", icon: Activity },
];

// Theme lives on <html data-theme>; this store lets React read it without setState-in-effect.
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  // With no saved choice the theme follows the system; tell React when the system flips.
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => {
    listeners.delete(cb);
    mq.removeEventListener("change", cb);
  };
};
const systemDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const isDarkNow = () => {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : systemDark();
};

function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, isDarkNow, () => false);
  // A saved theme is applied before the first paint by the script in layout.tsx; the store reads it from there.
  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    listeners.forEach((cb) => cb());
    try {
      localStorage.setItem("codetwin-theme", next);
    } catch {
      // not persisted; fine
    }
  };
  return (
    <button onClick={toggle} aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="grid h-9 w-9 place-items-center rounded-lg border border-border bg-card text-muted transition hover:text-foreground">
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label="CodeTwin AI, overview">
      <span className="grid h-9 w-9 place-items-center rounded-xl text-white"
        style={{ background: "linear-gradient(135deg, var(--accent), var(--accent-2))" }}>
        <GitBranch size={18} aria-hidden />
      </span>
      {/* On a phone the header also holds five nav icons and the theme toggle: show the name only from sm up. */}
      <span className={`leading-tight ${compact ? "hidden sm:block" : ""}`}>
        <span className="block text-sm font-semibold tracking-tight">CodeTwin AI</span>
        <span className="block text-[11px] text-muted">risk-calibrated testing</span>
      </span>
    </Link>
  );
}

export function Shell({ banner, children }: { banner?: React.ReactNode; children: React.ReactNode }) {
  const path = usePathname();
  const norm = (p: string) => p.replace(/\/+$/, "") || "/";
  // Highlight the section (Decisions also on a decision's detail page); aria-current only on the exact page.
  const isActive = (href: string) => (href === "/" ? norm(path) === "/" : norm(path).startsWith(norm(href)));
  const current = (href: string) => (norm(path) === norm(href) ? "page" as const : undefined);
  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card px-4 py-5 md:flex">
        <Logo />
        <nav className="mt-8 flex flex-col gap-1" aria-label="Main">
          {links.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} aria-current={current(href)}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                isActive(href) ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-card-2 hover:text-foreground"}`}>
              <Icon size={17} aria-hidden />
              {label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto text-[11px] leading-relaxed text-muted">
          Reads the CodeTwin API only. Code never leaves your machine.
        </p>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-border bg-background/80 px-4 py-3 backdrop-blur md:px-8">
          <div className="md:hidden"><Logo compact /></div>
          <nav className="flex gap-1 md:hidden" aria-label="Main (mobile)">
            {links.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} aria-label={label} aria-current={current(href)}
                className={`grid h-9 w-9 place-items-center rounded-lg ${isActive(href) ? "bg-accent-soft text-accent" : "text-muted"}`}>
                <Icon size={17} />
              </Link>
            ))}
          </nav>
          <div className="ml-auto"><ThemeToggle /></div>
        </header>
        {banner}
        <main className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
