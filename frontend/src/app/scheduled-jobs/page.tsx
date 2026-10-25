"use client";

import React, { useEffect, useState } from "react";
import { Clock, Plus, Play, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { DashboardLayout } from "../../components/layout/dashboard-layout";
import { Card, CardHeader, CardTitle, CardContent } from "../../components/ui/card";
import { Button } from "../../components/ui/button";
import { Badge } from "../../components/ui/badge";
import { Modal } from "../../components/ui/modal";
import { Input } from "../../components/ui/input";
import { EmptyState } from "../../components/ui/empty-state";
import { ApiClient } from "../../lib/api";
import { ScheduledJob } from "../../lib/types";

export default function ScheduledJobsPage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [jobType, setJobType] = useState<"report" | "anomaly_scan">("report");
  const [scheduleCron, setScheduleCron] = useState("0 9 * * 1"); // Monday 9am
  const [timezone, setTimezone] = useState("UTC");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchJobs = () => {
    setIsLoading(true);
    ApiClient.getScheduledJobs()
      .then(setJobs)
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    try {
      await ApiClient.createScheduledJob({
        name,
        job_type: jobType,
        schedule_cron: scheduleCron,
        timezone,
      });
      setIsModalOpen(false);
      setName("");
      fetchJobs();
    } catch (err: any) {
      alert(`Failed to schedule job: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DashboardLayout title="Scheduled Background Jobs & Automation">
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-gray-500">
              Durable cron-scheduled summaries, recurring anomaly scanners, and run history
            </h2>
          </div>
          <Button onClick={() => setIsModalOpen(true)} className="gap-2 text-xs" size="sm">
            <Plus className="w-4 h-4" />
            <span>Create Scheduled Job</span>
          </Button>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading scheduled jobs...</div>
        ) : jobs.length === 0 ? (
          <EmptyState
            title="No Scheduled Jobs"
            description="Automate weekly summary generation or recurring anomaly scans with Celery & Redis."
            actionText="Schedule Job"
            onAction={() => setIsModalOpen(true)}
            icon={<Clock className="w-6 h-6" />}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {jobs.map((job) => (
              <Card key={job.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm">{job.name}</CardTitle>
                    <p className="text-[11px] text-gray-400 uppercase tracking-wider mt-0.5">
                      {job.job_type}
                    </p>
                  </div>
                  <Badge variant={job.is_active ? "success" : "default"}>
                    {job.is_active ? "Active" : "Paused"}
                  </Badge>
                </CardHeader>
                <CardContent className="space-y-3 text-xs text-gray-600">
                  <div className="p-3 bg-gray-50 rounded-lg flex items-center justify-between font-mono text-[11px]">
                    <span className="text-gray-500">Cron:</span>
                    <span className="font-semibold text-gray-800">{job.schedule_cron}</span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400">
                    <span>Timezone: {job.timezone}</span>
                    <span>
                      Last Run: {job.last_run_at ? new Date(job.last_run_at).toLocaleDateString() : "Pending"}
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create Scheduled Job Modal */}
        <Modal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          title="Schedule Recurring Job"
          description="Create automated jobs executed durably on background workers."
        >
          <form onSubmit={handleCreateJob} className="space-y-4">
            <Input
              label="Job Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Weekly Sales Summary"
              required
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Workflow Type
              </label>
              <select
                value={jobType}
                onChange={(e) => setJobType(e.target.value as any)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-1 focus:ring-indigo-500"
              >
                <option value="report">Executive Report Snapshot</option>
                <option value="anomaly_scan">Automated Anomaly Scan</option>
              </select>
            </div>

            <Input
              label="Cron Expression (Standard 5-Part Syntax)"
              value={scheduleCron}
              onChange={(e) => setScheduleCron(e.target.value)}
              placeholder="0 9 * * 1 (Every Monday at 9:00 AM)"
              required
            />

            <Input
              label="Timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="UTC, America/New_York, etc."
            />

            <div className="flex justify-end gap-3 pt-3">
              <Button variant="outline" type="button" onClick={() => setIsModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isSubmitting}>
                Save Schedule
              </Button>
            </div>
          </form>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
