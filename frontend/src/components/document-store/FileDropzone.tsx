import React, { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';

interface FileDropzoneProps {
  backendReady: boolean;
  allowedExtensions: string[];
  maxMbLabel: string;
  onFilesAdded: (files: File[]) => void;
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({
  backendReady,
  allowedExtensions,
  maxMbLabel,
  onFilesAdded,
}) => {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const accept = allowedExtensions.join(',');

  const handleClick = () => {
    if (backendReady) {
      inputRef.current?.click();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (backendReady && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      inputRef.current?.click();
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (backendReady) {
      setDragging(true);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (backendReady) {
      onFilesAdded(Array.from(e.dataTransfer.files));
    }
  };

  return (
    <div
      role="button"
      tabIndex={backendReady ? 0 : -1}
      aria-label={`Drop files or click to choose documents. Maximum ${maxMbLabel} per file.`}
      className={`rounded-xl 3xl:rounded-2xl border border-dashed p-6 3xl:p-8 4xl:p-10 text-center transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 ${
        !backendReady ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      } ${
        dragging ? 'border-brand-500 bg-brand-50' : 'border-border-ui bg-surface-subtle/40 hover:bg-surface-subtle'
      }`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <UploadCloud className={`mx-auto h-8 w-8 3xl:h-10 3xl:w-10 4xl:h-12 4xl:w-12 ${dragging ? 'text-brand-500' : 'text-brand-700'}`} />
      <p className="mt-2 3xl:mt-3 font-inter text-body-sm 3xl:text-base 4xl:text-lg font-semibold text-text-primary">Drop files or click to choose</p>
      <p className="mt-1 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted">
        {allowedExtensions.map((ext) => ext.replace('.', '').toUpperCase()).join(', ')}
      </p>
      <p className="mt-1 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted">Max {maxMbLabel} per file</p>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        accept={accept}
        onChange={(e) => onFilesAdded(Array.from(e.target.files ?? []))}
      />
    </div>
  );
};
