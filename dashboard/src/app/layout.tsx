import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeTwin AI",
  description: "Evidence-aware, risk-calibrated change verification",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">
        <Providers>
          <header className="border-b border-border">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
              <span className="font-semibold">CodeTwin AI</span>
              <Nav />
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-6 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
