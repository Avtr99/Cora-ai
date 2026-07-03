import { QueryClient } from '@tanstack/react-query';
import type { VCMProjectDetail } from '@/types/project';
import { PROJECT_DATA_VERSION } from '@/generated/projectVersion';

/**
 * Creates a fresh QueryClient pre-seeded with project detail data.
 * Call this inside each story decorator (not at module scope) so every
 * story render gets an isolated cache.
 */
export function createProjectQueryClient(
  detailMap: Record<string, VCMProjectDetail>,
): QueryClient {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        staleTime: Infinity,
      },
    },
  });
  client.setQueryData(['vcm-project-details', PROJECT_DATA_VERSION], detailMap);
  return client;
}
