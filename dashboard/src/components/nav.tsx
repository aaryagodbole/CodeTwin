"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/map/", label: "System map" },
  { href: "/decisions/", label: "Decisions" },
  { href: "/results/", label: "Results" },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav className="flex gap-1">
      {links.map((l) => {
        const active = l.href === "/" ? path === "/" : path.startsWith(l.href.replace(/\/$/, ""));
        return (
          <Link key={l.href} href={l.href}
            className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-foreground/10 font-medium" : "text-muted hover:bg-foreground/5"}`}>
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
