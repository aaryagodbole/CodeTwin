"use client";

import { CircleHelp } from "lucide-react";
import { useId, useState } from "react";

/** A small "?" that explains a term in plain words. Opens on hover, keyboard focus or a tap (touch screens have no
 *  hover and Safari does not focus a tapped button); Escape closes it and keeps focus on the "?".
 *  `align="end"` anchors it to the right edge, for a "?" near the right side of a card. */
export function Info({ children, label = "What does this mean?", align = "center" }: {
  children: React.ReactNode; label?: string; align?: "center" | "end";
}) {
  const id = useId();
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hover || focus || pinned;
  const place = align === "end" ? "right-0" : "left-1/2 -translate-x-1/2";
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <button type="button" aria-label={label} aria-describedby={id} aria-expanded={open}
        onFocus={() => setFocus(true)} onBlur={() => { setFocus(false); setPinned(false); }}
        onClick={() => setPinned((p) => !p)}
        onKeyDown={(e) => { if (e.key === "Escape") { setHover(false); setFocus(false); setPinned(false); } }}
        className="text-muted transition hover:text-accent focus:text-accent focus:outline-none">
        <CircleHelp size={14} aria-hidden />
      </button>
      {/* pt-2 instead of a margin: the hover area runs unbroken from the "?" to the text, so it can be reached. */}
      <span className={`absolute top-full z-20 w-64 max-w-[calc(100vw-2rem)] pt-2 ${place} ${open ? "block" : "hidden"}`}>
        <span id={id} role="tooltip"
          className="block rounded-xl border border-border bg-card p-3 text-xs font-normal normal-case leading-relaxed tracking-normal text-foreground shadow-lg">
          {children}
        </span>
      </span>
    </span>
  );
}

export function PageHeader({ title, children, actions }: { title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {children && <p className="mt-1 max-w-2xl text-sm text-muted">{children}</p>}
      </div>
      {actions}
    </div>
  );
}
