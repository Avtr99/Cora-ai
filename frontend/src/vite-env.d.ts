/// <reference types="vite/client" />

// SVGR type declarations for importing SVGs as React components
declare module '*.svg?react' {
  import { FC, SVGProps } from 'react';
  const content: FC<SVGProps<SVGSVGElement>>;
  export default content;
}

// Keep standard SVG import for compatibility (if needed)
declare module '*.svg' {
  const content: string;
  export default content;
}
