import type { Metadata } from "next";
import { DemoBanner } from "@/components/demo-banner";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeTwin AI",
  description: "Evidence-aware, risk-calibrated change verification",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full">
        <Providers>
          <Shell banner={<DemoBanner />}>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
