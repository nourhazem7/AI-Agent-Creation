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

export type AgentAccessRole = "owner" | "admin" | "viewer";
// "viewer" is the only share role — a shared user can use/chat with an Agent but never
// modify it. There is no editor/collaborate concept.
export type ShareRole = "viewer";

export interface UserSummary {
  id: string;
  email: string;
  full_name: string | null;
}

export interface Agent {
  id: string;
  company_id: string;
  owner_id: string;
  owner: UserSummary;
  name: string;
  description: string | null;
  status: AgentStatus;
  llm_model: string;
  custom_instructions: string | null;
  knowledge_version: number;
  created_at: string;
  updated_at: string;
  // Access metadata — my_role is always set; shared_by/shared_at are only set when access
  // comes from an explicit share (my_role is "viewer"), never for owner/admin.
  my_role: AgentAccessRole;
  shared_by: UserSummary | null;
  shared_at: string | null;
  database_connected: boolean;
  knowledge_ready_count: number;
  knowledge_total_count: number;
}

export interface AgentShare {
  id: string;
  agent_id: string;
  role: ShareRole;
  user: UserSummary;
  shared_by: UserSummary;
  created_at: string;
  updated_at: string;
}

export interface CompanyMember {
  id: string;
  email: string;
  full_name: string | null;
}
