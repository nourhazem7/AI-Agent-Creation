import type { AssetType } from "../api/knowledgeAssets";

export interface AssetMeta {
  type: AssetType;
  title: string;
  description: string;
  accept: string;
  uploadHint: string;
}

export const KNOWLEDGE_ASSET_META: Record<AssetType, AssetMeta> = {
  schema: {
    type: "schema",
    title: "Database Schema",
    description: "The structural blueprint of your database.",
    accept: ".json,.sql",
    uploadHint: "Upload a schema export (.json or .sql)",
  },
  documentation: {
    type: "documentation",
    title: "Documentation",
    description: "Business context, terminology, and explanations that help the agent understand your data.",
    accept: ".md,.txt",
    uploadHint: "Upload a Markdown or text file",
  },
  validation_suite: {
    type: "validation_suite",
    title: "Validation Suite",
    description: "Questions used to verify that the agent understands your database correctly.",
    accept: ".csv,.json",
    uploadHint: "Upload test cases (.csv or .json)",
  },
};

export const KNOWLEDGE_ASSET_ORDER: AssetType[] = ["schema", "documentation", "validation_suite"];
