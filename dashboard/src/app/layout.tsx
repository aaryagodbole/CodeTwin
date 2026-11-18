import type { Metadata } from "next";
import { DemoBanner } from "@/components/demo-banner";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeTwin AI",
  description: "Evidence-aware, risk-calibrated change verification",
};

const THEME_INIT = `try{var t=localStorage.getItem("codetwin-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <head>
        {/* Before the first paint: a saved theme choice, so a reload never flashes the other theme. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body className="min-h-full">
        <Providers>
          <Shell banner={<DemoBanner />}>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
