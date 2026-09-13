import React, { useState, useEffect, lazy, Suspense } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { SearchBar } from "@/components/ui/SearchBar";
import { ChatScrollButton } from "@/components/chat/ChatScrollButton";
import { useSidebar } from "@/contexts/useSidebar";
import { useChatContext } from "@/contexts/useChatContext";
import { useUserContext } from "@/contexts/useUserContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { useChatReadiness } from "@/hooks/useChatReadiness";
import { motion, AnimatePresence } from "framer-motion";
import { sanitizeInput } from "@/lib/security";

// Lazy-load ChatInterface to defer loading react-markdown (336KB) and react-virtual
const ChatInterface = lazy(() => import("@/components/chat/ChatInterface").then(m => ({ default: m.ChatInterface })));

// Simple loading skeleton for chat
const ChatSkeleton = () => (
  <div className="flex-1 flex items-center justify-center">
    <div className="animate-pulse text-text-muted font-inter text-body-sm 3xl:text-lg 4xl:text-xl">Loading chat...</div>
  </div>
);

const PROMPT_CARDS = [
  {
    tag: "Methodology",
    text: "How is the VM0048 different from other deforestation methodologies?",
  },
  {
    tag: "Policy",
    text: "What are the takeaways from COP 30?",
  },
  {
    tag: "Pricing",
    text: "What factors influence the pricing of carbon credits in the VCM?",
  },
];

