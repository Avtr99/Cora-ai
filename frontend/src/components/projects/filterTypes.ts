import type { ProjectFilterKey } from '@/types/project';

export interface FilterOption {
  value: string;
  count: number;
}

export interface FilterDef {
  key: ProjectFilterKey;
  label: string;
}
