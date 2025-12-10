"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, Github, FileText, Mail } from "lucide-react";
import { fetchSystemHealth } from "@/lib/api";

export function Footer() {
  // Use static year to avoid hydration mismatch
  const currentYear = 2025;
  const [systemStatus, setSystemStatus] = useState<{
    status: string;
    color: string;
  }>({ status: "checking...", color: "gray" });

  useEffect(() => {
    async function loadSystemHealth() {
      try {
        const health = await fetchSystemHealth();
        setSystemStatus({
          status: health.status === "operational" ? "Operational" : 
                 health.status === "degraded" ? "Degraded" :
                 health.status === "critical" ? "Critical" : "Unknown",
          color: health.statusColor,
        });
      } catch (error) {
        setSystemStatus({
          status: "Degraded",
          color: "yellow",
        });
      }
    }

    void loadSystemHealth();
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      void loadSystemHealth();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="border-t bg-background">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand Section */}
          <div className="space-y-4">
            <Link href="/" className="flex items-center space-x-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Database className="h-5 w-5" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight">IndexPilot</span>
                <span className="text-xs text-muted-foreground -mt-1">Auto-Indexing</span>
              </div>
            </Link>
            <p className="text-sm text-muted-foreground">
              Automatic PostgreSQL index management with DNA-inspired architecture.
            </p>
          </div>

          {/* Product Links */}
          <div>
            <h3 className="text-sm font-semibold mb-4">Product</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <Link href="/dashboard/performance" className="text-muted-foreground hover:text-foreground transition-colors">
                  Performance Dashboard
                </Link>
              </li>
              <li>
                <Link href="/dashboard/health" className="text-muted-foreground hover:text-foreground transition-colors">
                  Health Monitoring
                </Link>
              </li>
              <li>
                <Link href="/dashboard/decisions" className="text-muted-foreground hover:text-foreground transition-colors">
                  Decision Explanations
                </Link>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-sm font-semibold mb-4">Resources</h3>
            <ul className="space-y-2 text-sm">
              <li>
                <a
                  href="https://github.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-foreground transition-colors flex items-center space-x-1"
                >
                  <Github className="h-3 w-3" />
                  <span>GitHub</span>
                </a>
              </li>
              <li>
                <a
                  href="#"
                  className="text-muted-foreground hover:text-foreground transition-colors flex items-center space-x-1"
                >
                  <FileText className="h-3 w-3" />
                  <span>Documentation</span>
                </a>
              </li>
              <li>
                <a
                  href="#"
                  className="text-muted-foreground hover:text-foreground transition-colors flex items-center space-x-1"
                >
                  <Mail className="h-3 w-3" />
                  <span>Support</span>
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t flex flex-col sm:flex-row justify-between items-center space-y-4 sm:space-y-0">
          <p className="text-sm text-muted-foreground">
            © {currentYear} IndexPilot. All rights reserved.
          </p>
          <div className="flex items-center space-x-6 text-sm text-muted-foreground">
            <span className="flex items-center space-x-1">
              <div
                className={`h-2 w-2 rounded-full ${
                  systemStatus.color === "green"
                    ? "bg-green-500"
                    : systemStatus.color === "yellow"
                      ? "bg-yellow-500"
                      : systemStatus.color === "red"
                        ? "bg-red-500"
                        : "bg-gray-500"
                } ${systemStatus.color === "green" ? "animate-pulse" : ""}`}
              />
              <span>System {systemStatus.status}</span>
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}

