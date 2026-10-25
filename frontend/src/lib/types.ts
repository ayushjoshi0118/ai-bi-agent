/**
 * Type-safe interfaces matching the backend Pydantic schemas.
 */

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  member_count?: number;
}

export type OrgRole = "owner" | "admin" | "analyst" | "viewer";

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: OrgRole;
  joined_at: string;
}

export type DataSourceType = "csv" | "xlsx" | "postgresql";
export type DataSourceStatus = "pending" | "connected" | "error" | "disconnected";

export interface DataSource {
  id: string;
  org_id: string;
  name: string;
  source_type: DataSourceType;
  connection_config?: Record<string, any>;
  status: DataSourceStatus;
  last_synced_at?: string;
  created_at: string;
  updated_at: string;
  dataset_count?: number;
}

export interface ColumnInfo {
  name: string;
  data_type: string;
  nullable: boolean;
  is_primary_key?: boolean;
  sample_values?: any[];
}

export interface Dataset {
  id: string;
  org_id: string;
  data_source_id: string;
  name: string;
  description?: string;
  table_name: string;
  row_count?: number;
  column_count?: number;
  status: "pending" | "profiling" | "ready" | "error";
  profiled_at?: string;
  created_at: string;
  updated_at?: string;
}

export interface DatasetSchema {
  id: string;
  name: string;
  table_name: string;
  row_count?: number;
  columns: ColumnInfo[];
  sample_data?: Record<string, any>[];
  profiled_at?: string;
}

export interface QueryExecution {
  id: string;
  sql_query: string;
  validation_status: "pending" | "valid" | "rejected";
  execution_status: "pending" | "running" | "completed" | "failed" | "cancelled" | "timeout";
  result_summary?: {
    columns: string[];
    row_count: number;
    truncated?: boolean;
  };
  row_count?: number;
  execution_time_ms?: number;
  executed_at: string;
}

export type ChartType = "line" | "bar" | "stacked_bar" | "scatter" | "table" | "kpi_card";

export interface AxisConfig {
  field: string;
  label?: string;
  format?: string;
  sort?: "asc" | "desc";
}

export interface SeriesConfig {
  field: string;
  label?: string;
  color?: string;
  aggregate?: string;
}

export interface ChartSpec {
  chart_type: ChartType;
  title: string;
  subtitle?: string;
  x_axis?: AxisConfig;
  y_axis?: AxisConfig;
  series?: SeriesConfig[];
  data: Record<string, any>[];
  kpi_value?: string;
  kpi_change?: string;
  kpi_change_direction?: "up" | "down" | "neutral";
  insights?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: {
    queries?: {
      id: string;
      sql: string;
      row_count: number;
      duration_ms: number;
    }[];
    chart?: ChartSpec;
    sources?: string[];
  };
  created_at: string;
}

export interface Conversation {
  id: string;
  org_id: string;
  user_id: string;
  title: string;
  message_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Anomaly {
  id: string;
  org_id: string;
  dataset_id: string;
  metric_name: string;
  metric_value?: number;
  expected_value?: number;
  deviation_score?: number;
  severity: "low" | "medium" | "high" | "critical";
  status: "detected" | "acknowledged" | "resolved" | "dismissed";
  detection_method: string;
  explanation?: string;
  supporting_data?: Record<string, any>;
  detected_at: string;
  created_at: string;
}

export interface Report {
  id: string;
  org_id: string;
  title: string;
  description?: string;
  status: "draft" | "published" | "archived";
  config?: Record<string, any>;
  created_at: string;
  updated_at: string;
  latest_version?: {
    id: string;
    version_number: number;
    content?: Record<string, any>;
    generated_at: string;
  };
}

export interface ScheduledJob {
  id: string;
  org_id: string;
  name: string;
  job_type: "report" | "anomaly_scan";
  config?: Record<string, any>;
  schedule_cron: string;
  timezone: string;
  is_active: boolean;
  last_run_at?: string;
  created_at: string;
  latest_run?: {
    id: string;
    status: "pending" | "running" | "completed" | "failed";
    duration_seconds?: number;
    started_at: string;
  };
}

export interface AuditEvent {
  id: string;
  org_id: string;
  user_id?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  details?: Record<string, any>;
  ip_address?: string;
  created_at: string;
}
