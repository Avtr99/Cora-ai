/**
 * Lazy-loads project detail data from projects-detail.json.
 *
 * The detail file is a flat { id: VCMProjectDetail } map fetched once
 * and cached by React Query. Components call useProjectDetail(id) to
 * attach _detail to a VCMProject on demand — the summary file no longer
 * carries _detail, saving ~90% of the initial payload.
 */
import { useQuery } from '@tanstack/react-query';
import type { VCMProject, VCMProjectDetail } from '@/types/project';
import { PROJECT_DATA_VERSION } from '@/generated/projectVersion';

/** Shape of the detail file: project-id → detail object */
type DetailMap = Record<string, VCMProjectDetail>;

async function fetchDetailMap(): Promise<DetailMap> {
  const res = await fetch('/data/projects-detail.json');
  if (!res.ok) throw new Error(`Failed to fetch project details: ${res.status}`);
  return res.json();
}

/**
 * Returns a function that enriches a VCMProject with its _detail.
 * The detail file is fetched once on first call, then cached forever.
 */
export function useProjectDetailEnricher() {
  const { data: detailMap } = useQuery({
    queryKey: ['vcm-project-details', PROJECT_DATA_VERSION],
    queryFn: fetchDetailMap,
    staleTime: Infinity,
    // Prefers cached data when offline; fetches immediately when online.
    // Data is fetched once on first component mount, then cached forever.
    networkMode: 'offlineFirst',
  });

  /**
   * Attach _detail to a project if available.
   * Returns the same project reference if detail is already present
   * or if the detail map hasn't loaded yet.
   */
  function enrich(project: VCMProject): VCMProject {
    if (project._detail) return project;
    const detail = detailMap?.[project.id];
    if (!detail) return project;
    return { ...project, _detail: detail };
  }

  /**
   * Attach _detail to multiple projects at once.
   */
  function enrichAll(projects: VCMProject[]): VCMProject[] {
    if (!detailMap) return projects;
    return projects.map(enrich);
  }

  const isLoading = !detailMap;

  return { enrich, enrichAll, isLoading };
}

/**
 * Convenience hook: enrich a single project and return it with _detail.
 * Re-renders automatically when the detail map finishes loading.
 */
export function useEnrichedProject(project: VCMProject | null): VCMProject | null {
  const { enrich } = useProjectDetailEnricher();
  if (!project) return null;
  return enrich(project);
}
