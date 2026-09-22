import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dossier — Research with evidence",
  description: "Live-source research and fact-checking with visible uncertainty.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
