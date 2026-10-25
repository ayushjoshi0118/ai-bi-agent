"use client";

import React, { useEffect, useState } from "react";
import { ShieldCheck, Search, Filter } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { AuditEvent } from "../../lib/types";

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    ApiClient.getAuditLogs()
      .then(setLogs)
      .catch(() => [])
      .finally(() => setIsLoading(false));
  }, []);

  const filteredLogs = logs.filter(
    (l) =>
      l.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.resource_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      JSON.stringify(l.details || {}).toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <DashboardLayout title="Security & Compliance Audit Trail">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-medium text-gray-500">
              Immutable ledger of all logins, SQL queries, rejected statements, and role changes
            </h2>
          </div>
          <div className="w-full sm:w-64">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search audit actions..."
              className="w-full px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        <Card>
          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="p-12 text-center text-xs text-gray-400">Loading audit trail...</div>
            ) : filteredLogs.length === 0 ? (
              <div className="p-12 text-center text-xs text-gray-400">No audit events found.</div>
            ) : (
              <table className="w-full text-left text-xs text-gray-600">
                <thead className="bg-gray-50 text-gray-700 font-semibold border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Client IP</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 font-mono text-[11px]">
                  {filteredLogs.map((log) => {
                    const isRejected = log.action.includes("rejected") || log.action.includes("failed");
                    return (
                      <tr key={log.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap text-gray-400">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <Badge variant={isRejected ? "danger" : "default"} className="font-mono text-[10px]">
                            {log.action}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-gray-700">
                          {log.resource_type || "-"}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-gray-500">
                          {log.ip_address || "internal"}
                        </td>
                        <td className="px-4 py-3 text-gray-600 max-w-xs truncate">
                          {log.details ? JSON.stringify(log.details) : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
