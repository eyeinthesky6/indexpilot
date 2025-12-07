"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface IndexHealth {
  indexName: string;
  tableName: string;
  bloatPercent: number;
  sizeMB: number;
  usageCount: number;
  lastUsed: string;
  healthStatus: "healthy" | "warning" | "critical";
}

interface HealthSummary {
  totalIndexes: number;
  healthyIndexes: number;
  warningIndexes: number;
  criticalIndexes: number;
  totalSizeMB: number;
  avgBloatPercent: number;
}

const COLORS = {
  healthy: "#82ca9d",
  warning: "#ffc658",
  critical: "#ff6b6b",
};

export default function HealthDashboard() {
  const [healthData, setHealthData] = useState<IndexHealth[]>([]);
  const [summary, setSummary] = useState<HealthSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch health data from API
    fetch("/api/health")
      .then((res) => res.json())
      .then((data) => {
        setHealthData(data.indexes || []);
        setSummary(data.summary || null);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch health data:", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="container mx-auto">
          <p>Loading health data...</p>
        </div>
      </div>
    );
  }

  const healthDistribution = summary
    ? [
        { name: "Healthy", value: summary.healthyIndexes, color: COLORS.healthy },
        { name: "Warning", value: summary.warningIndexes, color: COLORS.warning },
        { name: "Critical", value: summary.criticalIndexes, color: COLORS.critical },
      ]
    : [];

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="container mx-auto space-y-6">
        <div>
          <h1 className="text-4xl font-bold mb-2">Index Health Monitoring</h1>
          <p className="text-muted-foreground">
            Monitor index bloat, usage, and overall system health
          </p>
        </div>

        {/* Summary Cards */}
        {summary && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Indexes</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.totalIndexes}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Healthy</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">
                  {summary.healthyIndexes}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Warning</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">
                  {summary.warningIndexes}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Critical</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">
                  {summary.criticalIndexes}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Health Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Health Distribution</CardTitle>
            <CardDescription>Index health status breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={healthDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {healthDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Bloat Analysis */}
        <Card>
          <CardHeader>
            <CardTitle>Index Bloat Analysis</CardTitle>
            <CardDescription>Bloat percentage by index</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={healthData.slice(0, 20)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="indexName" angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="bloatPercent" fill="#8884d8" name="Bloat %" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Index Size Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Index Size Distribution</CardTitle>
            <CardDescription>Storage usage by index</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={healthData.slice(0, 20)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="indexName" angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="sizeMB" fill="#82ca9d" name="Size (MB)" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Index Details Table */}
        <Card>
          <CardHeader>
            <CardTitle>Index Details</CardTitle>
            <CardDescription>Detailed health information for all indexes</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Index Name</th>
                    <th className="text-left p-2">Table</th>
                    <th className="text-right p-2">Bloat %</th>
                    <th className="text-right p-2">Size (MB)</th>
                    <th className="text-right p-2">Usage</th>
                    <th className="text-left p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {healthData.map((index) => (
                    <tr key={index.indexName} className="border-b">
                      <td className="p-2">{index.indexName}</td>
                      <td className="p-2">{index.tableName}</td>
                      <td className="text-right p-2">
                        {index.bloatPercent.toFixed(1)}%
                      </td>
                      <td className="text-right p-2">{index.sizeMB.toFixed(2)}</td>
                      <td className="text-right p-2">{index.usageCount}</td>
                      <td className="p-2">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            index.healthStatus === "healthy"
                              ? "bg-green-100 text-green-800"
                              : index.healthStatus === "warning"
                                ? "bg-yellow-100 text-yellow-800"
                                : "bg-red-100 text-red-800"
                          }`}
                        >
                          {index.healthStatus}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

