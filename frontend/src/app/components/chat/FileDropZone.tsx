import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { cn } from "../../lib/utils";

interface FileDropZoneProps {
  onFiles: (files: File[]) => Promise<void> | void;
  disabled?: boolean;
}

export function FileDropZone({ onFiles, disabled }: FileDropZoneProps) {
  const [isOver, setIsOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const processFiles = async (fileList: FileList | null) => {
    if (!fileList || disabled) return;
    await onFiles(Array.from(fileList));
  };

  return (
    <div
      className={cn(
        "rounded-md border border-dashed px-4 py-4 text-center transition-colors",
        isOver ? "border-indigo-500 bg-indigo-50" : "border-slate-300 bg-slate-50",
        disabled && "cursor-not-allowed opacity-60",
      )}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={async (event) => {
        event.preventDefault();
        setIsOver(false);
        await processFiles(event.dataTransfer.files);
      }}
    >
      <div className="flex flex-col items-center gap-2">
        <UploadCloud size={20} className="text-slate-500" />
        <p className="text-xs text-slate-600">Drag and drop files, or click to upload</p>
        <button
          type="button"
          className="text-xs font-medium text-indigo-600 hover:underline"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
        >
          Select files
        </button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple
          onChange={(event) => {
            void processFiles(event.target.files);
            event.currentTarget.value = "";
          }}
        />
      </div>
    </div>
  );
}

