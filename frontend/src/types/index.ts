export interface Company {
  id: string;
  name: string;
}

export interface User {
  id: string;
  company_id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string;
}

export interface MeResponse {
  user: User;
  company: Company;
}

export type AgentStatus =
  | "draft"
  | "connecting"
  | "configuring_knowledge"
  | "preparing"
  | "ready_for_validation"
  | "validated"
  | "active"
  | "error";

export interface Agent {
  id: string;
  company_id: string;
  owner_id: string;
  name: string;
  description: string | null;
  status: AgentStatus;
  llm_model: string;
  custom_instructions: string | null;
  knowledge_version: number;
  created_at: string;
  updated_at: string;
}
