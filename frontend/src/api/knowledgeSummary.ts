import { apiClient } from "./client";

export interface ColumnFact {
  name: string;
  type: string;
  nullable: boolean;
  is_primary_key: boolean;
}

export interface ForeignKeyFact {
  columns: string[];
  referred_table: string;
  referred_columns: string[];
}

export interface TableFact {
  name: string;
  columns: ColumnFact[];
  primary_keys: string[];
  foreign_keys: ForeignKeyFact[];
}

export interface DatabaseFacts {
  connected: boolean;
  dialect: string | null;
  table_count: number;
  tables: TableFact[];
  relationship_count: number;
  source: "live" | "stored_schema_asset" | "none";
  schema_asset_matches_live: boolean | null;
}

export interface DocumentationSummary {
  configured: boolean;
  status: string;
  source: string | null;
  verified: boolean;
  content: string | null;
  word_count: number;
}

export interface ValidationCoverage {
  configured: boolean;
  status: string;
  source: string | null;
  total_tests: number;
  sql_verified_count: number;
}

export interface KnowledgeReadiness {
  ready_count: number;
  total_count: number;
  all_ready: boolean;
}

export interface KnowledgeSummary {
  agent_id: string;
  agent_name: string;
  database: DatabaseFacts;
  documentation: DocumentationSummary;
  validation: ValidationCoverage;
  readiness: KnowledgeReadiness;
}

export async function getKnowledgeSummary(agentId: string): Promise<KnowledgeSummary> {
  const { data } = await apiClient.get<KnowledgeSummary>(`/agents/${agentId}/knowledge-summary`);
  return data;
}
