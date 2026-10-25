"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, ShieldCheck, Play, CheckCircle2, ChevronRight, Filter } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Modal } from "../../components/ui/modal";
import { Input } from "../../components/ui/input";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { Anomaly, Dataset } from "../../lib/types";

export default function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanModalOpen, setIsScanModalOpen] = useState(false);

  // Scan modal form state
  const [scanDatasetId, setScanDatasetId] = useState("");
  const [scanMetric, setScanMetric] = useState("");
  const [scanMethod, setScanMethod] = useState("z_score");
  const [isScanning, setIsScanning] = useState(false);

  const fetchData = () => {
    setIsLoading(true);
    Promise.all([
      ApiClient.getAnomalies().catch(() => []),
      ApiClient.getDatasets().catch(() => []),
    ]).then(([anoms, ds]) => {
      setAnomalies(anoms);
      setDatasets(ds);
      if (ds.length > 0) setScanDatasetId(ds[0].id);
      setIsLoading(false);
    });
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRunScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scanDatasetId || !scanMetric.trim()) return;

    setIsScanning(true);
    try {
      const results = await ApiClient.triggerAnomalyScan({
        dataset_id: scanDatasetId,
        metric_column: scanMetric.trim(),
        method: scanMethod,
      });
      setIsScanModalOpen(false);
      setScanMetric("");
      fetchData();
      alert(`Scan complete. Found ${results.length} statistically anomalous data points.`);
    } catch (err: any) {
      alert(`Scan failed: ${err.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <DashboardLayout title="Statistical Anomaly Alerts">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-gray-500">
              Automated outliers, unexpected deviations, and sudden spikes detected in time series
            </h2>
          </div>
          <Button onClick={() => setIsScanModalOpen(true)} className="gap-2 text-xs" size="sm">
            <Play className="w-3.5 h-3.5" />
            <span>Run Anomaly Scan</span>
          </Button>
        </div>

        {/* Notice on statistical rigor */}
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Statistical Rigor Guarantee:</span> All anomalies are computed using formal statistical bounds (Z-Score & IQR deviations). Anomalies represent statistical observations only; the system never claims unproven business causation without evidence.
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading anomalies...</div>
        ) : anomalies.length === 0 ? (
          <EmptyState
            title="No Anomalies Detected"
            description="Run a statistical scan on your dataset's numeric columns (e.g. revenue, volume, latency) to detect outliers."
            actionText="Run Scan"
            onAction={() => setIsScanModalOpen(true)}
            icon={<CheckCircle2 className="w-6 h-6 text-emerald-600" />}
          />
        ) : (
          <div className="space-y-3">
            {anomalies.map((anom) => {
              const severityVariant =
                anom.severity === "critical"
                  ? "danger"
                  : anom.severity === "high"
                  ? "warning"
                  : "default";

              return (
                <div
                  key={anom.id}
                  className="p-5 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant={severityVariant} className="uppercase text-[10px]">
                        {anom.severity} Severity
                      </Badge>
                      <span className="text-xs font-semibold text-gray-900">
                        {anom.metric_name}
                      </span>
                      <span className="text-xs text-gray-400">via {anom.detection_method}</span>
                    </div>

                    <p className="text-xs text-gray-600 max-w-2xl">{anom.explanation}</p>

                    <div className="flex items-center gap-4 text-[11px] text-gray-400 pt-1">
                      <span>Observed: <strong className="text-gray-700">{anom.metric_value}</strong></span>
                      <span>Expected Baseline: <strong className="text-gray-700">{anom.expected_value}</strong></span>
                      <span>Deviation Score: <strong className="text-indigo-600">{anom.deviation_score}x</strong></span>
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0 text-xs text-gray-400">
                    <Badge variant={anom.status === "detected" ? "warning" : "success"}>
                      {anom.status}
                    </Badge>
                    <p className="text-[10px] text-gray-400 mt-1">
                      {new Date(anom.detected_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Scan Modal */}
        <Modal
          isOpen={isScanModalOpen}
          onClose={() => setIsScanModalOpen(false)}
          title="Run Statistical Anomaly Scan"
          description="Select a dataset and metric to compute deviations against historical baselines."
        >
          <form onSubmit={handleRunScan} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Dataset
              </label>
              <select
                value={scanDatasetId}
                onChange={(e) => setScanDatasetId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-1 focus:ring-indigo-500"
                required
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.table_name})
                  </option>
                ))}
              </select>
            </div>

            <Input
              label="Metric Column Name"
              value={scanMetric}
              onChange={(e) => setScanMetric(e.target.value)}
              placeholder="e.g. revenue, amount, transactions"
              required
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Detection Method
              </label>
              <select
                value={scanMethod}
                onChange={(e) => setScanMethod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-1 focus:ring-indigo-500"
              >
                <option value="z_score">Z-Score (Standard Deviations from Mean)</option>
                <option value="iqr">Interquartile Range (IQR Median Spread)</option>
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <Button variant="outline" type="button" onClick={() => setIsScanModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isScanning}>
                Run Scan
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
