/**
 * TanStack Query Configuration
 * Central configuration for React Query client with optimized defaults
 */

import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      console.error('Query error:', error);
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      console.error('Mutation error:', error);
    },
  }),
  defaultOptions: {
    queries: {
      // Cache data for 5 minutes (same as previous custom cache)
      staleTime: 5 * 60 * 1000, // 5 minutes
      
      // Keep unused data in cache for 5 minutes
      gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
      
      // Retry failed requests 3 times with exponential backoff
      // Don't retry on AbortError (user cancellation or timeout)
      retry: (failureCount, error) => {
        // Don't retry if request was aborted (user cancellation or timeout)
        if (error instanceof DOMException && error.name === 'AbortError') {
          return false;
        }
        // Retry up to 3 times for other errors
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      
      // Don't refetch on window focus in development (can be annoying)
      refetchOnWindowFocus: import.meta.env.PROD,
      
      // Refetch on mount when data is stale (default: true)
      // This ensures fresh data while respecting staleTime
      
      // Refetch on reconnect to get latest data
      refetchOnReconnect: true,
    },
    mutations: {
      // Don't retry mutations by default to avoid duplicate side-effects
      // Individual mutations can opt-in to retries if they are idempotent
      retry: 0,
    },
  },
});
