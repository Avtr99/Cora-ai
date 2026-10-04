import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Flame, Sprout, Trees, Zap, type LucideIcon } from 'lucide-react';
import { KPI } from '@/lib/colors';
import { CLAIMS_FLOW, type FlowIconId, type FlowSinkId } from '@/data/pricingFactorContent';

const SINK_ICONS: Record<FlowIconId, LucideIcon> = {
  flame: Flame,
  sprout: Sprout,
  trees: Trees,
  zap: Zap,
};

const SINK_COLORS: Record<FlowSinkId, string> = {
  neutral: KPI.removal,
  oer: KPI.reduction,
};

interface Ribbon {
  index: number;
  sink: FlowSinkId;
  path: string;
  stub: { x: number; y: number };
}

/** Landing stub marking where a sink's ribbons arrive (always full opacity). */
interface SinkStub {
  sink: FlowSinkId;
  x: number;
  y: number;
  height: number;
}

const RIBBON_THICKNESS = 22;

/**
 * Credit types on the left, the two claim outcomes on the right, and a ribbon
 * per credit tracing where it lands. Hovering or selecting a credit dims the
 * rest and reads out its rule. Ribbons are measured from the laid-out grid, so
 * they are recomputed on resize and skipped where the layout collapses.
 */
const ClaimFlow: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sourcesRef = useRef<HTMLDivElement>(null);
  const sinksRef = useRef<HTMLDivElement>(null);
  const sinkRefs = useRef<Partial<Record<FlowSinkId, HTMLDivElement | null>>>({});
  const sourceRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [ribbons, setRibbons] = useState<Ribbon[]>([]);
  const [sinkStubs, setSinkStubs] = useState<SinkStub[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const active = hovered ?? pinned;
  const { sources, sinks, resting } = CLAIMS_FLOW;

  const measure = useCallback(() => {
    const container = containerRef.current;
    const sourceColumn = sourcesRef.current;
    const sinkColumn = sinksRef.current;
    if (!container || !sourceColumn || !sinkColumn) return;
    const box = container.getBoundingClientRect();
    if (!box.width || !sinkColumn.getBoundingClientRect().width) {
      setRibbons([]);
      setSinkStubs([]);
      return;
    }
    const start = sourceColumn.getBoundingClientRect().right - box.left;
    const end = sinkColumn.getBoundingClientRect().left - box.left + 6;
    const slots: Record<FlowSinkId, number> = { neutral: 0, oer: 0 };
    const anchor: Record<FlowSinkId, number> = { neutral: 0, oer: 0 };

    const stubs: SinkStub[] = [];
    sinks.forEach((sink) => {
      const element = sinkRefs.current[sink.id];
      if (!element) return;
      const rect = element.getBoundingClientRect();
      const count = sources.filter((source) => source.to === sink.id).length;
      const height = count * RIBBON_THICKNESS + (count - 1) * 3;
      anchor[sink.id] = rect.top - box.top + rect.height / 2 - height / 2;
      stubs.push({ sink: sink.id, x: end - 6, y: anchor[sink.id], height });
    });
    setSinkStubs(stubs);

    const drawn: Ribbon[] = sources.map((source, index) => {
      const element = sourceRefs.current[index];
      const rect = element?.getBoundingClientRect();
      const top = rect ? rect.top - box.top + rect.height / 2 - RIBBON_THICKNESS / 2 : 0;
      const bottom = anchor[source.to] + slots[source.to]++ * (RIBBON_THICKNESS + 3);
      const middle = (start + end) / 2;
      return {
        index,
        sink: source.to,
        path:
          `M${start},${top} C${middle},${top} ${middle},${bottom} ${end - 6},${bottom} ` +
          `L${end - 6},${bottom + RIBBON_THICKNESS} C${middle},${bottom + RIBBON_THICKNESS} ` +
          `${middle},${top + RIBBON_THICKNESS} ${start},${top + RIBBON_THICKNESS} Z`,
        stub: { x: start, y: top },
      };
    });
    setRibbons(drawn);
  }, [sinks, sources]);

  useLayoutEffect(() => {
    measure();
    window.addEventListener('resize', measure);
    document.fonts?.ready.then(measure).catch(() => undefined);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(container);
    return () => observer.disconnect();
  }, [measure]);

  const ribbonClass = (index: number) =>
    `transition-opacity duration-500 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none ${
      active === null ? 'opacity-[0.22]' : index === active ? 'opacity-[0.55]' : 'opacity-[0.08]'
    }`;

  return (
    <div>
      <div
        ref={containerRef}
        className="relative grid grid-cols-1 gap-6 md:grid-cols-[13.75rem_minmax(7.5rem,1fr)_18.75rem] md:gap-0"
      >
        <svg className="pointer-events-none absolute inset-0 hidden h-full w-full overflow-visible md:block" aria-hidden="true">
          {sinkStubs.map((stub) => (
            <rect
              key={`sink-${stub.sink}`}
              x={stub.x}
              y={stub.y}
              width="6"
              height={stub.height}
              rx="2"
              fill={SINK_COLORS[stub.sink]}
            />
          ))}
          {ribbons.map((ribbon) => (
            <path key={ribbon.index} className={ribbonClass(ribbon.index)} fill={SINK_COLORS[ribbon.sink]} d={ribbon.path} />
          ))}
          {ribbons.map((ribbon) => (
            <rect
              key={`stub-${ribbon.index}`}
              className={ribbonClass(ribbon.index)}
              x={ribbon.stub.x}
              y={ribbon.stub.y}
              width="4"
              height={RIBBON_THICKNESS}
              rx="1.5"
              fill={SINK_COLORS[ribbon.sink]}
            />
          ))}
        </svg>

        <div ref={sourcesRef} className="flex flex-col gap-3.5">
          {sources.map((source, index) => {
            const Icon = SINK_ICONS[source.icon];
            return (
              <button
                key={source.code}
                ref={(element) => {
                  sourceRefs.current[index] = element;
                }}
                type="button"
                aria-pressed={pinned === index}
                className={`grid min-h-14 grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-3 rounded-xl pr-4 text-left transition-opacity duration-500 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus ${
                  active === null ? 'opacity-100' : index === active ? 'opacity-100' : 'opacity-45'
                }`}
                onMouseEnter={() => setHovered(index)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(index)}
                onBlur={() => setHovered(null)}
                onClick={() => setPinned(pinned === index ? null : index)}
              >
                <span
                  className={`grid h-10 w-10 place-items-center rounded-lg transition-colors duration-500 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none ${
                    active === index ? 'text-text-inverse' : 'bg-surface-subtle text-text-primary'
                  }`}
                  style={active === index ? { backgroundColor: SINK_COLORS[source.to] } : undefined}
                >
                  <Icon aria-hidden="true" strokeWidth={2} className="h-5 w-5" />
                </span>
                <span className="min-w-0">
                  <b className="block font-poppins text-body-sm 3xl:text-base font-semibold text-text-primary tabular-nums">
                    {source.code}
                  </b>
                  <em className="block font-inter text-caption font-normal text-text-muted">{source.type}</em>
                  <span className="mt-0.5 block text-caption font-semibold text-text-primary md:hidden">
                    <span aria-hidden="true" style={{ color: SINK_COLORS[source.to] }}>
                      {'\u2192 '}
                    </span>
                    {sinks.find((sink) => sink.id === source.to)?.title}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div aria-hidden="true" className="hidden md:block" />

        <div ref={sinksRef} className="hidden flex-col justify-between gap-6 pl-5.5 md:flex">
          {sinks.map((sink) => (
            <div
              key={sink.id}
              ref={(element) => {
                sinkRefs.current[sink.id] = element;
              }}
              className={`transition-opacity duration-500 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none ${
                active === null ? 'opacity-100' : sources[active]?.to === sink.id ? 'opacity-100' : 'opacity-35'
              }`}
            >
              <span
                className="inline-flex items-center gap-2 font-inter text-caption font-semibold text-text-primary"
              >
                <span
                  aria-hidden="true"
                  className={`h-2 w-2 shrink-0 rounded-full ${
                    sink.tone === 'success' ? 'bg-kpi-removal' : 'bg-kpi-reduction'
                  }`}
                />
                {sink.status}
              </span>
              <h4 className="mt-2 font-poppins text-body 3xl:text-lg font-semibold tracking-tight text-text-primary">
                {sink.title}
              </h4>
              <p className="mt-1.5 max-w-[34ch] text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
                {sink.body}
              </p>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-6 min-h-14 border-t border-border-ui pt-4 font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-secondary">
        {active === null ? (
          resting
        ) : (
          <>
            <strong className="font-semibold text-text-primary">{sources[active].message.lead}</strong>
            {sources[active].message.body}
          </>
        )}
      </p>
    </div>
  );
};

export default ClaimFlow;
