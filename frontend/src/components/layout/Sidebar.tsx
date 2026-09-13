import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useSidebar } from "@/contexts/useSidebar";
import { useChatContext } from "@/contexts/useChatContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { useWideBreakpoint } from "@/hooks/use-wide-breakpoint";

import { IconWrapper } from "@/components/icons/IconWrapper";
import SidebarCloseIcon from "@/assets/icons/sidebar-close.svg?react";
import PlusCircleIcon from "@/assets/icons/plus-circle.svg?react";
import BookIcon from "@/assets/icons/book.svg?react";
import FileIcon from "@/assets/icons/file.svg?react";
import PricingIcon from "@/assets/icons/pricing.svg?react";
import ChatIcon from "@/assets/icons/chat.svg?react";
import ExploreIcon from "@/assets/icons/explore.svg?react";
import { ChatListSection } from "./sidebar/ChatListSection";
import { MobileSidebarControls } from "./sidebar/MobileSidebarControls";
import { UserMenu } from "./UserMenu";

interface NavItemProps {
  to: string;
  label: string;
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  isActive: boolean;
  isCollapsed: boolean;
  onClick?: () => void;
}

const NavItem: React.FC<NavItemProps> = ({ to, label, Icon, isActive, isCollapsed, onClick }) => (
  <Link
    to={to}
    className={`flex items-center rounded-lg transition-colors ${isActive ? 'bg-brand-100 hover:bg-brand-100/80' : 'hover:bg-muted'
      } ${isCollapsed ? 'justify-center w-10 h-10 3xl:w-12 3xl:h-12 4xl:w-16 4xl:h-16 p-1' : 'gap-2 3xl:gap-2.5 4xl:gap-3 px-3 py-2 3xl:px-4 3xl:py-2.5 4xl:px-5 4xl:py-3.5 w-full'}`}
    aria-label={label}
    onClick={onClick}
  >
    <IconWrapper
      Icon={Icon}
      size={isCollapsed ? 24 : 18}
      state={isActive ? 'active' : 'default'}
      aria-hidden={true}
      className="3xl:scale-125 4xl:scale-150"
    />
    {!isCollapsed && (
      <span className={`font-inter text-ui 3xl:text-base 4xl:text-[19px] ${isActive ? 'text-brand-secondary font-semibold' : 'text-text-muted font-medium'}`}>
        {label}
      </span>
    )}
  </Link>
);

