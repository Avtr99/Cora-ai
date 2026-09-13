import React from 'react';

/**
 * AppFooter — minimal footer with a single attribution line.
 */
export const AppFooter: React.FC = () => (
  <footer className="mt-12 3xl:mt-14 4xl:mt-16 pt-6 3xl:pt-8 pb-6 3xl:pb-8 border-t border-border-ui">
    <p className="font-inter text-xs 3xl:text-[13px] 4xl:text-sm leading-[18px] 3xl:leading-[22px] text-text-muted text-center">
      Research project developed in Germany · v{__APP_VERSION__}
    </p>
  </footer>
);

export default AppFooter;
