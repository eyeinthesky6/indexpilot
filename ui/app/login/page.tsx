"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { clearApiToken, storeApiToken, verifyApiToken } from "@/lib/api";

export default function OperatorLoginPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

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
    router.push("/");
    router.refresh();
  }

  return (
    <main className="container mx-auto flex min-h-[70vh] max-w-lg items-center px-4 py-12">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Operator access</CardTitle>
          <CardDescription>
            Enter the bearer token configured by the IndexPilot API operator. It is kept only for
            this browser session.
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
                className="w-full rounded-md border bg-background px-3 py-2"
              />
            </label>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" disabled={checking} className="w-full">
              {checking ? "Checking…" : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
