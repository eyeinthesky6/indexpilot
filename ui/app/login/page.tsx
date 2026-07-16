"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { clearApiToken, fetchApiAccess, storeApiToken, verifyApiToken } from "@/lib/api";
import { OperatorUnavailable } from "@/components/OperatorUnavailable";
import { operatorUiDisabled } from "@/lib/public-build";

export default function OperatorLoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [accessState, setAccessState] = useState<"checking" | "required" | "unavailable">(
    "checking",
  );

  useEffect(() => {
    let cancelled = false;

    async function resolveAccess() {
      try {
        const access = await fetchApiAccess();
        if (cancelled) return;
        if (access.authMode === "disabled") {
          router.replace("/dashboard");
          return;
        }
        setAccessState(access.authMode === "required" && access.authConfigured ? "required" : "unavailable");
      } catch {
        if (!cancelled) setAccessState("unavailable");
      }
    }

    if (!operatorUiDisabled) {
      void resolveAccess();
    }
    return () => {
      cancelled = true;
    };
  }, [router]);

  if (operatorUiDisabled) {
    return <OperatorUnavailable />;
  }

  if (accessState !== "required") {
    return (
      <main className="container mx-auto flex min-h-[70vh] max-w-lg items-center px-4 py-12">
        <Card className="w-full">
          <CardHeader>
            <CardTitle>{accessState === "checking" ? "Checking local API…" : "API access unavailable"}</CardTitle>
            <CardDescription>
              {accessState === "checking"
                ? "The default loopback-only API opens the dashboard without a login."
                : "Start indexpilot-api on loopback, or configure its bearer token before using explicit authentication."}
            </CardDescription>
          </CardHeader>
        </Card>
      </main>
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const candidate = token.trim();
    if (!candidate) {
      setError("Enter the API bearer token.");
      return;
    }

    setChecking(true);
    setError(null);
    storeApiToken(candidate);
    const valid = await verifyApiToken();
    if (!valid) {
      clearApiToken();
      setChecking(false);
      setError("The API rejected this token or is not configured.");
      return;
    }
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="container mx-auto flex min-h-[70vh] max-w-lg items-center px-4 py-12">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Operator access</CardTitle>
          <CardDescription>
            This API uses explicit authentication. Enter its bearer token; it is kept only for this
            browser session.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <label className="block space-y-2 text-sm font-medium">
              API token
              <input
                type="password"
                autoComplete="current-password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? "operator-login-error" : undefined}
                className="w-full rounded-md border bg-background px-3 py-2"
              />
            </label>
            {error ? (
              <p id="operator-login-error" role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <Button type="submit" disabled={checking} className="w-full">
              {checking ? "Checking…" : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
