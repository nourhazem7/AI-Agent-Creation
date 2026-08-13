import { apiClient } from "./client";

export type SupportedDialect = "postgresql" | "mysql" | "sqlite" | "mssql";

export interface ConnectionFields {
  dialect: SupportedDialect;
  host?: string;
  port?: number;
  database_name?: string;
  username?: string;
  password?: string;
  sqlite_file_path?: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  error: string | null;
}

export interface ConnectionSummary {
  id: string;
  dialect: string;
  host: string | null;
  port: number | null;
  database_name: string | null;
  username: string | null;
  sqlite_file_path: string | null;
  is_connected: boolean;
  last_tested_at: string | null;
}

export async function testConnection(agentId: string, payload: ConnectionFields): Promise<ConnectionTestResult> {
  const { data } = await apiClient.post<ConnectionTestResult>(`/agents/${agentId}/database/test`, payload);
  return data;
}

export async function saveConnection(agentId: string, payload: ConnectionFields): Promise<ConnectionSummary> {
  const { data } = await apiClient.post<ConnectionSummary>(`/agents/${agentId}/database`, payload);
  return data;
}

export async function getConnection(agentId: string): Promise<ConnectionSummary | null> {
  try {
    const { data } = await apiClient.get<ConnectionSummary>(`/agents/${agentId}/database`);
    return data;
  } catch {
    return null;
  }
}

export async function uploadSqliteFile(
  agentId: string,
  file: File,
): Promise<{ sqlite_file_path: string; original_filename: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post(`/agents/${agentId}/database/upload-sqlite`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
