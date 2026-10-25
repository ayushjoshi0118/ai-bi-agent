"use client";

import React, { useEffect, useState } from "react";
import {
  Upload,
  Database,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Server,
  Loader2,
} from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Modal } from "../../components/ui/modal";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { DataSource } from "../../lib/types";

export default function DataSourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"file" | "postgres">("file");

  // File Upload State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [isUploading, setIsUploading] = useState(false);

  // PostgreSQL Form State
  const [pgName, setPgName] = useState("");
  const [pgHost, setPgHost] = useState("");
  const [pgPort, setPgPort] = useState(5432);
  const [pgDatabase, setPgDatabase] = useState("");
  const [pgUsername, setPgUsername] = useState("");
  const [pgPassword, setPgPassword] = useState("");
  const [pgSchema, setPgSchema] = useState("public");
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const fetchSources = () => {
    setIsLoading(true);
    ApiClient.getDataSources()
      .then(setSources)
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    try {
      await ApiClient.uploadFile(selectedFile, datasetName || undefined);
      setIsModalOpen(false);
      setSelectedFile(null);
      setDatasetName("");
      fetchSources();
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handlePostgresSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsTesting(true);
    setTestResult(null);

    try {
      await ApiClient.createPostgresSource({
        name: pgName,
        host: pgHost,
        port: pgPort,
        database: pgDatabase,
        username: pgUsername,
        password: pgPassword,
        schema_name: pgSchema,
      });
      setIsModalOpen(false);
      fetchSources();
    } catch (err: any) {
      alert(`Failed to save PostgreSQL source: ${err.message}`);
    } finally {
      setIsTesting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm("Are you sure you want to delete this data source and associated datasets?")) {
      await ApiClient.deleteDataSource(id);
      fetchSources();
    }
  };

  return (
    <DashboardLayout title="Data Sources">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-gray-500">
              Manage external PostgreSQL connections and uploaded datasets
            </h2>
          </div>
          <Button onClick={() => setIsModalOpen(true)} className="gap-2 text-xs" size="sm">
            <Plus className="w-4 h-4" />
            <span>Connect Data Source</span>
          </Button>
        </div>

        {/* Data Source Grid */}
        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading data sources...</div>
        ) : sources.length === 0 ? (
          <EmptyState
            title="No Data Sources Connected"
            description="Connect a PostgreSQL database or upload a CSV/Excel file to start running natural language queries."
            actionText="Add Data Source"
            onAction={() => setIsModalOpen(true)}
            icon={<Database className="w-6 h-6" />}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sources.map((source) => (
              <Card key={source.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                      {source.source_type === "postgresql" ? (
                        <Server className="w-4 h-4" />
                      ) : (
                        <FileSpreadsheet className="w-4 h-4" />
                      )}
                    </div>
                    <div>
                      <CardTitle className="text-sm truncate max-w-[160px]">{source.name}</CardTitle>
                      <p className="text-[11px] text-gray-400 uppercase tracking-wider">
                        {source.source_type}
                      </p>
                    </div>
                  </div>
                  <Badge variant={source.status === "connected" ? "success" : "warning"}>
                    {source.status}
                  </Badge>
                </CardHeader>
                <CardContent className="space-y-3 text-xs text-gray-600">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-400">Discovered Tables:</span>
                    <span className="font-semibold">{source.dataset_count || 1} table</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-400">Credentials:</span>
                    <span className="font-mono text-emerald-600 font-medium">AES-256 Encrypted</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-400">Last Synced:</span>
                    <span>
                      {source.last_synced_at
                        ? new Date(source.last_synced_at).toLocaleDateString()
                        : "Pending"}
                    </span>
                  </div>

                  <div className="pt-2 border-t flex justify-end">
                    <button
                      onClick={() => handleDelete(source.id)}
                      className="text-gray-400 hover:text-red-600 p-1 rounded transition-colors"
                      title="Delete Source"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Modal for Adding Data Source */}
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Connect Data Source"
          description="Choose a data connection type to begin analyzing your data."
        >
          {/* Tabs */}
          <div className="flex border-b border-gray-200 mb-6">
            <button
              onClick={() => setActiveTab("file")}
              className={`pb-2.5 px-4 text-xs font-medium border-b-2 transition-colors ${
                activeTab === "file"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              CSV / Excel Upload
            </button>
            <button
              onClick={() => setActiveTab("postgres")}
              className={`pb-2.5 px-4 text-xs font-medium border-b-2 transition-colors ${
                activeTab === "postgres"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              PostgreSQL Database
            </button>
          </div>

          {activeTab === "file" ? (
            /* File Upload Form */
            <form onSubmit={handleFileUpload} className="space-y-4">
              <Input
                label="Dataset Name (Optional)"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder="e.g. Q3 Sales & Revenue"
              />

              <div className="p-6 border-2 border-dashed border-gray-300 rounded-xl text-center hover:bg-gray-50 transition-colors">
                <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-xs text-gray-600 font-medium">
                  {selectedFile ? selectedFile.name : "Click to browse or drag & drop CSV/XLSX"}
                </p>
                <p className="text-[10px] text-gray-400 mt-1">Up to 50MB file size</p>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="file-upload"
                  required
                />
                <label
                  htmlFor="file-upload"
                  className="mt-3 inline-block cursor-pointer px-3 py-1.5 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
                >
                  Browse Computer
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" isLoading={isUploading} disabled={!selectedFile}>
                  Upload & Profile
                </Button>
              </div>
            </form>
          ) : (
            /* PostgreSQL Connection Form */
            <form onSubmit={handlePostgresSubmit} className="space-y-3">
              <Input
                label="Connection Name"
                value={pgName}
                onChange={(e) => setPgName(e.target.value)}
                placeholder="Production Analytics DB"
                required
              />
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <Input
                    label="Host / Endpoint"
                    value={pgHost}
                    onChange={(e) => setPgHost(e.target.value)}
                    placeholder="db.company.com"
                    required
                  />
                </div>
                <div>
                  <Input
                    label="Port"
                    type="number"
                    value={pgPort}
                    onChange={(e) => setPgPort(Number(e.target.value))}
                    required
                  />
                </div>
              </div>
              <Input
                label="Database Name"
                value={pgDatabase}
                onChange={(e) => setPgDatabase(e.target.value)}
                placeholder="analytics_prod"
                required
              />
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="Username"
                  value={pgUsername}
                  onChange={(e) => setPgUsername(e.target.value)}
                  placeholder="read_only_user"
                  required
                />
                <Input
                  label="Password"
                  type="password"
                  value={pgPassword}
                  onChange={(e) => setPgPassword(e.target.value)}
                  placeholder="••••••••••••"
                  required
                />
              </div>
              <Input
                label="Schema (Default: public)"
                value={pgSchema}
                onChange={(e) => setPgSchema(e.target.value)}
                placeholder="public"
              />

              <div className="p-3 bg-gray-50 border rounded-lg text-[11px] text-gray-500">
                Database passwords are encrypted in storage using Fernet symmetric encryption and executed under strict read-only transactions.
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" isLoading={isTesting}>
                  Save & Introspect
                </Button>
              </div>
            </form>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
}
