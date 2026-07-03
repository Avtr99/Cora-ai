import { useQuery } from '@tanstack/react-query';
import { feature } from 'topojson-client';
import { geoCentroid } from 'd3-geo';

export interface WorldData {
  topology: unknown;
  disputedTopology: unknown;
  centroidByTopoName: Map<string, [number, number]>;
}

async function fetchWorld(): Promise<WorldData> {
  const [resWorld, resDisputed] = await Promise.all([
    fetch('/data/countries-50m.json'),
    fetch('/data/disputed-areas-50m.json'),
  ]);
  if (!resWorld.ok) throw new Error(`Failed to load world geometry: ${resWorld.status} ${resWorld.statusText}`);
  if (!resDisputed.ok) throw new Error(`Failed to load disputed areas geometry: ${resDisputed.status} ${resDisputed.statusText}`);

  const [topo, topoDisputed] = await Promise.all([
    resWorld.json(),
    resDisputed.json(),
  ]);

  const fc = feature(topo, topo.objects.countries) as {
    features: { properties: { name: string } }[];
  };
  const centroidByTopoName = new Map<string, [number, number]>();
  for (const f of fc.features) {
    if (!f.properties?.name) continue;
    const c = geoCentroid(f as unknown as Parameters<typeof geoCentroid>[0]) as [number, number];
    centroidByTopoName.set(f.properties.name, c);
  }
  return { topology: topo, disputedTopology: topoDisputed, centroidByTopoName };
}

export function useWorldData() {
  return useQuery({
    queryKey: ['world-topojson'],
    queryFn: fetchWorld,
    staleTime: Infinity,
  });
}
