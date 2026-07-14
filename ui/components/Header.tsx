"use client";

import Link from "next/link";
import { Activity, BarChart3, FileText, Home, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BrandMark } from "@/components/BrandMark";

export function Header() {
  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link href="/dashboard" className="flex items-center space-x-2">
            <BrandMark className="h-10 w-10" />
            <div className="flex flex-col">
              <span className="text-xl font-bold tracking-tight">IndexPilot</span>
              <span className="-mt-1 text-xs text-muted-foreground">Operator console</span>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            <Button asChild variant="ghost" className="gap-2">
              <Link href="/">
                <Home className="h-4 w-4" />
                <span>Project</span>
              </Link>
            </Button>
            <Button asChild variant="ghost" className="gap-2">
              <Link href="/dashboard/performance">
                <BarChart3 className="h-4 w-4" />
                <span>Performance</span>
              </Link>
            </Button>
            <Button asChild variant="ghost" className="gap-2">
              <Link href="/dashboard/health">
                <Activity className="h-4 w-4" />
                <span>Health</span>
              </Link>
            </Button>
            <Button asChild variant="ghost" className="gap-2">
              <Link href="/dashboard/decisions">
                <FileText className="h-4 w-4" />
                <span>Decisions</span>
              </Link>
            </Button>
          </nav>

          {/* Right side actions */}
          <div className="flex items-center space-x-4">
            <Button asChild variant="outline" className="gap-2">
              <Link href="/login">
                <LogIn className="h-4 w-4" />
                <span className="hidden sm:inline">Operator login</span>
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
