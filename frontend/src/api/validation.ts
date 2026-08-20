import { apiClient } from "./client";

export type RunStatus = "not_run" | "passed" | "partial" | "failed" | "error" | "inconclusive";
export type TestOrigin = "ai_generated" | "uploaded" | "manual";

export interface ValidationRun {
  id: string;
  status: RunStatus;
  generated_sql: string | null;
  result_data: string | null;
  agent_answer: string | null;
  reference_result: string | null;
  error_message: string | null;
  comparison_note: string | null;
  violated_requirement: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  iterations: number | null;
  created_at: string;
}

export interface ValidationTest {
  id: string;
  agent_id: string;
  question: string;
  expected_sql: string | null;
  expected_answer: string | null;
  criteria: string | null;
  notes: string | null;
  origin: TestOrigin;
  expected_sql_verified: boolean;
  last_status: RunStatus;
  created_at: string;
  updated_at: string;
  latest_run: ValidationRun | null;
}

export interface ValidationSummary {
  total: number;
  passed: number;
  partial: number;
  failed: number;
  error: number;
  inconclusive: number;
  not_run: number;
}

export interface CreateTestPayload {
  question: string;
  expected_sql?: string;
  expected_answer?: string;
  criteria?: string;
  notes?: string;
}

export async function listValidationTests(agentId: string): Promise<ValidationTest[]> {
  const { data } = await apiClient.get<ValidationTest[]>(`/agents/${agentId}/validation-tests`);
  return data;
}

export async function getValidationSummary(agentId: string): Promise<ValidationSummary> {
  const { data } = await apiClient.get<ValidationSummary>(`/agents/${agentId}/validation-summary`);
  return data;
}

export async function createValidationTest(
  agentId: string,
  payload: CreateTestPayload,
): Promise<ValidationTest> {
  const { data } = await apiClient.post<ValidationTest>(`/agents/${agentId}/validation-tests`, payload);
  return data;
}

export async function deleteValidationTest(agentId: string, testId: string): Promise<void> {
  await apiClient.delete(`/agents/${agentId}/validation-tests/${testId}`);
}

export async function runValidationTest(agentId: string, testId: string): Promise<ValidationTest> {
  const { data } = await apiClient.post<ValidationTest>(`/agents/${agentId}/validation-tests/${testId}/run`);
  return data;
}

export async function runAllValidationTests(agentId: string): Promise<ValidationTest[]> {
  const { data } = await apiClient.post<ValidationTest[]>(`/agents/${agentId}/validation-tests/run-all`);
  return data;
}

export async function runFailedValidationTests(agentId: string): Promise<ValidationTest[]> {
  const { data } = await apiClient.post<ValidationTest[]>(`/agents/${agentId}/validation-tests/run-failed`);
  return data;
}
