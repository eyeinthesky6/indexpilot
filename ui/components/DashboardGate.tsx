"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, LogIn, RefreshCw } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { OperatorUnavailable } from "@/components/OperatorUnavailable";
import { Button } from "@/components/ui/button";
import { clearApiToken, fetchApiAccess, hasApiToken, verifyApiToken } from "@/lib/api";
import { operatorUiDisabled } from "@/lib/public-build";

type GateState = "checking" | "open" | "token-required" | "misconfigured" | "unavailable";

export function DashboardGate({ children }: Readonly<{ children: React.ReactNode }>) {
  const [gateState, setGateState] = useState<GateState>("checking");

  useEffect(() => {
    let cancelled = false;

    async function resolveAccess() {
      try {
        const access = await fetchApiAccess();
        if (cancelled) return;

        if (access.authMode === "disabled") {
          setGateState("open");
          return;
        }
        if (access.authMode !== "required" || !access.authConfigured) {
          setGateState("misconfigured");
          return;
        }
        if (!hasApiToken()) {
          setGateState("token-required");
          return;
        }

        const tokenIsValid = await verifyApiToken();
        if (cancelled) return;
        if (!tokenIsValid) {
          clearApiToken();
        }
        setGateState(tokenIsValid ? "open" : "token-required");
      } catch {
        if (!cancelled) setGateState("unavailable");
      }
    }

    if (!operatorUiDisabled) {
      void resolveAccess();
    }
    return () => {
      cancelled = true;
    };
  }, []);

  if (operatorUiDisabled) {
    return <OperatorUnavailable />;
  }

  if (gateState === "checking") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-5 py-16">
        <section className="w-full max-w-xl rounded-3xl border bg-white p-7 shadow-sm sm:p-10" aria-live="polite">
          <BrandMark className="h-12 w-12" />
          <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Local operator surface
          </p>
          <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
            Checking your local IndexPilot API…
          </h1>
        </section>
      </main>
    );
  }

  if (gateState === "unavailable") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-5 py-16">
        <section className="w-full max-w-xl rounded-3xl border bg-white p-7 shadow-sm sm:p-10">
          <BrandMark className="h-12 w-12" />
          <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Local operator surface
          </p>
          <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
            Start the local API first.
          </h1>
          <p className="mt-4 leading-7 text-muted-foreground">
            Run <code>indexpilot-api</code> on this machine, then retry. Loopback access opens
            directly without a login.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button className="gap-2" onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4" />
              Retry connection
            </Button>
            <Button asChild variant="outline" className="gap-2">
              <Link href="https://eyeinthesky6.github.io/indexpilot/">
                <ArrowLeft className="h-4 w-4" />
                Back to project site
              </Link>
            </Button>
          </div>
        </section>
      </main>
    );
  }

  if (gateState === "misconfigured") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-5 py-16">
        <section className="w-full max-w-xl rounded-3xl border bg-white p-7 shadow-sm sm:p-10">
          <BrandMark className="h-12 w-12" />
          <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            API configuration
          </p>
          <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
            Finish configuring API access.
          </h1>
          <p className="mt-4 leading-7 text-muted-foreground">
            Restart the API on its default loopback address for passwordless local access, or set a
            bearer token when explicit authentication is required.
          </p>
        </section>
      </main>
    );
  }

  if (gateState === "token-required") {
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
            This API was started with explicit authentication. Enter its bearer token once for this
            browser session. The default loopback-only API does not show this step.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild className="gap-2">
              <Link href="/login">
                <LogIn className="h-4 w-4" />
                Operator login
              </Link>
            </Button>
            <Button asChild variant="outline" className="gap-2">
              <Link href="https://eyeinthesky6.github.io/indexpilot/">
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
