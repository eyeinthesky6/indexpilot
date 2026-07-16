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
    default: "IndexPilot | Stop bad PostgreSQL indexes before production",
    template: "%s · IndexPilot",
  },
  description:
    "Check proposed PostgreSQL indexes against your real workload before you merge them.",
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
    title: "Stop bad PostgreSQL indexes before they reach production",
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
    title: "IndexPilot | Stop bad PostgreSQL indexes before production",
    description:
      "Check a proposed index against your real PostgreSQL workload before you merge it.",
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
