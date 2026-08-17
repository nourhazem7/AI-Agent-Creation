import type { AssetType } from "../api/knowledgeAssets";

export interface SchemaPreview {
  tableCount: number;
  tableNames: string[];
}

export interface ValidationSuitePreview {
  questionCount: number;
  verifiedCount: number;
  questions: string[];
}

export function previewSchema(content: string): SchemaPreview | null {
  try {
    const parsed = JSON.parse(content) as Record<string, unknown>;
    const tableNames = Object.keys(parsed);
    return { tableCount: tableNames.length, tableNames: tableNames.slice(0, 8) };
  } catch {
    return null;
  }
}

export function previewValidationSuite(content: string): ValidationSuitePreview | null {
  try {
    const parsed = JSON.parse(content) as Array<{ question?: string; sql_verified?: boolean }>;
    if (!Array.isArray(parsed)) return null;
    return {
      questionCount: parsed.length,
      verifiedCount: parsed.filter((q) => q.sql_verified === true).length,
      questions: parsed.slice(0, 5).map((q) => q.question ?? "").filter(Boolean),
    };
  } catch {
    return null;
  }
}

/** One-line status summary shown on the collapsed card, computed from real content only. */
export function assetSummaryLine(assetType: AssetType, content: string | null | undefined): string | null {
  if (!content) return null;
  if (assetType === "schema") {
    const preview = previewSchema(content);
    return preview ? `${preview.tableCount} table${preview.tableCount === 1 ? "" : "s"} detected` : null;
  }
  if (assetType === "validation_suite") {
    const preview = previewValidationSuite(content);
    return preview ? `${preview.questionCount} test${preview.questionCount === 1 ? "" : "s"}` : null;
  }
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  return `${words} word${words === 1 ? "" : "s"}`;
}

/**
 * Verification badge text — only shown for automatically generated assets. Uploaded assets
 * never get this label, since we don't claim the same guarantee for user-supplied content.
 * "ready" on a generated asset already implies verification passed (the backend never sets
 * ready otherwise), so this is safe to compute purely from source+status+content.
 */
export function assetVerificationLabel(
  assetType: AssetType,
  source: string | null | undefined,
  status: string,
  content: string | null | undefined,
): string | null {
  if (source !== "generated" || status !== "ready") return null;

  if (assetType === "schema") return "Verified against database";
  if (assetType === "documentation") return "Verified against database";
  if (assetType === "validation_suite") {
    const preview = content ? previewValidationSuite(content) : null;
    if (!preview) return null;
    return `${preview.verifiedCount}/${preview.questionCount} SQL tests verified`;
  }
  return null;
}