const Index: React.FC = () => {
  const { isCollapsed } = useSidebar();
  const { activeChat, isTyping, sendMessage, createNewChat } = useChatContext();
  const { userProfile } = useUserContext();
  const isMobile = useIsMobile();
  const { chatReady } = useChatReadiness();
  const [isUserTyping, setIsUserTyping] = useState(false);
  const [isReady, setIsReady] = useState(false);

  const handlePromptClick = (text: string, tag: string) => {
    if (!chatReady) return;
    const sanitized = sanitizeInput(text);
    if (sanitized.trim()) {
      // If no active chat or active chat has messages, create a new one
      if (!activeChat || activeChat.messages.length > 0) {
        const newChat = createNewChat(sanitized);
        // createNewChat returns null if userProfile is not ready
        if (!newChat) {
          console.error('Cannot create chat: user profile not loaded');
        }
      } else {
        // Use existing empty chat
        sendMessage(sanitized);
      }
    }
  };

  // Check if UserContext is ready by monitoring userProfile.
  // The chat itself is additionally gated by backend readiness (KB / web search).
  useEffect(() => {
    setIsReady(!!userProfile);
  }, [userProfile]);

  const [scrollbarWidth, setScrollbarWidth] = useState(0);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const scrollContainerRef = React.useRef<HTMLElement>(null);
  const composerRef = React.useRef<HTMLDivElement>(null);
  const [composerHeight, setComposerHeight] = useState(0);

  // Measure system scrollbar width once
  useEffect(() => {
    const outer = document.createElement('div');
    outer.style.visibility = 'hidden';
    outer.style.overflow = 'scroll';
    document.body.appendChild(outer);
    const inner = document.createElement('div');
    outer.appendChild(inner);
    const width = outer.offsetWidth - inner.offsetWidth;
    document.body.removeChild(outer);
    setScrollbarWidth(width);
  }, []);

  // Track if the chat container is actually overflowing (has a scrollbar visible)
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    const checkOverflow = () => {
      // Use 1px tolerance for subpixel rounding
      setIsOverflowing(el.scrollHeight > el.clientHeight + 1);
    };

    checkOverflow();
    const resizeObserver = new ResizeObserver(checkOverflow);
    resizeObserver.observe(el);

    const mutationObserver = new MutationObserver(checkOverflow);
    mutationObserver.observe(el, { childList: true, subtree: true, characterData: true });

    return () => {
      resizeObserver.disconnect();
      mutationObserver.disconnect();
    };
  }, [activeChat?.id, activeChat?.messages.length]);

  // Measure the fixed composer so scroll clearance tracks its real height
  // across breakpoints, wrapping, rate-limit and disclaimer changes.
  useEffect(() => {
    const el = composerRef.current;
    if (!el) return;

    const update = () => {
      setComposerHeight(Math.ceil(el.getBoundingClientRect().height));
    };

    update();
    const resizeObserver = new ResizeObserver(update);
    resizeObserver.observe(el);
    window.addEventListener('resize', update);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [isMobile, isCollapsed, isOverflowing, activeChat?.id, activeChat?.messages.length]);

  return (
    // h-dvh (dynamic viewport height) keeps `main` exactly the size of the
    // VISIBLE viewport on mobile/tablet browsers. h-screen (100vh) is the
    // "large" viewport (with UA chrome retracted), which on tablets like
    // Brave/Safari on Android/iPad extends below the visible fold → the
    // document body becomes scrollable and the sidebar (inside main) scrolls
    // off-screen alongside the chat content. h-dvh eliminates that whole-page
    // scroll bug. Desktop is unaffected because dvh === vh without UA chrome.
    <main className="bg-surface-base h-dvh flex flex-col overflow-hidden [--sidebar-width:240px] [--sidebar-collapsed-width:68px] [--composer-bottom:1rem] 3xl:[--sidebar-width:300px] 3xl:[--sidebar-collapsed-width:80px] 3xl:[--composer-bottom:1.5rem] 4xl:[--sidebar-width:400px] 4xl:[--sidebar-collapsed-width:96px] 4xl:[--composer-bottom:2rem]">
      {/* Main Page Heading - Visually Hidden but accessible to screen readers */}
      <h1 className="sr-only">Cora - Voluntary Carbon Market AI Assistant</h1>

      <div className="flex flex-1 max-md:flex-col overflow-hidden">
        {/* Sidebar - Fixed width, scrollable internally */}
        <motion.div
          className="flex-shrink-0 max-md:w-full max-md:h-auto h-full overflow-hidden"
          animate={{ width: isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)' }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          style={{ height: isMobile ? 'auto' : '100%' }}
        >
          {/* Sidebar has its own internal scrolling */}
          <Sidebar />
        </motion.div>

        {/* Main content area - Explicit scroll container for virtualizer */}
        <motion.section
          ref={scrollContainerRef}
          data-chat-scroll-container
          className="flex-1 overflow-y-auto overflow-x-clip relative min-w-0 max-md:h-[calc(100dvh-60px)] h-full"
          style={{ height: isMobile ? 'calc(100dvh - 60px)' : '100%' }}
        >
          <div className="grow min-h-full min-w-0 pt-10 max-md:pt-14 px-6 md:px-8 3xl:pt-12 3xl:px-12 max-md:max-w-full flex flex-col">
            <div className={`w-full min-w-0 flex-1 flex flex-col ${activeChat && activeChat.messages.length > 0 ? 'max-w-2xl 3xl:max-w-[850px] 4xl:max-w-[960px]' : 'max-w-5xl 3xl:max-w-7xl 4xl:max-w-[1536px]'} max-md:max-w-full mx-auto`}>
              <AnimatePresence>
                {!isTyping && !activeChat?.messages.length && !isUserTyping && (
                  <motion.header
                    className="flex w-full flex-col items-center text-center max-md:max-w-full pt-6 md:pt-32 3xl:pt-[clamp(11rem,18dvh,14rem)] 4xl:pt-[clamp(16rem,20dvh,22rem)]"
                    initial={{ opacity: 1, y: 0 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -30 }}
                    transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
                  >
                    <div className="w-full overflow-hidden flex flex-col items-center">
                      {/* Cora Logo */}
                      <motion.div
                        className="mb-3 md:mb-6"
                        initial={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
                      >
                        <img src="/cora.svg" alt="" aria-hidden="true" className="w-12 h-12 md:w-16 md:h-16 3xl:w-20 3xl:h-20 4xl:w-24 4xl:h-24" />
                      </motion.div>

                      <motion.h2
                        className="font-poppins text-heading-1 md:text-display font-semibold text-brand-700 max-md:max-w-full 3xl:text-[35px] 4xl:text-[44px] leading-tight text-balance"
                        initial={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -15 }}
                        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                      >
                        Hi, I'm Cora!
                      </motion.h2>
                      <motion.p
                        className="font-inter text-text-muted text-body-sm md:text-body mt-1 md:mt-2 max-md:max-w-full 3xl:text-xl 4xl:text-2xl 3xl:mt-2.5 4xl:mt-3"
                        initial={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1], delay: 0.05 }}
                        style={{ marginTop: 'auto' }}
                      >
                        Your VCM Educational AI assistant
                      </motion.p>
                    </div>
                  </motion.header>
                )}
              </AnimatePresence>

              <div className="flex-grow flex flex-col relative">
                <div className="flex-grow min-h-0">
                  <AnimatePresence mode="wait">
                    {activeChat && activeChat.messages.length > 0 ? (
                      <motion.div
                        key="chat-interface"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{ duration: 0.3 }}
                        className="w-full md:max-w-[680px] 3xl:max-w-[850px] 4xl:max-w-[960px] md:mx-auto"
                      >
                        <Suspense fallback={<ChatSkeleton />}>
                          <ChatInterface />
                        </Suspense>
                      </motion.div>
                    ) : (
                      !isTyping && !isUserTyping && (
                        <motion.div
                          key="topics"
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -30, scale: 0.98 }}
                          transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
                          className="flex w-full flex-col items-start justify-end flex-1 pb-20 md:pb-8 md:pt-20 3xl:pt-24 4xl:pt-28"
                          style={{ marginTop: 'auto', paddingTop: isMobile ? '1.5rem' : undefined }}
                        >
                          <p className="font-inter text-caption md:text-body-sm text-text-muted mb-2 md:mb-3 3xl:text-[17px] 4xl:text-xl 3xl:mb-4 4xl:mb-5">
                            Get started with prompts
                          </p>

                          <motion.div
                            className="grid w-full gap-2 md:gap-3 3xl:gap-4 4xl:gap-5 sm:grid-cols-2 lg:grid-cols-3"
                            initial="hidden"
                            animate="show"
                            variants={{
                              hidden: { opacity: 1 },
                              show: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
                            }}
                          >
                            {PROMPT_CARDS.map(({ tag, text }) => {
                              const promptEnabled = isReady && chatReady;
                              return (
                                <motion.button
                                  key={tag}
                                  type="button"
                                  onClick={() => promptEnabled && handlePromptClick(text, tag)}
                                  disabled={!promptEnabled}
                                  variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }}
                                  className={`group flex h-full flex-col rounded-lg md:rounded-xl 4xl:rounded-2xl border border-border-ui bg-white px-3.5 py-3 md:px-4 md:py-3.5 3xl:px-6 3xl:py-5 4xl:px-8 4xl:py-6 text-left shadow-card transition-all duration-200 ${promptEnabled ? 'hover:border-brand-500 hover:shadow-[0_8px_16px_rgba(111,78,203,0.12)] cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                                >
                                  <span className="font-poppins text-overline font-semibold uppercase tracking-wider text-brand-500 3xl:text-[15px] 4xl:text-[17px]">
                                    {tag}
                                  </span>
                                  <p className="mt-2 md:mt-2.5 3xl:mt-3 4xl:mt-3.5 font-inter text-caption md:text-ui 3xl:text-base 4xl:text-lg text-text-secondary">{text}</p>
                                </motion.button>
                              );
                            })}
                          </motion.div>
                        </motion.div>
                      )
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>
            {/* In-flow spacer reserves composer space. Unlike scroll-container
                padding-bottom, a spacer is always part of the scrollable
                overflow area, so the last message can't be cut off. */}
            <div aria-hidden="true" style={{ height: composerHeight, flexShrink: 0 }} />
          </div>
        </motion.section>



        {/* SearchBar moved outside the main content area to prevent jumping */}
        <div
          ref={composerRef}
          className="fixed bottom-0 py-1 md:py-2 3xl:py-3 4xl:py-4 z-20 bg-surface-base transition-all duration-200"
          style={{
            left: isMobile ? '0' : (isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'),
            right: isOverflowing ? `${scrollbarWidth}px` : '0px',
            // Keep a smaller bottom padding on mobile, plus iOS safe-area when present
            paddingBottom: isMobile ? 'calc(0.25rem + env(safe-area-inset-bottom, 0px))' : 'calc(var(--composer-bottom) + env(safe-area-inset-bottom, 0px))'
          }}>
          {/* Match exact width of the main content container to ensure perfect alignment */}
          <div className="w-full px-6 md:px-8 3xl:px-12">
            <div className={`relative w-full ${activeChat && activeChat.messages.length > 0 ? 'md:max-w-[680px] 3xl:max-w-[850px] 4xl:max-w-[960px] md:mx-auto' : 'max-w-5xl 3xl:max-w-7xl 4xl:max-w-[1536px] mx-auto'}`}>
              <ChatScrollButton hasMessages={activeChat ? activeChat.messages.length > 0 : false} />
              <SearchBar
                onTypingStateChange={(typing) => setIsUserTyping(typing)}
                variant={activeChat && activeChat.messages.length > 0 ? 'composer' : 'large'}
              />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default Index;
