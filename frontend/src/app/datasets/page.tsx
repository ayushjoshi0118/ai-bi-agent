"use client";

import React, { useEffect, useState } from "react";
import { Table2, Eye, Calendar, Hash, CheckCircle2, ChevronRight, X } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";
import { Modal } from "../../components/ui/modal";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { Dataset, DatasetSchema } from "../../lib/types";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedDataset, setSelectedDataset] = useState<DatasetSchema | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  useEffect(() => {
    ApiClient.getDatasets()
      .then(setDatasets)
      .finally(() => setIsLoading(false));
  }, []);

  const handleInspect = async (id: string) => {
    setIsPreviewLoading(true);
    try {
      const details = await ApiClient.getDatasetDetails(id);
      setSelectedDataset(details);
    } catch (err: any) {
      alert(`Could not load schema: ${err.message}`);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  return (
    <DashboardLayout title="Datasets & Schema Explorer">
      <div className="space-y-6">
        <div>
          <h2 className="text-sm font-medium text-gray-500">
            Introspected database tables, profiled column types, and sample previews
          </h2>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading datasets...</div>
        ) : datasets.length === 0 ? (
          <EmptyState
            title="No Datasets Discovered"
            description="Upload a CSV or connect a PostgreSQL database to inspect schemas and profile columns."
            icon={<Table2 className="w-6 h-6" />}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {datasets.map((d) => (
              <Card key={d.id} className="hover:shadow-md transition-shadow flex flex-col justify-between">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div className="truncate">
                      <CardTitle className="text-sm truncate">{d.name}</CardTitle>
                      <p className="text-xs font-mono text-gray-400 mt-0.5">{d.table_name}</p>
                    </div>
                    <Badge variant={d.status === "ready" ? "success" : "default"}>
                      {d.status}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 p-3 bg-gray-50 rounded-lg text-xs">
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">
                        Rows
                      </span>
                      <span className="font-semibold text-gray-800">
                        {d.row_count?.toLocaleString() || 0}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400 block text-[10px] uppercase font-semibold">
                        Columns
                      </span>
                      <span className="font-semibold text-gray-800">{d.column_count || 0} cols</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400 pt-1">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {d.profiled_at ? new Date(d.profiled_at).toLocaleDateString() : "Just now"}
                    </span>
                    <button
                      onClick={() => handleInspect(d.id)}
                      className="text-indigo-600 font-semibold hover:underline flex items-center gap-1"
                    >
                      <span>View Schema</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Schema Viewer Modal */}
        {selectedDataset && (
          <Modal
            isOpen={!!selectedDataset}
            onClose={() => setSelectedDataset(null)}
            title={`Schema: ${selectedDataset.name || selectedDataset.table_name}`}
            description={`Table: ${selectedDataset.table_name} • ${selectedDataset.row_count || 0} rows`}
            className="max-w-3xl"
          >
            <div className="space-y-6">
              {/* Columns Table */}
              <div>
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                  Column Profiling ({selectedDataset.columns?.length || 0} columns)
                </h4>
                <div className="border border-gray-200 rounded-lg overflow-hidden max-h-60 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold">
                      <tr>
                        <th className="px-3 py-2">Column Name</th>
                        <th className="px-3 py-2">Data Type</th>
                        <th className="px-3 py-2">Nullable</th>
                        <th className="px-3 py-2">Key</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {selectedDataset.columns.map((c) => (
                        <tr key={c.name} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-mono font-medium text-gray-900">{c.name}</td>
                          <td className="px-3 py-2 font-mono text-indigo-600">{c.data_type}</td>
                          <td className="px-3 py-2 text-gray-500">{c.nullable ? "YES" : "NO"}</td>
                          <td className="px-3 py-2 text-gray-500">
                            {c.is_primary_key ? <Badge variant="info">PK</Badge> : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Sample Preview Rows */}
              {selectedDataset.sample_data && selectedDataset.sample_data.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                    Sample Data Preview (First 5 Rows)
                  </h4>
                  <div className="border border-gray-200 rounded-lg overflow-x-auto max-h-48 overflow-y-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-gray-50 border-b border-gray-200 text-gray-600 font-semibold">
                        <tr>
                          {Object.keys(selectedDataset.sample_data[0]).map((k) => (
                            <th key={k} className="px-3 py-2 whitespace-nowrap">
                              {k}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 font-mono text-[11px]">
                        {selectedDataset.sample_data.slice(0, 5).map((row, idx) => (
                          <tr key={idx} className="hover:bg-gray-50">
                            {Object.values(row).map((val: any, cIdx) => (
                              <td key={cIdx} className="px-3 py-2 whitespace-nowrap text-gray-700">
                                {String(val ?? "-")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </Modal>
        )}
      </div>
    </DashboardLayout>
  );
}
