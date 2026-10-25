"use client";

import React, { useEffect, useState } from "react";
import { FileBarChart, Plus, Clock, Eye, Trash2, Calendar } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Modal } from "../../components/ui/modal";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { Report } from "../../lib/types";

export default function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchReports = () => {
    setIsLoading(true);
    ApiClient.getReports()
      .then(setReports)
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleCreateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setIsSubmitting(true);
    try {
      await ApiClient.createReport({ title, description });
      setIsModalOpen(false);
      setTitle("");
      setDescription("");
      fetchReports();
    } catch (err: any) {
      alert(`Failed to create report: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DashboardLayout title="Saved Business Intelligence Reports">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-gray-500">
              Persistent business summaries, snapshots, and recurring report decks
            </h2>
          </div>
          <Button onClick={() => setIsModalOpen(true)} className="gap-2 text-xs" size="sm">
            <Plus className="w-4 h-4" />
            <span>Create Report Deck</span>
          </Button>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading reports...</div>
        ) : reports.length === 0 ? (
          <EmptyState
            title="No Reports Created"
            description="Create reports from saved AI analyses or build a periodic executive summary."
            actionText="Create Report"
            onAction={() => setIsModalOpen(true)}
            icon={<FileBarChart className="w-6 h-6" />}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reports.map((report) => (
              <Card key={report.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-sm">{report.title}</CardTitle>
                      {report.description && (
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {report.description}
                        </p>
                      )}
                    </div>
                    <Badge variant={report.status === "published" ? "success" : "default"}>
                      {report.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-xs text-gray-600">
                  <div className="p-3 bg-gray-50 rounded-lg flex items-center justify-between">
                    <span className="text-gray-500">Current Version:</span>
                    <span className="font-semibold text-indigo-600">
                      v{report.latest_version?.version_number || 1}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-indigo-600 font-medium hover:underline cursor-pointer">
                      View Snapshot
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Create New Report"
          description="Build an automated business report with versioned data snapshots."
        >
          <form onSubmit={handleCreateReport} className="space-y-4">
            <Input
              label="Report Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Weekly Executive Summary"
              required
            />
            <Input
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Key performance drivers across sales and churn..."
            />

            <div className="flex justify-end gap-3 pt-3">
              <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isSubmitting}>
                Save Report
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
