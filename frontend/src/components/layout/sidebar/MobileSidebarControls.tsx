import React from 'react';
import { motion } from 'framer-motion';
import { Menu } from 'lucide-react';

interface MobileSidebarControlsProps {
  isMobile: boolean;
  mobileOpen: boolean;
  isHamburgerVisible: boolean;
  setMobileOpen: (open: boolean) => void;
}

export const MobileSidebarControls: React.FC<MobileSidebarControlsProps> = ({
  isMobile,
  mobileOpen,
  isHamburgerVisible,
  setMobileOpen,
}) => {
  React.useEffect(() => {
    if (!isMobile || !mobileOpen) {
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMobile, mobileOpen, setMobileOpen]);

  return (
    <>
      {isMobile && !mobileOpen && (
        <motion.button
          aria-label="Open sidebar"
          aria-expanded={false}
          aria-controls="mobile-sidebar"
          className="fixed top-3 left-3 z-40 w-9 h-9 rounded-lg flex items-center justify-center bg-surface-card/90 backdrop-blur-sm border border-border-ui/60 shadow-sm hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 active:scale-[0.97]"
          onClick={() => setMobileOpen(true)}
          title="Open menu"
          initial={false}
          animate={{
            opacity: isHamburgerVisible ? 1 : 0.25,
            scale: isHamburgerVisible ? 1 : 0.95,
          }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          whileTap={{ scale: 0.95 }}
        >
          <Menu size={16} className="text-brand-500" strokeWidth={2} aria-hidden="true" />
        </motion.button>
      )}

      {isMobile && mobileOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-[1px] z-40"
          aria-hidden="true"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
};