export const Sidebar: React.FC = () => {
  const { isCollapsed, toggleSidebar } = useSidebar();
  const { chats, activeChat, prepareNewChat, setActiveChat, deleteChat, clearActiveChat } = useChatContext();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const isMobile = useIsMobile();
  const wideBreakpoint = useWideBreakpoint();
  // Sidebar widths match the --sidebar-width / --sidebar-collapsed-width CSS
  // vars declared in Index.tsx so the composer stays aligned at every tier.
  const expandedWidth = wideBreakpoint === '4xl' ? 400 : wideBreakpoint === '3xl' ? 300 : 240;
  const collapsedWidth = wideBreakpoint === '4xl' ? 96 : wideBreakpoint === '3xl' ? 80 : 68;
  const [focusedChatIndex, setFocusedChatIndex] = React.useState<number>(-1);
  const [isHamburgerVisible, setIsHamburgerVisible] = React.useState(true);
  const lastScrollY = React.useRef(0);
  const scrollTimeout = React.useRef<NodeJS.Timeout | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const chatListRef = React.useRef<HTMLDivElement>(null);
  const shouldReduceMotion = useReducedMotion();

  // TanStack Virtual for chat list
  const chatVirtualizer = useVirtualizer({
    count: chats.length,
    getScrollElement: () => chatListRef.current,
    estimateSize: () => 36, // Increased to 36px for proper, even breathing room
    overscan: 5,
  });

  const virtualItems = chatVirtualizer.getVirtualItems();
  const firstVisibleIndex = virtualItems.length > 0 ? virtualItems[0].index : 0;
  const lastVisibleIndex = virtualItems.length > 0 ? virtualItems[virtualItems.length - 1].index : 0;
  const focusableIndex =
    focusedChatIndex !== -1
      ? focusedChatIndex
      : (() => {
        if (activeChat) {
          const idx = chats.findIndex(chat => chat.id === activeChat.id);
          if (idx !== -1) {
            if (virtualItems.length > 0) {
              return Math.min(Math.max(idx, firstVisibleIndex), lastVisibleIndex);
            }
            return idx;
          }
        }
        if (virtualItems.length > 0) {
          return firstVisibleIndex;
        }
        return chats.length > 0 ? 0 : -1;
      })();

  // Hamburger button fade on scroll
  React.useEffect(() => {
    if (!isMobile) return;

    const scrollContainer = document.querySelector('[data-chat-scroll-container]');
    if (!scrollContainer) return;

    const handleScroll = () => {
      const currentScrollY = scrollContainer.scrollTop;
      const isScrollingDown = currentScrollY > lastScrollY.current && currentScrollY > 50;

      if (isScrollingDown) {
        setIsHamburgerVisible(false);
      } else {
        setIsHamburgerVisible(true);
      }

      lastScrollY.current = currentScrollY;

      // Show button after scroll stops
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
      scrollTimeout.current = setTimeout(() => {
        setIsHamburgerVisible(true);
      }, 1500);
    };

    scrollContainer.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      scrollContainer.removeEventListener('scroll', handleScroll);
      if (scrollTimeout.current) clearTimeout(scrollTimeout.current);
    };
  }, [isMobile]);

  const handleNewChat = () => {
    // Clear active chat to ensure clean slate
    clearActiveChat();
    // Navigate to homepage - will show empty state with starter prompts
    navigate('/');
    // Close sidebar on mobile
    if (isMobile) setMobileOpen(false);
  };

  const handleChatKeyDown = (e: React.KeyboardEvent, index: number) => {
    // Don't handle keyboard navigation if focus is on the delete button
    if (e.target instanceof HTMLElement) {
      const isDeleteButton = e.target.closest('[data-action="delete-chat"]') !== null;
      if (isDeleteButton) {
        return; // Let the delete button handle its own keyboard events
      }
    }

    // Virtualization-aware keyboard navigation
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const nextIndex = Math.min(index + 1, chats.length - 1);
      setFocusedChatIndex(nextIndex);
      chatVirtualizer.scrollToIndex(nextIndex, { align: 'auto' });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prevIndex = Math.max(index - 1, 0);
      setFocusedChatIndex(prevIndex);
      chatVirtualizer.scrollToIndex(prevIndex, { align: 'auto' });
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setActiveChat(chats[index].id);
    }
  };

  const handleDeleteChat = (e: React.SyntheticEvent, chatId: string) => {
    e.stopPropagation();
    deleteChat(chatId);
  };

  return (
    <>
      <MobileSidebarControls
        isMobile={isMobile}
        mobileOpen={mobileOpen}
        isHamburgerVisible={isHamburgerVisible}
        setMobileOpen={setMobileOpen}
      />

      <motion.aside
        id="mobile-sidebar"
        className={`bg-surface-base flex flex-col overflow-hidden border-r border-border-ui ${isMobile ? 'fixed top-0 left-0 h-[100dvh] max-h-[100dvh] z-50' : 'h-full'}`}
        initial={false}
        animate={isMobile ? { x: mobileOpen ? 0 : -256 } : { width: isCollapsed ? collapsedWidth : expandedWidth }}
        transition={shouldReduceMotion ? { duration: 0 } : (isMobile ? { duration: 0.18, ease: 'easeOut' } : { duration: 0.16, ease: 'easeOut' })}
        style={isMobile ? { width: 250 } : undefined}
        onWheel={(e) => {
          // Prevent sidebar wheel events from bubbling to the chat scroll container
          e.stopPropagation();
        }}
      >
        {/* Header: Cora Logo + Toggle Button */}
        <div className={`flex items-center flex-shrink-0 ${isCollapsed ? 'justify-center pt-3.5 3xl:pt-4 4xl:pt-6 px-3.5' : 'justify-between px-4 3xl:px-5 pt-4 md:pt-5 3xl:pt-6'} pb-2 3xl:pb-3 4xl:pb-4`}>
          <button
            onClick={() => {
              if (isMobile) return setMobileOpen(false);
              if (isCollapsed) toggleSidebar();
            }}
            className="flex items-center justify-center cursor-pointer bg-surface-card rounded-xl w-10 h-10 3xl:w-12 3xl:h-12 4xl:w-16 4xl:h-16 overflow-hidden flex-shrink-0"
            aria-label="Cora Logo"
          >
            <img
              src="/cora.svg"
              alt="Cora Logo"
              className="w-full h-full object-cover"
            />
          </button>
          {!isCollapsed && (
            <button
              aria-label="Toggle Sidebar"
              className="hover:bg-muted transition-all duration-200 flex items-center justify-center w-11 h-11 3xl:w-12 3xl:h-12 4xl:w-16 4xl:h-16 rounded-xl"
              onClick={() => {
                if (isMobile) return setMobileOpen(false);
                toggleSidebar();
              }}
            >
              <IconWrapper Icon={SidebarCloseIcon} size={24} aria-hidden={true} className="3xl:scale-110 4xl:scale-125" />
            </button>
          )}
        </div>

        {/* New Chat Button */}
        <div className={`flex-shrink-0 ${isCollapsed ? 'flex justify-center px-3.5 mt-3 3xl:mt-4 4xl:mt-6 pb-2 3xl:pb-3 4xl:pb-4' : 'px-4 3xl:px-5 mt-3 3xl:mt-4 pb-2'}`}>
          {isCollapsed ? (
            <motion.button
              className="flex items-center justify-center w-10 h-10 3xl:w-12 3xl:h-12 4xl:w-16 4xl:h-16 bg-surface-card border border-border-ui rounded-full hover:bg-surface-subtle transition-colors"
              onClick={handleNewChat}
              aria-label="New chat"
              whileTap={shouldReduceMotion ? undefined : { scale: 0.92 }}
              transition={shouldReduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 22 }}
            >
              <IconWrapper Icon={PlusCircleIcon} size={24} aria-hidden={true} className="3xl:scale-125 4xl:scale-150" />
            </motion.button>
          ) : (
            <motion.button
              className="font-inter w-full bg-surface-card border border-border-ui hover:bg-surface-subtle transition-colors duration-200 gap-2 3xl:gap-2.5 text-body-sm 3xl:text-[17px] 4xl:text-xl font-medium flex items-center justify-center px-5 py-2.5 3xl:py-3 4xl:py-3.5 rounded-full"
              onClick={handleNewChat}
              whileTap={shouldReduceMotion ? undefined : { scale: 0.97 }}
              transition={shouldReduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 22 }}
            >
              <IconWrapper Icon={PlusCircleIcon} size={18} aria-hidden={true} className="3xl:scale-125 4xl:scale-150" />
              <span className="text-foreground">New chat</span>
            </motion.button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className={`flex flex-col flex-shrink-0 ${isCollapsed ? 'items-center gap-2 3xl:gap-3 4xl:gap-4 px-3.5 mt-2 3xl:mt-3 4xl:mt-4' : 'px-4 3xl:px-5 gap-2 3xl:gap-3 mt-2 3xl:mt-3'}`}>
          <NavItem
            to="/case-studies/"
            label="Case studies"
            Icon={BookIcon}
            isActive={location.pathname.includes('/case-study') || location.pathname === '/case-studies/'}
            isCollapsed={isCollapsed}
            onClick={() => isMobile && setMobileOpen(false)}
          />

          <NavItem
            to="/pricing/"
            label="Understanding pricing"
            Icon={PricingIcon}
            isActive={location.pathname === '/pricing/'}
            isCollapsed={isCollapsed}
            onClick={() => isMobile && setMobileOpen(false)}
          />

          <NavItem
            to="/projects/"
            label="Explore projects"
            Icon={ExploreIcon}
            isActive={location.pathname === '/projects/'}
            isCollapsed={isCollapsed}
            onClick={() => isMobile && setMobileOpen(false)}
          />

          <NavItem
            to="/documents/"
            label="Document store"
            Icon={FileIcon}
            isActive={location.pathname === '/documents/'}
            isCollapsed={isCollapsed}
            onClick={() => isMobile && setMobileOpen(false)}
          />

          <NavItem
            to="/"
            label="Chats"
            Icon={ChatIcon}
            isActive={location.pathname === '/'}
            isCollapsed={isCollapsed}
            onClick={() => isMobile && setMobileOpen(false)}
          />
        </nav>

        {/* Separator between nav and chat history */}
        {!isCollapsed && (
          <div className="mx-4 3xl:mx-5 mt-5 3xl:mt-6 border-t border-surface-subtle flex-shrink-0" />
        )}

        <ChatListSection
          chats={chats}
          activeChat={activeChat}
          virtualState={{
            chatListRef,
            chatVirtualizer,
            virtualItems,
          }}
          uiState={{
            isCollapsed,
            isMobile,
            setMobileOpen,
            focusableIndex,
          }}
          actions={{
            setFocusedChatIndex,
            handleChatKeyDown,
            setActiveChat,
            handleDeleteChat,
          }}
        />

        {/* Footer: About & User Menu */}
        <div className="mt-auto flex-shrink-0 border-t border-surface-subtle/60 pt-3 3xl:pt-4">
          <div className={`${isCollapsed ? 'flex flex-col items-center gap-2.5 px-3.5' : 'px-4 3xl:px-5'} pb-3 md:pb-5 3xl:pb-6 4xl:pb-8`}>
            {/* User Menu */}
            <UserMenu
              isCollapsed={isCollapsed}
              isMobile={isMobile}
              setMobileOpen={setMobileOpen}
            />
          </div>
        </div>
      </motion.aside>
    </>
  );
};
