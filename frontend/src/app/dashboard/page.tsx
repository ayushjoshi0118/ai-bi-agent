"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Database,
  Terminal,
  FileBarChart,
  AlertTriangle,
  ArrowRight,
  Upload,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { KPICard } from "../../components/ui/kpi-card";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { ApiClient } from "../../lib/api";
import { Conversation, Dataset, QueryExecution } from "../../lib/types";

export default function DashboardPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [queries, setQueries] = useState<QueryExecution[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [anomaliesCount, setAnomaliesCount] = useState<number>(0);
  const [reportsCount, setReportsCount] = useState<number>(0);

  useEffect(() => {
    Promise.all([
      ApiClient.getDatasets().catch(() => []),
      ApiClient.getQueryExecutions().catch(() => []),
      ApiClient.getConversations().catch(() => []),
      ApiClient.getAnomalies().catch(() => []),
      ApiClient.getReports().catch(() => []),
    ]).then(([ds, qs, cs, anoms, reps]) => {
      setDatasets(ds);
      setQueries(qs);
      setConversations(cs);
      setAnomaliesCount(anoms.length);
      setReportsCount(reps.length);
    });
  }, []);

  return (
    <DashboardLayout title="Operational Dashboard">
      <div className="space-y-8">
        {/* Welcome Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-gradient-to-r from-indigo-900 to-indigo-800 rounded-2xl text-white shadow-sm">
          <div>
            <h2 className="text-xl font-bold tracking-tight">AI Business Intelligence Agent</h2>
            <p className="text-xs text-indigo-200 mt-1 max-w-xl">
              Ask questions across connected databases, discover automated insights, and run deterministic read-only queries with zero hallucinations.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/data-sources">
              <Button variant="secondary" size="sm" className="gap-1.5 text-xs">
                <Upload className="w-3.5 h-3.5" />
                <span>Upload Data</span>
              </Button>
            </Link>
            <Link href="/chat">
              <Button size="sm" className="gap-1.5 text-xs bg-white text-indigo-900 hover:bg-indigo-50">
                <MessageSquare className="w-3.5 h-3.5 text-indigo-600" />
                <span>Ask AI Question</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Real Metrics KPI Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <KPICard
            title="Connected Datasets"
            value={datasets.length}
            subtitle={`${datasets.reduce((acc, d) => acc + (d.row_count || 0), 0).toLocaleString()} rows tracked`}
            icon={<Database className="w-5 h-5 text-indigo-600" />}
          />
          <KPICard
            title="Executed Queries"
            value={queries.length}
            subtitle="100% read-only & validated"
            icon={<Terminal className="w-5 h-5 text-cyan-600" />}
          />
          <KPICard
            title="Anomalies Caught"
            value={anomaliesCount}
            subtitle="Statistical outliers detected"
            changeDirection={anomaliesCount > 0 ? "up" : "neutral"}
            icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
          />
          <KPICard
            title="Active Reports"
            value={reportsCount}
            subtitle="Automated summaries"
            icon={<FileBarChart className="w-5 h-5 text-purple-600" />}
          />
        </div>

        {/* Recent Activity Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Analysis Conversations */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-sm">Recent AI Analyses</CardTitle>
              <Link href="/chat" className="text-xs text-indigo-600 hover:underline flex items-center gap-1 font-medium">
                <span>Open Chat Workspace</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </CardHeader>
            <CardContent>
              {conversations.length === 0 ? (
                <div className="py-8 text-center text-xs text-gray-400">
                  No conversations yet. Ask your first question to generate analysis!
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {conversations.slice(0, 5).map((conv) => (
                    <Link
                      key={conv.id}
                      href={`/chat?id=${conv.id}`}
                      className="py-3 flex items-center justify-between hover:bg-gray-50 px-2 rounded-lg transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg group-hover:bg-indigo-100 transition-colors">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900 group-hover:text-indigo-600 transition-colors">
                            {conv.title}
                          </p>
                          <p className="text-xs text-gray-400">
                            {new Date(conv.updated_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-indigo-600 transition-colors" />
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Connected Data Sources Preview */}
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle className="text-sm">Data Repositories</CardTitle>
              <Link href="/data-sources" className="text-xs text-indigo-600 hover:underline">
                Manage
              </Link>
            </CardHeader>
            <CardContent>
              {datasets.length === 0 ? (
                <div className="py-8 text-center text-xs text-gray-400">
                  No datasets uploaded. Upload a CSV or connect PostgreSQL.
                </div>
              ) : (
                <div className="space-y-3">
                  {datasets.slice(0, 5).map((d) => (
                    <div key={d.id} className="p-3 bg-gray-50 rounded-lg border border-gray-100 flex items-center justify-between">
                      <div className="truncate pr-2">
                        <p className="text-xs font-semibold text-gray-800 truncate">{d.name}</p>
                        <p className="text-[10px] text-gray-400 uppercase tracking-wider">{d.table_name}</p>
                      </div>
                      <span className="text-xs font-medium text-gray-500 flex-shrink-0">
                        {d.row_count?.toLocaleString() || 0} rows
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
