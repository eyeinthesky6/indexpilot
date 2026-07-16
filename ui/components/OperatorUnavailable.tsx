import Link from "next/link";
import { ArrowLeft, BookOpen } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";

export function OperatorUnavailable() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-5 py-16">
      <section className="w-full max-w-xl rounded-3xl border bg-white p-7 shadow-sm sm:p-10">
        <BrandMark className="h-12 w-12" />
        <p className="mt-8 font-mono text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Local operator surface
        </p>
        <h1 className="mt-3 font-display text-3xl font-bold tracking-[-0.04em] sm:text-4xl">
          The dashboard is not hosted here.
        </h1>
        <p className="mt-4 leading-7 text-muted-foreground">
          This public site never accepts an API token or connects to a database. Run the optional
          operator UI beside your own loopback-only IndexPilot API; it opens locally without a
          login. Any non-loopback API still requires explicit authentication.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button asChild className="gap-2">
            <Link href="https://eyeinthesky6.github.io/indexpilot/">
              <ArrowLeft className="h-4 w-4" />
              Back to project site
            </Link>
          </Button>
          <Button asChild variant="outline" className="gap-2">
            <a href="https://github.com/eyeinthesky6/indexpilot/blob/main/ui/README.md">
              <BookOpen className="h-4 w-4" />
              Local UI guide
            </a>
          </Button>
        </div>
      </section>
    </main>
  );
}
