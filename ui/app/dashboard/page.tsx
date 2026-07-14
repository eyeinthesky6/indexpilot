"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertCircle, Database, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchHealthData, fetchPerformanceData } from "@/lib/api";

export default function DashboardOverview() {
  const [stats, setStats] = useState({
    totalIndexes: 0,
    avgImprovement: 0,
    systemHealth: "unknown",
    alerts: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadStats() {
      try {
        const [healthData, perfData] = await Promise.all([
          fetchHealthData().catch(() => null),
          fetchPerformanceData().catch(() => null),
        ]);

        if (healthData) {
          const summary = healthData.summary;
          const healthStatus =
            summary.criticalIndexes > 0
              ? "critical"
              : summary.warningIndexes > 0
                ? "warning"
                : "healthy";

          setStats({
            totalIndexes: summary.totalIndexes,
            avgImprovement: perfData?.indexImpact
              ? perfData.indexImpact.reduce((acc, index) => acc + index.improvement, 0) /
                perfData.indexImpact.length
              : 0,
            systemHealth: healthStatus,
            alerts: summary.criticalIndexes + summary.warningIndexes,
          });
        }
      } catch (error) {
        console.error("Failed to load dashboard statistics:", error);
      } finally {
        setLoading(false);
      }
    }

    void loadStats();
    const interval = setInterval(() => {
      void loadStats();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-background">
      <div className="container mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <p className="mb-2 font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Experimental local surface
          </p>
          <h1 className="font-display text-4xl font-bold">Operator dashboard</h1>
          <p className="mt-2 text-muted-foreground">
            Inspect advisory index evidence and health from a configured IndexPilot API.
          </p>
        </div>

        <div className="mb-8 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total indexes</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? "—" : stats.totalIndexes}</div>
              <p className="text-xs text-muted-foreground">Visible to the API role</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Query performance</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {loading ? "—" : `${stats.avgImprovement.toFixed(1)}%`}
              </div>
              <p className="text-xs text-muted-foreground">Reported average improvement</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Index health</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${
                  stats.systemHealth === "healthy"
                    ? "text-green-700"
                    : stats.systemHealth === "warning"
                      ? "text-amber-700"
                      : "text-red-700"
                }`}
              >
                {loading ? "—" : stats.systemHealth}
              </div>
              <p className="text-xs text-muted-foreground">Current API assessment</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alerts</CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{loading ? "—" : stats.alerts}</div>
              <p className="text-xs text-muted-foreground">Warning and critical findings</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Performance</CardTitle>
              <CardDescription>
                Inspect query metrics, reported index impact, and optimization trends.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full">
                <Link href="/dashboard/performance">View performance</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Health</CardTitle>
              <CardDescription>
                Review index bloat, usage counters, and current system status.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full">
                <Link href="/dashboard/health">View health</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Decision evidence</CardTitle>
              <CardDescription>
                Inspect why a proposal received support, caution, or an inconclusive result.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild className="w-full">
                <Link href="/dashboard/decisions">View decisions</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
