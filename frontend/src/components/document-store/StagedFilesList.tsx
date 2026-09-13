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
    <div className="mt-4 3xl:mt-5 4xl:mt-6">
      <div className="flex items-center justify-between mb-2 3xl:mb-3">
        <p className="font-inter text-body-sm 3xl:text-[15px] 4xl:text-base font-medium text-text-primary">
          {files.length} file{files.length === 1 ? '' : 's'} ready
        </p>
        <button
          type="button"
          onClick={onClear}
          disabled={isUploading}
          className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted hover:text-semantic-error-icon disabled:opacity-50"
        >
          Clear
        </button>
      </div>
      <div className="rounded-lg 3xl:rounded-xl border border-border-ui divide-y divide-border-ui bg-surface-card">
        {files.map((staged) => (
          <div key={staged.id} className="flex items-center justify-between gap-3 3xl:gap-4 px-3 3xl:px-4 py-2 3xl:py-3">
            <div className="min-w-0">
              <p className="truncate font-inter text-body-sm 3xl:text-[15px] 4xl:text-base text-text-primary">{staged.file.name}</p>
              <p className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted">{formatBytes(staged.file.size)}</p>
            </div>
            <button
              type="button"
              onClick={() => onRemove(staged.id)}
              disabled={isUploading}
              className="h-7 w-7 3xl:h-9 3xl:w-9 flex items-center justify-center rounded-lg text-text-muted hover:text-semantic-error-icon hover:bg-semantic-error-bg disabled:opacity-50"
              aria-label="Remove"
            >
              <X className="h-4 w-4 3xl:h-5 3xl:w-5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
