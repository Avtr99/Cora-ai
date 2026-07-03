import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";

/**
 * DataProviders wraps routes that need `@tanstack/react-query`.
 *
 * Kept in its own module so it can be lazy-imported from `App.tsx` — pages
 * that don't fetch data (legal pages, pricing, case-study, etc.) never pay
 * the ~10 KiB gzipped cost of loading react-query + the query client.
 */
const DataProviders = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

export default DataProviders;
