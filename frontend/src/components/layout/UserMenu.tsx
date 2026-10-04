import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Settings, BookOpen, Info, LogOut } from 'lucide-react';
import SettingsDialog from '@/components/settings/SettingsDialog';
import { useSettingsDialogStore } from '@/store/settingsDialogStore';
import { useAuthStore } from '@/store/authStore';
import { logout } from '@/services/authApi';

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
  const authStatus = useAuthStore((s) => s.status);
  const setAuthStatus = useAuthStore((s) => s.setStatus);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  // Fixed position of the portaled popup (collapsed rail only). The sidebar
  // aside is overflow-hidden, so anything rendered inside it gets clipped
  // once it extends past the 60px rail — the popup must live on body.
  const [popupPos, setPopupPos] = useState<{ left: number; bottom: number } | null>(null);

  const updatePopupPos = useCallback(() => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    setPopupPos({
      left: rect.right + 8,
      bottom: Math.max(8, window.innerHeight - rect.bottom),
    });
  }, []);

  // Dismiss on outside pointerdown (trigger + popup both count as inside)
  // or Escape. Replaces the old useClickAway, which only knew the trigger
  // and would have closed the portaled popup before item clicks could fire.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (popupRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open ]);

  // Keep the portaled popup anchored to the trigger across resizes/scrolls.
  useEffect(() => {
    if (!open || !isCollapsed) return;
    updatePopupPos();
    window.addEventListener('resize', updatePopupPos);
    window.addEventListener('scroll', updatePopupPos, true);
    return () => {
      window.removeEventListener('resize', updatePopupPos);
      window.removeEventListener('scroll', updatePopupPos, true);
    };
  }, [open, isCollapsed, updatePopupPos]);

  const handleToggle = () => {
    if (!open && isCollapsed) updatePopupPos();
    setOpen((v) => !v);
  };

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

  const handleSignOut = async () => {
    setOpen(false);
    if (isMobile && setMobileOpen) {
      setMobileOpen(false);
    }
    try {
      await logout();
    } catch (err) {
      console.error('Sign-out failed:', err);
    }
    setAuthStatus('required');
  };

  const menuItemClass =
    "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 font-inter text-sm text-text-primary transition-colors hover:bg-surface-subtle text-left";

  const menuItems = (
    <>
      <button type="button" onClick={handleSettings} className={menuItemClass}>
        <Settings className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
        Settings
      </button>
      <button type="button" onClick={handleAbout} className={menuItemClass}>
        <Info className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
        About
      </button>
      <button type="button" onClick={handleGettingStarted} className={menuItemClass}>
        <BookOpen className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
        Getting started guide
      </button>
      {authStatus === 'authenticated' && (
        <button
          type="button"
          onClick={() => void handleSignOut()}
          className={menuItemClass}
        >
          <LogOut className="h-4 w-4 text-text-muted" strokeWidth={1.75} />
          Sign out
        </button>
      )}
    </>
  );

  return (
    <>
      <div ref={menuRef} className="relative w-full flex justify-center">
        <button
          ref={buttonRef}
          type="button"
          onClick={handleToggle}
          aria-label="About and settings"
          aria-expanded={open}
          aria-haspopup="menu"
          className={`flex items-center rounded-lg transition-colors ${
            open ? 'bg-muted/80' : 'hover:bg-muted'
          } ${
            isCollapsed
              ? 'justify-center w-10 h-10 shrink-0'
              : 'gap-2.5 px-3 h-9 w-full shrink-0'
          }`}
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center">
            <Settings
              className="h-5 w-5 text-text-muted"
              strokeWidth={1.75}
              aria-hidden={true}
            />
          </span>
          {!isCollapsed && (
            <span className="font-inter text-ui font-medium text-text-muted">
              About & Settings
            </span>
          )}
        </button>

        {open && !isCollapsed && (
          <div
            role="menu"
            className="absolute z-50 left-0 bottom-full mb-2 w-full rounded-xl border border-border-ui bg-surface-card p-1.5 shadow-modal"
          >
            {menuItems}
          </div>
        )}

        {open && isCollapsed && popupPos && createPortal(
          <div
            ref={popupRef}
            role="menu"
            style={{ position: 'fixed', left: popupPos.left, bottom: popupPos.bottom }}
            className="z-50 w-56 rounded-xl border border-border-ui bg-surface-card p-1.5 shadow-modal max-h-[calc(100dvh-16px)] overflow-y-auto"
          >
            {menuItems}
          </div>,
          document.body,
        )}
      </div>

      <SettingsDialog open={settingsOpen} onOpenChange={closeSettings} />
    </>
  );
};
