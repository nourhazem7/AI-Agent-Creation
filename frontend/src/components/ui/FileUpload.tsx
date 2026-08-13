import { useRef, useState, type DragEvent } from "react";

interface FileUploadProps {
  accept?: string;
  onFileSelected: (file: File) => void;
  selectedFileName?: string | null;
  hint?: string;
}

export function FileUpload({ accept, onFileSelected, selectedFileName, hint }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onFileSelected(file);
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
      className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2
        border-dashed px-4 py-8 text-center transition-colors
        ${isDragOver ? "border-ink bg-canvas" : "border-border hover:border-ink-muted"}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelected(file);
        }}
      />
      {selectedFileName ? (
        <p className="text-sm font-medium text-ink">{selectedFileName}</p>
      ) : (
        <>
          <p className="text-sm font-medium text-ink">Click to upload or drag and drop</p>
          {hint && <p className="text-xs text-ink-muted">{hint}</p>}
        </>
      )}
    </div>
  );
}
