import React, { useState, useEffect, lazy, Suspense } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { SearchBar } from "@/components/ui/SearchBar";
import { ScrollToTop } from "@/components/ui/ScrollToTop";
import { useSidebar } from "@/contexts/useSidebar";
import { useChatContext } from "@/contexts/useChatContext";
import { useUserContext } from "@/contexts/useUserContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { useChatReadiness } from "@/hooks/useChatReadiness";
import { ChatReadinessBanner } from "@/components/chat/ChatReadinessBanner";
import { motion, AnimatePresence } from "framer-motion";
import { sanitizeInput } from "@/lib/security";

// Lazy-load ChatInterface to defer loading react-markdown (336KB) and react-virtual
const ChatInterface = lazy(() => import("@/components/chat/ChatInterface").then(m => ({ default: m.ChatInterface })));

// Simple loading skeleton for chat
const ChatSkeleton = () => (
  <div className="flex-1 flex items-center justify-center">
    <div className="animate-pulse text-text-muted font-inter text-sm">Loading chat...</div>
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
  const { chatReady, isLoading: isReadinessLoading } = useChatReadiness();
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

  return (
    // h-dvh (dynamic viewport height) keeps `main` exactly the size of the
    // VISIBLE viewport on mobile/tablet browsers. h-screen (100vh) is the
    // "large" viewport (with UA chrome retracted), which on tablets like
    // Brave/Safari on Android/iPad extends below the visible fold → the
    // document body becomes scrollable and the sidebar (inside main) scrolls
    // off-screen alongside the chat content. h-dvh eliminates that whole-page
    // scroll bug. Desktop is unaffected because dvh === vh without UA chrome.
    <main className="bg-surface-base h-dvh flex flex-col overflow-hidden">
      {/* Main Page Heading - Visually Hidden but accessible to screen readers */}
      <h1 className="sr-only">Cora - Voluntary Carbon Market AI Assistant</h1>

      <div className="flex flex-1 max-md:flex-col overflow-hidden">
        {/* Sidebar - Fixed width, scrollable internally */}
        <motion.div
          className="flex-shrink-0 max-md:w-full overflow-hidden"
          animate={{ width: isCollapsed ? 68 : 240 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          style={{ height: isMobile ? 'auto' : '100%' }}
        >
          {/* Sidebar has its own internal scrolling */}
          <Sidebar />
        </motion.div>

        {/* Main content area - Explicit scroll container for virtualizer */}
        <motion.section
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto relative"
          animate={{ marginLeft: isCollapsed ? 2 : 5 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          style={{ height: isMobile ? 'calc(100dvh - 60px)' : '100%', paddingBottom: isMobile ? '100px' : '160px' }} /* Extra padding to ensure content doesn't hide behind search bar */
        >
          {/* Scroll to top button - only show when chat has messages */}
          {activeChat && activeChat.messages.length > 0 && (
            <ScrollToTop
              variant="compact"
              scrollContainerSelector="[data-chat-scroll-container]"
            />
          )}

          <div className="grow h-full pt-10 max-md:pt-14 pb-12 px-6 md:px-8 max-md:max-w-full">
            <div className="w-full h-full flex flex-col max-w-5xl max-md:max-w-full mx-auto">
              <AnimatePresence>
                {!isTyping && !activeChat?.messages.length && !isUserTyping && (
                  <motion.header
                    className="flex w-full flex-col items-center text-center max-md:max-w-full pt-6 md:pt-32"
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
                        <img src="/cora.svg" alt="" aria-hidden="true" className="w-12 h-12 md:w-16 md:h-16" />
                      </motion.div>

                      <motion.h2
                        className="font-poppins text-[28px] leading-8 md:text-[34px] md:leading-10 font-semibold text-brand-700 tracking-tight max-md:max-w-full"
                        initial={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -15 }}
                        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
                      >
                        Hi, I'm Cora!
                      </motion.h2>
                      <motion.p
                        className="font-inter text-text-muted text-sm md:text-base mt-1 md:mt-2 max-md:max-w-full"
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
                <div className="flex-grow pb-16 md:pb-24 min-h-0" style={{ paddingBottom: isMobile ? 'calc(4rem + env(safe-area-inset-bottom, 0px))' : 'calc(8rem + env(safe-area-inset-bottom, 0px))' }}>
                  <AnimatePresence mode="wait">
                    {activeChat && activeChat.messages.length > 0 ? (
                      <motion.div
                        key="chat-interface"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{ duration: 0.3 }}
                        className="w-full md:max-w-2xl md:mx-auto"
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
                          className="flex w-full flex-col items-start justify-end flex-1 pb-20 md:pb-8"
                          style={{ marginTop: 'auto', paddingTop: isMobile ? '1.5rem' : '5rem' }}
                        >
                          <p className="font-inter text-xs md:text-sm text-text-muted mb-2 md:mb-3">
                            Get started with prompts
                          </p>

                          <motion.div
                            className="grid w-full gap-2 md:gap-3 sm:grid-cols-2 lg:grid-cols-3"
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
                                  className={`group flex h-full flex-col rounded-lg md:rounded-xl border border-border-ui bg-white px-3.5 py-3 md:px-4 md:py-3.5 text-left shadow-card transition-all duration-200 ${promptEnabled ? 'hover:border-brand-500 hover:shadow-[0_8px_16px_rgba(111,78,203,0.12)] cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
                                >
                                  <span className="font-poppins text-xs font-semibold uppercase tracking-wider text-brand-500">
                                    {tag}
                                  </span>
                                  <p className="mt-2 md:mt-2.5 font-inter text-xs md:text-sm text-text-secondary leading-snug">{text}</p>
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
          </div>
        </motion.section>



        {/* SearchBar moved outside the main content area to prevent jumping */}
        <div className="fixed bottom-0 py-1 md:py-2 z-20 bg-surface-base transition-all duration-200"
          style={{
            left: isMobile ? '0' : (isCollapsed ? '68px' : '240px'),
            right: isOverflowing ? `${scrollbarWidth}px` : '0px',
            // Keep a smaller bottom padding on mobile, plus iOS safe-area when present
            paddingBottom: isMobile ? 'calc(0.25rem + env(safe-area-inset-bottom, 0px))' : 'calc(1rem + env(safe-area-inset-bottom, 0px))'
          }}>
          {/* Match exact width of the main content container to ensure perfect alignment */}
          <div className="w-full px-6 md:px-8">
            <div className={`w-full ${activeChat && activeChat.messages.length > 0 ? 'md:max-w-2xl md:mx-auto' : 'max-w-5xl mx-auto'}`}>
              {!isReadinessLoading && <ChatReadinessBanner />}
              <div className={!isReadinessLoading ? 'mt-2' : ''}>
                <SearchBar
                  onTypingStateChange={(typing) => setIsUserTyping(typing)}
                  variant={activeChat && activeChat.messages.length > 0 ? 'composer' : 'large'}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default Index;
