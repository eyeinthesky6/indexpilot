"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  fetchDecisionsData,
  type DecisionExplanation,
  type DecisionsResponse,
} from "@/lib/api";
import { CheckCircle2, XCircle, Info, TrendingUp, DollarSign, Zap } from "lucide-react";

const COLORS = {
  created: "#82ca9d",
  skipped: "#ffc658",
  advisory: "#8884d8",
};

export default function DecisionsDashboard() {
  const [decisions, setDecisions] = useState<DecisionExplanation[]>([]);
  const [summary, setSummary] = useState<DecisionsResponse["summary"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDecision, setSelectedDecision] = useState<DecisionExplanation | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchDecisionsData(100);
        setDecisions(data.decisions || []);
        setSummary(data.summary || null);
      } catch (err) {
        console.error("Failed to fetch decisions data:", err);
        setError(err instanceof Error ? err.message : "Failed to load decisions data");
      } finally {
        setLoading(false);
      }
    }

    void loadData();

    // Refresh every 60 seconds
    const interval = setInterval(() => {
      void loadData();
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="container mx-auto">
          <Card>
            <CardContent className="p-8">
              <p className="text-center">Loading decision explanations...</p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background p-8">
        <div className="container mx-auto">
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

  // Prepare chart data
  const decisionTypeData = [
    { name: "Created", value: summary?.totalCreated || 0 },
    { name: "Skipped", value: summary?.totalSkipped || 0 },
  ];

  const confidenceData = decisions
    .filter((d) => d.wasCreated)
    .map((d) => ({
      name: d.indexName || `${d.tableName}.${d.fieldName}`,
      confidence: d.confidence,
    }))
    .slice(0, 10)
    .sort((a, b) => b.confidence - a.confidence);

  const costBenefitData = decisions
    .filter((d) => d.wasCreated && d.costBenefitRatio > 0)
    .map((d) => ({
      name: d.indexName || `${d.tableName}.${d.fieldName}`,
      costBenefit: d.costBenefitRatio,
      improvement: d.improvementPct,
    }))
    .slice(0, 10)
    .sort((a, b) => b.costBenefit - a.costBenefit);

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="container mx-auto space-y-6">
        <div>
          <h1 className="text-4xl font-bold mb-2">Decision Explanations</h1>
          <p className="text-muted-foreground">
            Understand why indexes were created or skipped, with full cost-benefit analysis
          </p>
        </div>

        {/* Summary Cards */}
        {summary && (
          <div className="grid gap-6 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Decisions</CardTitle>
                <Info className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summary.totalDecisions}</div>
                <p className="text-xs text-muted-foreground">Last 30 days</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Indexes Created</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">{summary.totalCreated}</div>
                <p className="text-xs text-muted-foreground">
                  {summary.creationRate.toFixed(1)}% creation rate
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Indexes Skipped</CardTitle>
                <XCircle className="h-4 w-4 text-yellow-600" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-yellow-600">{summary.totalSkipped}</div>
                <p className="text-xs text-muted-foreground">Not beneficial</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Confidence</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {decisions.length > 0
                    ? (
                        decisions.reduce((sum, d) => sum + d.confidence, 0) / decisions.length
                      ).toFixed(1)
                    : "0"}
                </div>
                <p className="text-xs text-muted-foreground">Decision confidence</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Decision Type Distribution */}
        {decisionTypeData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Decision Distribution</CardTitle>
              <CardDescription>Created vs Skipped indexes</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={decisionTypeData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {decisionTypeData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.name === "Created" ? COLORS.created : COLORS.skipped}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Confidence Analysis */}
        {confidenceData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Top Indexes by Confidence</CardTitle>
              <CardDescription>Highest confidence index creation decisions</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={confidenceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    angle={-45}
                    textAnchor="end"
                    height={100}
                  />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="confidence" fill="#8884d8" name="Confidence" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Cost-Benefit Analysis */}
        {costBenefitData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Cost-Benefit Analysis</CardTitle>
              <CardDescription>Indexes with best cost-benefit ratios</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={costBenefitData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="name"
                    angle={-45}
                    textAnchor="end"
                    height={100}
                  />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="costBenefit" fill="#82ca9d" name="Cost-Benefit Ratio" />
                  <Bar dataKey="improvement" fill="#ffc658" name="Improvement %" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Decision Details Table */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Decisions</CardTitle>
            <CardDescription>
              Detailed explanations for index creation decisions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Index</th>
                    <th className="text-left p-2">Table.Field</th>
                    <th className="text-left p-2">Decision</th>
                    <th className="text-left p-2">Reason</th>
                    <th className="text-right p-2">Confidence</th>
                    <th className="text-right p-2">Queries</th>
                    <th className="text-right p-2">Cost-Benefit</th>
                    <th className="text-left p-2">Date</th>
                    <th className="text-left p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.slice(0, 20).map((decision) => (
                    <tr
                      key={decision.id}
                      className="border-b hover:bg-muted/50 cursor-pointer"
                      onClick={() => setSelectedDecision(decision)}
                    >
                      <td className="p-2 font-mono text-sm">
                        {decision.indexName || "N/A"}
                      </td>
                      <td className="p-2">
                        {decision.tableName}.{decision.fieldName}
                      </td>
                      <td className="p-2">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs ${
                            decision.wasCreated
                              ? "bg-green-100 text-green-800"
                              : "bg-yellow-100 text-yellow-800"
                          }`}
                        >
                          {decision.wasCreated ? (
                            <>
                              <CheckCircle2 className="h-3 w-3" />
                              Created
                            </>
                          ) : (
                            <>
                              <XCircle className="h-3 w-3" />
                              Skipped
                            </>
                          )}
                        </span>
                      </td>
                      <td className="p-2 text-sm text-muted-foreground max-w-xs truncate">
                        {decision.reason || "N/A"}
                      </td>
                      <td className="p-2 text-right">
                        {(decision.confidence * 100).toFixed(1)}%
                      </td>
                      <td className="p-2 text-right">{decision.queriesAnalyzed}</td>
                      <td className="p-2 text-right">
                        {decision.costBenefitRatio > 0
                          ? decision.costBenefitRatio.toFixed(2)
                          : "N/A"}
                      </td>
                      <td className="p-2 text-sm text-muted-foreground">
                        {new Date(decision.createdAt).toLocaleDateString()}
                      </td>
                      <td className="p-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedDecision(decision);
                          }}
                        >
                          View Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Decision Detail Modal */}
        {selectedDecision && (
          <div
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setSelectedDecision(null)}
          >
            <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto m-4">
              <CardHeader>
                <CardTitle>Decision Explanation</CardTitle>
                <CardDescription>
                  Detailed analysis for {selectedDecision.tableName}.{selectedDecision.fieldName}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Index Name</p>
                    <p className="font-mono text-sm">{selectedDecision.indexName || "N/A"}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Decision</p>
                    <p
                      className={`font-semibold ${
                        selectedDecision.wasCreated ? "text-green-600" : "text-yellow-600"
                      }`}
                    >
                      {selectedDecision.wasCreated ? "Created" : "Skipped"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Reason</p>
                    <p className="text-sm">{selectedDecision.reason || "N/A"}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Confidence</p>
                    <p className="text-sm font-semibold">
                      {(selectedDecision.confidence * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h3 className="font-semibold mb-2 flex items-center gap-2">
                    <DollarSign className="h-4 w-4" />
                    Cost-Benefit Analysis
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Build Cost</p>
                      <p className="text-sm font-semibold">
                        {selectedDecision.buildCost.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Query Cost (Before)</p>
                      <p className="text-sm font-semibold">
                        {selectedDecision.queryCostBefore.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Query Cost (After)</p>
                      <p className="text-sm font-semibold">
                        {selectedDecision.queryCostAfter.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Cost-Benefit Ratio</p>
                      <p className="text-sm font-semibold">
                        {selectedDecision.costBenefitRatio.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Improvement</p>
                      <p className="text-sm font-semibold text-green-600">
                        {selectedDecision.improvementPct.toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Queries Analyzed</p>
                      <p className="text-sm font-semibold">{selectedDecision.queriesAnalyzed}</p>
                    </div>
                  </div>
                </div>

                {selectedDecision.queryPatterns.length > 0 && (
                  <div className="border-t pt-4">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Zap className="h-4 w-4" />
                      Query Patterns
                    </h3>
                    <ul className="list-disc list-inside space-y-1">
                      {selectedDecision.queryPatterns.map((pattern, idx) => (
                        <li key={idx} className="text-sm text-muted-foreground">
                          {pattern}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="border-t pt-4">
                  <p className="text-sm text-muted-foreground">Created At</p>
                  <p className="text-sm">
                    {new Date(selectedDecision.createdAt).toLocaleString()}
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button variant="outline" onClick={() => setSelectedDecision(null)}>
                    Close
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

