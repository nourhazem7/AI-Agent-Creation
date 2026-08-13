import type { SupportedDialect } from "../api/database";

export interface DialectMeta {
  value: SupportedDialect | "snowflake" | "oracle" | "bigquery";
  label: string;
  initial: string;
  color: string; // Tailwind bg-* class for the icon chip
  defaultPort?: number;
  enabled: boolean;
}

// Only dialects with a driver actually installed in the backend (see
// backend/requirements.txt) are enabled here — matches SUPPORTED_DIALECTS
// in backend/app/models/database_connection.py. The rest are shown so users
// know they're on the roadmap, but are visibly disabled — never silently
// pretend an unsupported dialect works.
export const DIALECTS: DialectMeta[] = [
  { value: "postgresql", label: "PostgreSQL", initial: "P", color: "bg-blue-600", defaultPort: 5432, enabled: true },
  { value: "mysql", label: "MySQL", initial: "M", color: "bg-orange-500", defaultPort: 3306, enabled: true },
  { value: "mssql", label: "SQL Server", initial: "S", color: "bg-red-600", defaultPort: 1433, enabled: true },
  { value: "sqlite", label: "SQLite", initial: "L", color: "bg-slate-600", enabled: true },
  { value: "snowflake", label: "Snowflake", initial: "F", color: "bg-sky-500", enabled: false },
  { value: "oracle", label: "Oracle", initial: "O", color: "bg-rose-700", enabled: false },
  { value: "bigquery", label: "BigQuery", initial: "B", color: "bg-indigo-600", enabled: false },
];
