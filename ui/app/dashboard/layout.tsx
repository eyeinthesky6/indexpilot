import type { Metadata } from "next";
import { DashboardGate } from "@/components/DashboardGate";

export const metadata: Metadata = {
  title: "Operator dashboard",
  description: "Local operator dashboard for IndexPilot.",
  robots: { index: false, follow: false },
};

export default function DashboardLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <DashboardGate>{children}</DashboardGate>;
}
