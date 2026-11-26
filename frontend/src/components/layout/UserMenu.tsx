import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { Settings, BookOpen, Info, LogOut, User } from 'lucide-react';
import SettingsDialog from '@/components/settings/SettingsDialog';
import AccountDialog from '@/components/account/AccountDialog';
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
  const [accountOpen, setAccountOpen] = useState(false);
  const settingsOpen = useSettingsDialogStore((s) => s.open);
  const closeSettings = useSettingsDialogStore((s) => s.closeSettings);
  const openSettings = useSettingsDialogStore((s) => s.openSettings);
  const authStatus = useAuthStore((s) => s.status);
  const authUser = useAuthStore((s) => s.user);
  const markRequired = useAuthStore((s) => s.markRequired);
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

  const handleAccount = () => {
    setOpen(false);
    if (isMobile && setMobileOpen) {
      setMobileOpen(false);
    }
    setAccountOpen(true);
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
    markRequired();
  };

  const menuItemClass =
    "flex w-full items-center gap-2.5 3xl:gap-3 rounded-lg px-2.5 3xl:px-3 4xl:px-3.5 py-2 3xl:py-2.5 4xl:py-3 font-inter text-sm 3xl:text-base 4xl:text-lg text-text-primary transition-colors hover:bg-surface-subtle text-left";
  const menuIconClass = "h-4 w-4 3xl:h-4.5 3xl:w-4.5 4xl:h-5 4xl:w-5 shrink-0 text-text-muted";

  const menuItems = (
    <>
      {authStatus === 'authenticated' && (
        <button type="button" onClick={handleAccount} className={menuItemClass}>
          <User className={menuIconClass} strokeWidth={1.75} />
          Account
        </button>
      )}
      <button type="button" onClick={handleSettings} className={menuItemClass}>
        <Settings className={menuIconClass} strokeWidth={1.75} />
        Settings
      </button>
      <button type="button" onClick={handleAbout} className={menuItemClass}>
        <Info className={menuIconClass} strokeWidth={1.75} />
        About
      </button>
      <button type="button" onClick={handleGettingStarted} className={menuItemClass}>
        <BookOpen className={menuIconClass} strokeWidth={1.75} />
        Getting started guide
      </button>
      {authUser && (
        <div className="px-2.5 3xl:px-3 4xl:px-3.5 py-2 3xl:py-2.5 font-inter text-xs 3xl:text-sm 4xl:text-base text-text-muted truncate">
          Signed in as {authUser.username}
        </div>
      )}
      {authStatus === 'authenticated' && (
        <button
          type="button"
          onClick={() => void handleSignOut()}
          className={menuItemClass}
        >
          <LogOut className={menuIconClass} strokeWidth={1.75} />
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
              ? 'justify-center w-10 h-10 3xl:w-11 3xl:h-11 4xl:w-13 4xl:h-13 shrink-0'
              : 'gap-2.5 3xl:gap-3 4xl:gap-3.5 px-3 3xl:px-3.5 4xl:px-4 h-9 3xl:h-11 4xl:h-12 w-full shrink-0'
          }`}
        >
          <span className="flex h-5 w-5 3xl:h-5.5 3xl:w-5.5 4xl:h-6 4xl:w-6 shrink-0 items-center justify-center">
            <Settings
              className={`${isCollapsed ? 'h-5 w-5 3xl:h-5.5 3xl:w-5.5 4xl:h-6 4xl:w-6' : 'h-4.5 w-4.5 3xl:h-5 3xl:w-5 4xl:h-5.5 4xl:w-5.5'} text-text-muted`}
              strokeWidth={1.75}
              aria-hidden={true}
            />
          </span>
          {!isCollapsed && (
            <span className="font-inter text-ui 3xl:text-base 4xl:text-lg font-medium text-text-muted min-w-0 flex-1 truncate text-left">
              About & Settings
            </span>
          )}
        </button>

        {open && !isCollapsed && (
          <div
            role="menu"
            className="absolute z-50 left-0 bottom-full mb-2 w-full rounded-xl border border-border-ui bg-surface-card p-1.5 3xl:p-2 shadow-modal origin-bottom-left animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-1 duration-150 ease-[cubic-bezier(0.16,1,0.3,1)]"
          >
            {menuItems}
          </div>
        )}

        {open && isCollapsed && popupPos && createPortal(
          <div
            ref={popupRef}
            role="menu"
            style={{ position: 'fixed', left: popupPos.left, bottom: popupPos.bottom }}
            className="z-50 w-56 3xl:w-64 4xl:w-72 rounded-xl border border-border-ui bg-surface-card p-1.5 3xl:p-2 shadow-modal max-h-[calc(100dvh-16px)] overflow-y-auto origin-bottom-left animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-1 duration-150 ease-[cubic-bezier(0.16,1,0.3,1)]"
          >
            {menuItems}
          </div>,
          document.body,
        )}
      </div>

      <SettingsDialog open={settingsOpen} onOpenChange={closeSettings} />
      <AccountDialog open={accountOpen} onOpenChange={setAccountOpen} />
    </>
  );
};
