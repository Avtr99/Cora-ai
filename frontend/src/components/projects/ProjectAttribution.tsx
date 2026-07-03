import React from 'react';

interface ProjectAttributionProps {
  version: string;
  lastUpdated: string;
}

export const ProjectAttribution: React.FC<ProjectAttributionProps> = ({
  version,
  lastUpdated,
}) => (
  <footer className="mt-10 pt-6 border-t border-border-ui">
    <p className="font-inter text-xs text-text-muted leading-relaxed mb-1.5">
      <span className="font-semibold">Data source:</span>{' '}
      Pamela Quartson, Barbara K Haya, Tyler Bernard, Aline Abayo, Xinyun Rong, Ivy S So, Micah Elias. (2026).{' '}
      <em>Voluntary Registry Offsets Database v2026-04</em>, Berkeley Carbon Trading Project, University of California, Berkeley.
      Retrieved from:{' '}
      <a
        href="https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database"
        target="_blank"
        rel="noopener noreferrer"
        className="text-brand-500 underline hover:text-brand-900"
      >
        gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database
        <span className="sr-only"> (opens in new tab)</span>
      </a>
    </p>
    <p className="font-inter text-xs text-text-muted">
      <span className="font-semibold">Last updated:</span> {lastUpdated} ({version})
    </p>
  </footer>
);
