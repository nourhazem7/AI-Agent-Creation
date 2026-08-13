import type { AssetType } from "../api/knowledgeAssets";

export interface SchemaPreview {
  tableCount: number;
  tableNames: string[];
}

export interface ValidationSuitePreview {
  questionCount: number;
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
    const parsed = JSON.parse(content) as Array<{ question?: string }>;
    if (!Array.isArray(parsed)) return null;
    return {
      questionCount: parsed.length,
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
