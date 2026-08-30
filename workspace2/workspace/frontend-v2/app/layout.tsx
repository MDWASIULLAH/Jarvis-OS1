import "../styles/globals.css";
import "../styles/operations.css";
import "../styles/development-studio.css";
import "../styles/mission-control.css";
import "../styles/workforce.css";
import "../styles/knowledge-graph.css";
import "../styles/security.css";
import "../styles/hardening.css";
import "katex/dist/katex.min.css";
import "@xyflow/react/dist/style.css";
import { AppProviders } from "../providers/app-providers";
import { themeBootstrapScript } from "../providers/theme-manager";
import type { ReactNode } from "react";

export const metadata = { title: "JARVIS OS", description: "JARVIS AI Operating System" };

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Sets data-theme before first paint so panels never flash the wrong palette. */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
