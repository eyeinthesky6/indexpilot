"use client";

import Link from "next/link";
import { Database, BarChart3, Activity, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Header() {
  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Database className="h-6 w-6" />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold tracking-tight">IndexPilot</span>
              <span className="text-xs text-muted-foreground -mt-1">Auto-Indexing</span>
            </div>
          </Link>

          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            <Link href="/dashboard/performance">
              <Button variant="ghost" className="flex items-center space-x-2">
                <BarChart3 className="h-4 w-4" />
                <span>Performance</span>
              </Button>
            </Link>
            <Link href="/dashboard/health">
              <Button variant="ghost" className="flex items-center space-x-2">
                <Activity className="h-4 w-4" />
                <span>Health</span>
              </Button>
            </Link>
            <Link href="/dashboard/decisions">
              <Button variant="ghost" className="flex items-center space-x-2">
                <FileText className="h-4 w-4" />
                <span>Decisions</span>
              </Button>
            </Link>
          </nav>

          {/* Right side actions */}
          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex items-center space-x-2 text-sm text-muted-foreground">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>API Connected</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

