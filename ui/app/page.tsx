"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Activity, Database, TrendingUp, AlertCircle } from "lucide-react";
import { fetchHealthData, fetchPerformanceData } from "@/lib/api";

export default function Home() {
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
              ? perfData.indexImpact.reduce((acc, idx) => acc + idx.improvement, 0) /
                perfData.indexImpact.length
              : 0,
            systemHealth: healthStatus,
            alerts: summary.criticalIndexes + summary.warningIndexes,
          });
        }
      } catch (err) {
        console.error("Failed to load stats:", err);
      } finally {
        setLoading(false);
      }
    }

    void loadStats();
    const interval = setInterval(() => {
      void loadStats();
    }, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);
  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto p-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">IndexPilot Dashboard</h1>
          <p className="text-muted-foreground">
            PostgreSQL Auto-Indexing Management and Monitoring
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Indexes</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {loading ? "-" : stats.totalIndexes}
              </div>
              <p className="text-xs text-muted-foreground">Active indexes</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Query Performance</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {loading ? "-" : `${stats.avgImprovement.toFixed(1)}%`}
              </div>
              <p className="text-xs text-muted-foreground">Avg improvement</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">System Health</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${
                  stats.systemHealth === "healthy"
                    ? "text-green-600"
                    : stats.systemHealth === "warning"
                      ? "text-yellow-600"
                      : "text-red-600"
                }`}
              >
                {loading ? "-" : stats.systemHealth}
              </div>
              <p className="text-xs text-muted-foreground">Overall status</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Alerts</CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {loading ? "-" : stats.alerts}
              </div>
              <p className="text-xs text-muted-foreground">Active alerts</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Performance Dashboard</CardTitle>
              <CardDescription>
                View query performance metrics, index impact, and optimization trends
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/dashboard/performance">
                <Button className="w-full">View Performance Dashboard</Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Health Monitoring</CardTitle>
              <CardDescription>
                Monitor index health, bloat, usage statistics, and system status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/dashboard/health">
                <Button className="w-full">View Health Dashboard</Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Decision Explanations</CardTitle>
              <CardDescription>
                Understand why indexes were created or skipped with full cost-benefit analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/dashboard/decisions">
                <Button className="w-full">View Decisions</Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
