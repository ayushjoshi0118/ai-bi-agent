/**
 * Type-Safe API Client for FastAPI backend.
 */

import {
  Anomaly,
  AuditEvent,
  Conversation,
  DataSource,
  Dataset,
  DatasetSchema,
  Member,
  Message,
  Organization,
  QueryExecution,
  Report,
  ScheduledJob,
  User,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiClient {
  private static getAccessToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private static getActiveOrgId(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("active_org_id");
  }

  public static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getAccessToken();
    const orgId = this.getActiveOrgId();

    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (orgId) {
      headers["X-Org-ID"] = orgId;
    }

    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (response.status === 401 && typeof window !== "undefined") {
      // Clear expired credentials and redirect to login if unauthorized
      localStorage.removeItem("access_token");
      if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/signup")) {
        window.location.href = "/login";
      }
    }

    if (!response.ok) {
      let errMessage = "An error occurred";
      try {
        const errorData = await response.json();
        errMessage = errorData.message || errorData.detail || errMessage;
      } catch {
        errMessage = response.statusText;
      }
      throw new Error(errMessage);
    }

    return response.json();
  }

  // --- Auth & Users ---
  static async signup(data: { email: string; password: string; full_name: string }) {
    return this.request<{ user: User; tokens: { access_token: string; refresh_token: string } }>(
      "/auth/signup",
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  static async login(data: { email: string; password: string }) {
    return this.request<{ user: User; tokens: { access_token: string; refresh_token: string } }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  static async getMe() {
    return this.request<User>("/users/me");
  }

  // --- Organizations ---
  static async getOrganizations() {
    return this.request<Organization[]>("/organizations");
  }

  static async getActiveOrg() {
    return this.request<Organization>("/organizations/current");
  }

  static async getOrgMembers() {
    return this.request<Member[]>("/organizations/current/members");
  }

  static async inviteMember(email: string, role: string) {
    return this.request<{ success: boolean; message: string }>("/organizations/current/members", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
  }

  // --- Data Sources ---
  static async getDataSources() {
    return this.request<DataSource[]>("/data-sources");
  }

  static async uploadFile(file: File, name?: string) {
    const formData = new FormData();
    formData.append("file", file);
    if (name) formData.append("name", name);

    return this.request<DataSource>("/data-sources/upload", {
      method: "POST",
      body: formData,
    });
  }

  static async createPostgresSource(data: Record<string, any>) {
    const formData = new FormData();
    Object.entries(data).forEach(([key, val]) => {
      formData.append(key, String(val));
    });

    return this.request<DataSource>("/data-sources/postgres", {
      method: "POST",
      body: formData,
    });
  }

  static async testDataSource(sourceId: string) {
    return this.request<{ success: boolean; message: string }>(`/data-sources/${sourceId}/test`, {
      method: "POST",
    });
  }

  static async deleteDataSource(sourceId: string) {
    return this.request<{ success: boolean }>(`/data-sources/${sourceId}`, {
      method: "DELETE",
    });
  }

  // --- Datasets ---
  static async getDatasets() {
    return this.request<Dataset[]>("/datasets");
  }

  static async getDatasetDetails(datasetId: string) {
    return this.request<DatasetSchema>(`/datasets/${datasetId}`);
  }

  static async getDatasetPreview(datasetId: string) {
    return this.request<{ columns: any[]; sample_data: any[]; row_count: number }>(
      `/datasets/${datasetId}/preview`
    );
  }

  static async deleteDataset(datasetId: string) {
    return this.request<{ success: boolean }>(`/datasets/${datasetId}`, {
      method: "DELETE",
    });
  }

  // --- Conversations & AI Agent ---
  static async getConversations() {
    return this.request<Conversation[]>("/conversations");
  }

  static async getConversation(conversationId: string) {
    return this.request<{ id: string; title: string; messages: Message[] }>(
      `/conversations/${conversationId}`
    );
  }

  static async sendMessage(conversationId: string, content: string) {
    return this.request<{
      conversation_id: string;
      message_id: string;
      answer: string;
      chart?: any;
      queries?: any[];
      sources?: string[];
    }>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  }

  static async askQuestion(question: string, datasetIds?: string[], conversationId?: string) {
    return this.request<{
      conversation_id: string;
      message_id: string;
      answer: string;
      chart?: any;
      queries?: any[];
      sources?: string[];
    }>("/conversations/analyze", {
      method: "POST",
      body: JSON.stringify({ question, dataset_ids: datasetIds, conversation_id: conversationId }),
    });
  }

  // --- Query Executions ---
  static async getQueryExecutions() {
    return this.request<QueryExecution[]>("/queries");
  }

  // --- Reports & Saved Analyses ---
  static async getReports() {
    return this.request<Report[]>("/reports");
  }

  static async createReport(data: { title: string; description?: string; config?: any }) {
    return this.request<Report>("/reports", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  static async getSavedAnalyses() {
    return this.request<any[]>("/reports/analyses");
  }

  static async saveAnalysis(data: {
    title: string;
    description?: string;
    conversation_id?: string;
    chart_config?: any;
  }) {
    return this.request<any>("/reports/analyses", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Anomalies ---
  static async getAnomalies(datasetId?: string) {
    const url = datasetId ? `/anomalies?dataset_id=${datasetId}` : "/anomalies";
    return this.request<Anomaly[]>(url);
  }

  static async triggerAnomalyScan(data: {
    dataset_id: string;
    metric_column: string;
    time_column?: string;
    method?: string;
  }) {
    return this.request<Anomaly[]>("/anomalies/scan", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Scheduled Jobs ---
  static async getScheduledJobs() {
    return this.request<ScheduledJob[]>("/scheduled-jobs");
  }

  static async createScheduledJob(data: {
    name: string;
    job_type: "report" | "anomaly_scan";
    schedule_cron: string;
    timezone?: string;
    config?: any;
  }) {
    return this.request<ScheduledJob>("/scheduled-jobs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Audit Logs ---
  static async getAuditLogs() {
    return this.request<AuditEvent[]>("/audit-logs");
  }
}
