import type { Metadata } from "next";
import { Instrument_Sans, Syne } from "next/font/google";
import "./globals.css";

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument-sans",
  display: "swap",
});

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
});

const siteUrl = "https://eyeinthesky6.github.io/indexpilot/";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "IndexPilot | PostgreSQL index review before merge",
    template: "%s · IndexPilot",
  },
  description:
    "Review proposed PostgreSQL indexes against observed workload, existing indexes, and optional HypoPG evidence before they reach production.",
  keywords: [
    "PostgreSQL",
    "database migrations",
    "index review",
    "HypoPG",
    "pg_stat_statements",
    "SARIF",
  ],
  alternates: {
    canonical: siteUrl,
    types: { "text/plain": `${siteUrl}llms.txt` },
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    siteName: "IndexPilot",
    title: "Make every proposed PostgreSQL index earn its benchmark",
    description:
      "An open-source evidence gate for the exact CREATE INDEX in your migration pull request.",
    images: [
      {
        url: `${siteUrl}brand/indexpilot-social.png`,
        width: 1280,
        height: 640,
        alt: "IndexPilot reviewing a proposed PostgreSQL index before merge",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "IndexPilot | PostgreSQL index review before merge",
    description:
      "Make every proposed PostgreSQL index earn its benchmark before merge.",
    images: [`${siteUrl}brand/indexpilot-social.png`],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${instrumentSans.variable} ${syne.variable} font-sans`}>{children}</body>
    </html>
  );
}
