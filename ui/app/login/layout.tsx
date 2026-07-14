import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Operator access",
  robots: { index: false, follow: false },
};

export default function LoginLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
