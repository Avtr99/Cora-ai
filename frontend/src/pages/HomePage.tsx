import React, { lazy, Suspense } from "react";

const ReactQueryDevtools = import.meta.env.DEV
  ? lazy(() =>
      import('@tanstack/react-query-devtools').then(m => ({ default: m.ReactQueryDevtools }))
    )
  : () => null;
import { SidebarProvider } from "@/contexts/useSidebar";
import { ChatProvider } from "@/contexts/ChatContext";
import { UserProvider } from "@/contexts/UserContext";
import ErrorBoundary from "@/components/ErrorBoundary";
import Index from "@/pages/Index";

/**
 * HomePage wraps chat-specific providers and UI that are only needed on the home/chat route.
 * This keeps non-chat routes (e.g. pricing) lighter by avoiding unnecessary provider and animation code.
 */
const HomePage: React.FC = () => {
  return (
    <>
      {/* TanStack Query DevTools - lazy-loaded only in development */}
      {import.meta.env.DEV && (
        <Suspense fallback={null}>
          <ReactQueryDevtools initialIsOpen={false} />
        </Suspense>
      )}
      <ErrorBoundary
        fallback={
          <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center gap-4 text-center px-6">
            <p className="text-brand-700 font-poppins text-base">
              Something went wrong while loading chat.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-5 py-2 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-md transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
            >
              Reload
            </button>
          </div>
        }
        onError={(error, info) => {
          console.error('HomePage error:', error, info.componentStack);
        }}
      >
        <UserProvider>
          <SidebarProvider>
            <ChatProvider>
              <Index />
            </ChatProvider>
          </SidebarProvider>
        </UserProvider>
      </ErrorBoundary>
    </>
  );
};

export default HomePage;
