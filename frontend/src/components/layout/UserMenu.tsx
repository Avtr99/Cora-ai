import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Settings, BookOpen, Info } from 'lucide-react';
import { useClickAway } from '@/hooks/useClickAway';
import SettingsDialog from '@/components/settings/SettingsDialog';
import { useSettingsDialogStore } from '@/store/settingsDialogStore';

interface UserMenuProps {
  isCollapsed: boolean;
  isMobile?: boolean;
  setMobileOpen?: (open: boolean) => void;
}

export const UserMenu: React.FC<UserMenuProps> = ({ isCollapsed, isMobile, setMobileOpen }) => {
  const [open, setOpen] = useState(false);
  const settingsOpen = useSettingsDialogStore((s) => s.open);
  const closeSettings = useSettingsDialogStore((s) => s.closeSettings);
  const openSettings = useSettingsDialogStore((s) => s.openSettings);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useClickAway(menuRef, () => setOpen(false));

  React.useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  const handleSettings = () => {
    setOpen(false);
    if (isMobile && setMobileOpen) {
      setMobileOpen(false);
    }
    openSettings('llm');
  };

  const handleAbout = () => {
    setOpen(false);
    if (isMobile && setMobileOpen) {
      setMobileOpen(false);
    }
    navigate('/about/');
  };

  const handleGettingStarted = () => {
    setOpen(false);
    if (isMobile && setMobileOpen) {
      setMobileOpen(false);
    }
    navigate('/onboarding');
  };

  return (
    <>
      <div ref={menuRef} className="relative w-full flex justify-center">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label="About and settings"
          aria-expanded={open}
          className={`flex items-center rounded-lg transition-colors ${
            open ? 'bg-muted/80' : 'hover:bg-muted'
          } ${
            isCollapsed
              ? 'justify-center w-10 h-10 p-1'
              : 'gap-2 px-3 py-2 w-full'
          }`}
        >
          <Settings
            className={`${isCollapsed ? 'h-6 w-6' : 'h-4.5 w-4.5'} text-text-muted`}
            strokeWidth={1.75}
            aria-hidden={true}
          />
          {!isCollapsed && (
            <span className="font-inter text-sm font-medium text-text-muted">
              About & Settings
            </span>
          )}
        </button>

        {open && (
          <div
            className={`absolute z-50 rounded-xl border border-border-ui bg-surface-card p-1.5 shadow-modal ${
              isCollapsed
                ? 'left-full bottom-0 ml-2 w-56'
                : 'left-0 bottom-full mb-2 w-full'
            }`}
          >
            <button
              type="button"
              onClick={handleSettings}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 font-inter text-sm text-text-primary transition-colors hover:bg-surface-subtle text-left"
            >
              <Settings className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
              Settings
            </button>
            <button
              type="button"
              onClick={handleAbout}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 font-inter text-sm text-text-primary transition-colors hover:bg-surface-subtle text-left"
            >
              <Info className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
              About
            </button>
            <button
              type="button"
              onClick={handleGettingStarted}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 font-inter text-sm text-text-primary transition-colors hover:bg-surface-subtle text-left"
            >
              <BookOpen className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
              Getting started guide
            </button>
          </div>
        )}
      </div>

      <SettingsDialog open={settingsOpen} onOpenChange={closeSettings} />
    </>
  );
};
