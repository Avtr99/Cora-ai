import React from 'react';
import { X } from 'lucide-react';
import { formatBytes } from '@/services/documentStoreApi';

interface StagedFile {
  id: string;
  file: File;
}

interface StagedFilesListProps {
  files: StagedFile[];
  isUploading: boolean;
  onRemove: (id: string) => void;
  onClear: () => void;
}

export const StagedFilesList: React.FC<StagedFilesListProps> = ({
  files,
  isUploading,
  onRemove,
  onClear,
}) => {
  if (files.length === 0) return null;

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <p className="font-poppins text-sm font-medium text-text-primary">
          {files.length} file{files.length === 1 ? '' : 's'} ready
        </p>
        <button
          type="button"
          onClick={onClear}
          disabled={isUploading}
          className="font-inter text-xs text-text-muted hover:text-semantic-error-icon disabled:opacity-50"
        >
          Clear
        </button>
      </div>
      <div className="rounded-lg border border-border-ui divide-y divide-border-ui bg-surface-card">
        {files.map((staged) => (
          <div key={staged.id} className="flex items-center justify-between gap-3 px-3 py-2">
            <div className="min-w-0">
              <p className="truncate font-inter text-sm text-text-primary">{staged.file.name}</p>
              <p className="font-inter text-xs text-text-muted">{formatBytes(staged.file.size)}</p>
            </div>
            <button
              type="button"
              onClick={() => onRemove(staged.id)}
              disabled={isUploading}
              className="h-7 w-7 flex items-center justify-center rounded-lg text-text-muted hover:text-semantic-error-icon hover:bg-semantic-error-bg disabled:opacity-50"
              aria-label="Remove"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
