"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { ArrowLeft, LogIn } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { OperatorUnavailable } from "@/components/OperatorUnavailable";
import { Button } from "@/components/ui/button";
import { hasApiToken } from "@/lib/api";
import { operatorUiDisabled } from "@/lib/public-build";

function subscribeToOperatorSession() {
  return () => undefined;
}

export function DashboardGate({ children }: Readonly<{ children: React.ReactNode }>) {
  const hasToken = useSyncExternalStore(subscribeToOperatorSession, hasApiToken, () => false);

  if (operatorUiDisabled) {
    return <OperatorUnavailable />;
  }

  if (!hasToken) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-5 py-16">
        <section className="w-full max-w-xl rounded-3xl border bg-white p-7 shadow-sm sm:p-10">
          <BrandMark className="h-12 w-12" />
          <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Local operator surface
          </p>
          <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
            Connect your IndexPilot API first.
          </h1>
          <p className="mt-4 leading-7 text-muted-foreground">
            The experimental dashboard needs the bearer token configured by the API operator. The
            token stays in this browser session. This screen is a convenience gate; the Python API
            remains the authorization boundary.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild className="gap-2">
              <Link href="/login">
                <LogIn className="h-4 w-4" />
                Operator login
              </Link>
            </Button>
            <Button asChild variant="outline" className="gap-2">
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
                Back to project site
              </Link>
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}
