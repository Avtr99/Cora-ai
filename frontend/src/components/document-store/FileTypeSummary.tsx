import React from 'react';

interface FileTypeSummaryProps {
  files: Array<{ file: File }>;
}

// Describes what will happen to a non-PDF file when it's added to the KB.
function fileTypeDescription(filename: string): string {
  const ext = `.${filename.split('.').pop()?.toLowerCase() ?? ''}`;
  switch (ext) {
    case '.md':
      return 'Markdown, added directly';
    case '.txt':
      return 'Plain text, wrapped and added';
    case '.csv':
      return 'CSV, flattened to rows (first 50,000) and added';
    case '.json':
      return 'JSON, pretty-printed and added';
    case '.jsonl':
      return 'JSONL, each record pretty-printed and added';
    default:
      return 'Added directly';
  }
}

export const FileTypeSummary: React.FC<FileTypeSummaryProps> = ({ files }) => {
  if (files.length === 0) return null;

  const counts = files.reduce<Record<string, number>>((acc, s) => {
    const desc = fileTypeDescription(s.file.name);
    acc[desc] = (acc[desc] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mt-2 space-y-0.5">
      {Object.entries(counts).map(([desc, count]) => (
        <p key={desc} className="font-inter text-xs text-text-muted">
          · {count} {count === 1 ? 'file' : 'files'}: {desc}
        </p>
      ))}
    </div>
  );
};
