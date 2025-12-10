"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { fetchPerformanceData, type PerformanceData, type IndexImpact, type ExplainStats } from "@/lib/api";

export default function PerformanceDashboard() {
  const [performanceData, setPerformanceData] = useState<PerformanceData[]>([]);
  const [indexImpact, setIndexImpact] = useState<IndexImpact[]>([]);
  const [explainStats, setExplainStats] = useState<ExplainStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchPerformanceData();
        setPerformanceData(data.performance || []);
        setIndexImpact(data.indexImpact || []);
        setExplainStats(data.explainStats || null);
      } catch (err) {
        console.error("Failed to fetch performance data:", err);
        setError(err instanceof Error ? err.message : "Failed to load performance data");
      } finally {
        setLoading(false);
      }
    }

    void loadData();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      void loadData();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-background">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card>
            <CardContent className="p-8">
              <p className="text-center">Loading performance data...</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-background">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card>
            <CardContent className="p-8">
              <p className="text-center text-destructive">Error: {error}</p>
              <p className="text-center text-sm text-muted-foreground mt-2">
                Make sure the API server is running on http://localhost:8000
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-background">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div>
          <h1 className="text-4xl font-bold mb-2">Performance Dashboard</h1>
          <p className="text-muted-foreground">
            Query performance metrics and index optimization impact
          </p>
        </div>

        {/* EXPLAIN Statistics */}
        {explainStats && (
          <Card>
            <CardHeader>
              <CardTitle>EXPLAIN Integration Statistics</CardTitle>
              <CardDescription>
                Success rate and usage metrics for query plan analysis
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Success Rate</p>
                  <p className="text-2xl font-bold">
                    {explainStats.success_rate?.toFixed(1) || 0}%
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Attempts</p>
                  <p className="text-2xl font-bold">{explainStats.total_attempts || 0}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Cache Hit Rate</p>
                  <p className="text-2xl font-bold">
                    {explainStats.cached_hit_rate?.toFixed(1) || 0}%
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Fast EXPLAIN</p>
                  <p className="text-2xl font-bold">
                    {explainStats.fast_explain_rate?.toFixed(1) || 0}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Query Performance Over Time */}
        {performanceData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Query Performance Trends</CardTitle>
              <CardDescription>Average and P95 latency over time</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={performanceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line
                    type="monotone"
                    dataKey="avgLatency"
                    stroke="#8884d8"
                    name="Avg Latency (ms)"
                  />
                  <Line
                    type="monotone"
                    dataKey="p95Latency"
                    stroke="#82ca9d"
                    name="P95 Latency (ms)"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Index Impact */}
        {indexImpact.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Index Impact Analysis</CardTitle>
              <CardDescription>
                Performance improvement from index optimizations
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={450}>
                <BarChart data={indexImpact.slice(0, 20)} margin={{ bottom: 120, top: 10, right: 10, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="indexName"
                    angle={-45}
                    textAnchor="end"
                    height={100}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ fontSize: 12 }} />
                  <Legend wrapperStyle={{ paddingTop: "20px", fontSize: 12 }} />
                  <Bar dataKey="improvement" fill="#8884d8" name="Improvement %" />
                  <Bar dataKey="queryCount" fill="#82ca9d" name="Query Count" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Query Count Over Time */}
        <Card>
          <CardHeader>
            <CardTitle>Query Volume</CardTitle>
            <CardDescription>Total queries and index usage over time</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="queryCount"
                  stroke="#8884d8"
                  name="Total Queries"
                />
                <Line
                  type="monotone"
                  dataKey="indexHits"
                  stroke="#82ca9d"
                  name="Index Hits"
                />
                <Line
                  type="monotone"
                  dataKey="indexMisses"
                  stroke="#ffc658"
                  name="Index Misses"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

