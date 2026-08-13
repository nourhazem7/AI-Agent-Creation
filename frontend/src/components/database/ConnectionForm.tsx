import { useState } from "react";
import { Button, FileUpload, Input, StatusIndicator } from "../ui";
import type { DialectMeta } from "../../lib/dialects";
import { saveConnection, testConnection, uploadSqliteFile, type ConnectionFields } from "../../api/database";
import { apiErrorMessage } from "../../api/client";
import { withMinDuration } from "../../lib/withMinDuration";

interface ConnectionFormProps {
  agentId: string;
  dialect: DialectMeta;
  onBack: () => void;
  onConnected: () => void;
}

type TestState = { status: "idle" | "testing" | "success" | "error"; error?: string };

export function ConnectionForm({ agentId, dialect, onBack, onConnected }: ConnectionFormProps) {
  const [host, setHost] = useState("");
  const [port, setPort] = useState(dialect.defaultPort ? String(dialect.defaultPort) : "");
  const [databaseName, setDatabaseName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [sqliteFilePath, setSqliteFilePath] = useState<string | null>(null);
  const [sqliteFileName, setSqliteFileName] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [testState, setTestState] = useState<TestState>({ status: "idle" });
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isSqlite = dialect.value === "sqlite";

  function buildPayload(): ConnectionFields {
    if (isSqlite) {
      return { dialect: "sqlite", sqlite_file_path: sqliteFilePath ?? undefined };
    }
    return {
      dialect: dialect.value as ConnectionFields["dialect"],
      host,
      port: port ? Number(port) : undefined,
      database_name: databaseName,
      username,
      password,
    };
  }

  async function handleFileSelected(file: File) {
    setIsUploading(true);
    setUploadError(null);
    try {
      const result = await uploadSqliteFile(agentId, file);
      setSqliteFilePath(result.sqlite_file_path);
      setSqliteFileName(result.original_filename);
      setTestState({ status: "idle" });
    } catch (err) {
      setUploadError(apiErrorMessage(err, "Could not upload that file."));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleTest() {
    setTestState({ status: "testing" });
    try {
      // A local SQLite check can resolve in under 100ms — without a minimum duration,
      // the state flips so fast it looks like nothing happened rather than a real check.
      const result = await withMinDuration(testConnection(agentId, buildPayload()));
      setTestState(result.ok ? { status: "success" } : { status: "error", error: result.error ?? undefined });
    } catch (err) {
      setTestState({ status: "error", error: apiErrorMessage(err, "Could not test the connection.") });
    }
  }

  async function handleSave() {
    setIsSaving(true);
    setSaveError(null);
    try {
      await withMinDuration(saveConnection(agentId, buildPayload()));
      onConnected();
    } catch (err) {
      setSaveError(apiErrorMessage(err, "Could not save the connection."));
    } finally {
      setIsSaving(false);
    }
  }

  const canTest = isSqlite ? !!sqliteFilePath : !!host && !!databaseName;
  const canSave = testState.status === "success";

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="text-sm font-medium text-ink-muted hover:text-ink"
      >
        ← Choose a different database
      </button>

      <div className="mt-4 flex items-center gap-3">
        <span
          className={`flex h-9 w-9 items-center justify-center rounded-lg text-sm font-semibold text-white ${dialect.color}`}
          aria-hidden="true"
        >
          {dialect.initial}
        </span>
        <h2 className="text-lg font-semibold text-ink">{dialect.label}</h2>
      </div>

      <div className="mt-6 flex flex-col gap-4">
        {isSqlite ? (
          <>
            <FileUpload
              accept=".db,.sqlite,.sqlite3"
              onFileSelected={handleFileSelected}
              selectedFileName={sqliteFileName}
              hint="Upload a .db or .sqlite file"
            />
            {isUploading && <p className="text-sm text-ink-muted">Uploading…</p>}
            {uploadError && <p className="text-sm text-danger">{uploadError}</p>}
          </>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <Input label="Host" value={host} onChange={(e) => setHost(e.target.value)} placeholder="db.company.com" required />
              </div>
              <Input label="Port" type="number" value={port} onChange={(e) => setPort(e.target.value)} />
            </div>
            <Input
              label="Database name"
              value={databaseName}
              onChange={(e) => setDatabaseName(e.target.value)}
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </>
        )}

        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={handleTest}
            isLoading={testState.status === "testing"}
            disabled={!canTest}
          >
            Test Connection
          </Button>
          {testState.status === "testing" && <StatusIndicator status="pending" label="Testing connection…" />}
          {testState.status === "success" && <StatusIndicator status="success" label="Database connected successfully" />}
          {testState.status === "error" && <StatusIndicator status="error" label="Connection failed" />}
        </div>

        {testState.status === "error" && testState.error && (
          <p className="rounded-md border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger">
            {testState.error}
          </p>
        )}

        {saveError && <p className="text-sm text-danger">{saveError}</p>}

        <Button type="button" onClick={handleSave} isLoading={isSaving} disabled={!canSave} className="mt-2">
          {isSaving ? "Saving connection…" : "Save & Continue"}
        </Button>
      </div>
    </div>
  );
}
