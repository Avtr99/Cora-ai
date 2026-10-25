import React, { useEffect, useState } from 'react';

import { getAppVersion } from '@/services/coraApi';

/**
 * AppFooter — minimal footer with a single attribution line.
 *
 * Shows the deployed backend's version (from /health, synced to the release
 * tag by release-it) and falls back to the build-time __APP_VERSION__.
 */
export const AppFooter: React.FC = () => {
  const [version, setVersion] = useState(__APP_VERSION__);

  useEffect(() => {
    let cancelled = false;
    getAppVersion().then((v) => {
      if (!cancelled && v) setVersion(v);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <footer className="mt-12 3xl:mt-14 4xl:mt-16 pt-6 3xl:pt-8 pb-6 3xl:pb-8 border-t border-border-ui">
      <p className="font-inter text-xs 3xl:text-[13px] 4xl:text-sm leading-[18px] 3xl:leading-[22px] text-text-muted text-center">
        Research project developed in Germany · v{version}
      </p>
    </footer>
  );
};

export default AppFooter;
