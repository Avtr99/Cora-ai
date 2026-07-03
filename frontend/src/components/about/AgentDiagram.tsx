import React, { useState, useRef, useEffect } from 'react';
import { BRAND, NEUTRAL } from '../../lib/colors';
import {
  Users,
  FileEdit,
  ArrowLeftRight,
  Book,
  Globe,
  FileText,
  FileCheck,
  BookOpen,
} from 'lucide-react';
import geminiText from '../../assets/gemini-text.svg';

/* ────────────────────────────────────────────────────────────────────────────
   Agent Orchestration Diagram – About Page
   Pure static HTML/CSS/SVG diagram with responsive Container Query scaling.
   ─────────────────────────────────────────────────────────────────────────── */

interface AgentCardDef {
  id: string;
  title: string;
  description?: string;
  icon?: React.ElementType;
  x: number;
  y: number;
  w: number;
  h: number;
  isCircle?: boolean;
}

const cards: AgentCardDef[] = [
  { id: 'user', title: 'User query', icon: Users, x: 100, y: 130, w: 130, h: 60 },
  { id: 'rewriter', title: 'Rewriter agent', description: 'Fix typos & expand terms', icon: FileEdit, x: 260, y: 60, w: 160, h: 70 },
  { id: 'router', title: 'Router agent', description: 'KB vs Web vs Hybrid', icon: ArrowLeftRight, x: 480, y: 60, w: 160, h: 70 },
  { id: 'base', title: 'Base model', description: 'Gemini 2.5 flash', x: 505, y: 175, w: 110, h: 110, isCircle: true },
  { id: 'kb', title: 'VCM Knowledge base', icon: Book, x: 260, y: 195, w: 160, h: 70 },
  { id: 'web', title: 'Websearch', description: 'Google Search grounding', icon: Globe, x: 700, y: 195, w: 160, h: 70 },
  { id: 'answer', title: 'Answer Generator', icon: FileText, x: 480, y: 310, w: 160, h: 70 },
  { id: 'validator', title: 'Validator agent', icon: FileCheck, x: 700, y: 310, w: 160, h: 70 },
  { id: 'final', title: 'Final answer', description: 'With citations & sources', icon: BookOpen, x: 480, y: 400, w: 160, h: 60 },
];

/* ── Helper: percentage position ─────────────────────────────────────────── */

function pct(v: number, base: number): string {
  return `${(v / base * 100).toFixed(2)}%`;
}

/* ── Helper: hover / dim class bundle ───────────────────────────────────── */

function getHoverDimClasses(isDimmed: boolean, isHovered: boolean) {
  return {
    transition: "transition-all duration-300 ease-out",
    opacity: isDimmed ? "opacity-30" : "opacity-100",
    scale: isDimmed ? "scale-[0.96]" : "scale-100",
    border: isHovered ? "border-border-ui shadow-card-md" : "border-border-ui",
  };
}

/* ── Card component ────────────────────────────────────────────────────── */

function AgentCard({
  card,
  isHovered,
  isDimmed,
  onMouseEnter,
  onMouseLeave,
}: {
  card: AgentCardDef;
  isHovered: boolean;
  isDimmed: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const left = pct(card.x, 960);
  const top = pct(card.y, 490);
  const width = pct(card.w, 960);
  const minHeight = pct(card.h, 490);

  const { transition, opacity, scale, border } = getHoverDimClasses(isDimmed, isHovered);

  if (card.isCircle) {
    return (
      <div
        className={`absolute flex flex-col items-center justify-center bg-surface-card border rounded-full shadow-card hover:scale-[1.04] z-10 p-2 select-none cursor-pointer ${transition} ${opacity} ${scale} ${border}`}
        style={{ left, top, width, aspectRatio: '1', willChange: 'transform' }}
        tabIndex={0}
        aria-label={card.description ? `${card.title}: ${card.description}` : card.title}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onFocus={onMouseEnter}
        onBlur={onMouseLeave}
      >
        <img
          src={geminiText}
          alt="Gemini"
          className="h-[15%] w-auto mb-1.5 opacity-95 shrink-0"
        />
        <div className="font-poppins font-semibold text-text-primary text-center leading-tight"
          style={{ fontSize: 'clamp(9px, 1.25cqw, 13.5px)' }}>
          {card.title}
        </div>
        {card.description && (
          <div className="font-inter text-text-muted font-medium text-center leading-tight mt-0.5"
            style={{ fontSize: 'clamp(8px, 0.95cqw, 10.5px)' }}>
            {card.description}
          </div>
        )}
      </div>
    );
  }

  const Icon = card.icon;
  return (
    <div
      className={`absolute flex flex-col items-center justify-center bg-surface-card border rounded-xl shadow-card hover:scale-[1.04] hover:-translate-y-0.5 px-2 py-1.5 select-none cursor-pointer z-10 ${transition} ${opacity} ${scale} ${border}`}
      style={{ left, top, width, minHeight, willChange: 'transform' }}
      tabIndex={0}
      aria-label={card.description ? `${card.title}: ${card.description}` : card.title}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onFocus={onMouseEnter}
      onBlur={onMouseLeave}
    >
      {Icon && (
        <div className="w-[24%] aspect-square max-w-[32px] rounded-lg bg-brand-100 flex items-center justify-center text-brand-500 mb-1.5 shrink-0">
          <Icon className="w-[55%] h-[55%]" />
        </div>
      )}
      <div className="font-poppins font-semibold text-text-primary text-center leading-tight w-full"
        style={{ fontSize: 'clamp(9px, 1.2cqw, 13px)' }}>
        {card.title}
      </div>
      {card.description && (
        <div className="font-inter text-text-secondary text-center leading-tight mt-0.5 w-full"
          style={{ fontSize: 'clamp(8px, 0.95cqw, 10.5px)' }}>
          {card.description}
        </div>
      )}
    </div>
  );
}

/* ── Arrow data ──────────────────────────────────────────────────────────── */

interface ArrowDef {
  id: string;
  d: string;
  source: string;
  target: string;
  label?: string;
  labelX?: number;
  labelY?: number;
}

function isLabeledArrow(a: ArrowDef): boolean {
  return !!a.label && typeof a.labelX === 'number' && typeof a.labelY === 'number';
}

// IDs intentionally skip a5 (the "Hybrid" arrow was removed)
const arrows: ArrowDef[] = [
  { id: 'a1', d: 'M230,160 L245,160 L245,95 L260,95', source: 'user', target: 'rewriter' },
  { id: 'a2', d: 'M420,95 L480,95', source: 'rewriter', target: 'router' },
  { id: 'a3', d: 'M560,130 L560,150 L340,150 L340,195', source: 'router', target: 'kb' },
  { id: 'a4', d: 'M560,130 L560,150 L780,150 L780,195', source: 'router', target: 'web' },
  { id: 'a6', d: 'M505,230 L420,230', source: 'base', target: 'kb' },
  { id: 'a7', d: 'M615,230 L700,230', source: 'base', target: 'web' },
  { id: 'a8', d: 'M340,265 L340,290 L560,290 L560,310', source: 'kb', target: 'answer' },
  { id: 'a9', d: 'M780,265 L780,290 L560,290 L560,310', source: 'web', target: 'answer' },
  { id: 'a10', d: 'M560,285 L560,310', source: 'base', target: 'answer' },
  { id: 'a11', d: 'M640,345 L700,345', source: 'answer', target: 'validator', label: 'If low confidence', labelX: 670, labelY: 345 },
  { id: 'a12', d: 'M780,380 L780,430 L640,430', source: 'validator', target: 'final' },
  { id: 'a13', d: 'M560,380 L560,400', source: 'answer', target: 'final' },
];

/* ── Main component ──────────────────────────────────────────────────────── */

// Native design dimensions of the diagram (all card/arrow coordinates use this space).
const NATIVE_W = 960;
const NATIVE_H = 490;
// Readable floor: never shrink below this rendered width. Narrower viewports scroll.
const MIN_RENDER_WIDTH = 680;
const MIN_SCALE = MIN_RENDER_WIDTH / NATIVE_W;

export function AgentDiagram() {
  const [hoveredCardId, setHoveredCardId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  // Proportionally scale the whole diagram to fit the container width,
  // clamped to a readable floor (below which the container scrolls horizontally).
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      const width = el.clientWidth;
      if (width > 0) {
        setScale(Math.min(1, Math.max(MIN_SCALE, width / NATIVE_W)));
      }
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Helper to determine active connection pathways
  const isCardConnected = (cardId: string): boolean => {
    if (!hoveredCardId) return false;
    return arrows.some(a => 
      (a.source === hoveredCardId && a.target === cardId) ||
      (a.target === hoveredCardId && a.source === cardId)
    );
  };

  return (
    <div className="w-full overflow-x-auto" ref={containerRef}>
      <div
        className="mx-auto overflow-hidden"
        style={{ width: NATIVE_W * scale, height: NATIVE_H * scale }}
      >
        <div
          className="relative bg-surface-base rounded-2xl"
          style={{
            width: NATIVE_W,
            height: NATIVE_H,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
            containerType: 'inline-size',
          }}
          aria-label="Interactive agent workflow diagram showing query processing, routing, answer generation, and validation steps."
        >
        {/* ── SVG arrows (bottom layer) ── */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 960 490"
          preserveAspectRatio="xMidYMid meet"
          style={{
            '--arrow-color': NEUTRAL[150],
            '--arrow-active-color': NEUTRAL[600], // muted slate-gray for a balanced, non-purple active state
          } as React.CSSProperties}
        >
          <defs>
            <marker
              id="arrowhead"
              markerWidth="5"
              markerHeight="5"
              refX="4"
              refY="2.5"
              orient="auto"
            >
              <path d="M0,0 L5,2.5 L0,5 Z" fill="var(--arrow-color)" />
            </marker>
            <marker
              id="arrowhead-active"
              markerWidth="5"
              markerHeight="5"
              refX="4"
              refY="2.5"
              orient="auto"
            >
              <path d="M0,0 L5,2.5 L0,5 Z" fill="var(--arrow-active-color)" />
            </marker>
          </defs>
          {arrows.map((a) => {
            const isHovered = hoveredCardId !== null && (a.source === hoveredCardId || a.target === hoveredCardId);
            const isDimmed = hoveredCardId !== null && !isHovered;

            return (
              <path
                key={a.id}
                d={a.d}
                fill="none"
                stroke={isHovered ? "var(--arrow-active-color)" : "var(--arrow-color)"}
                strokeOpacity={isHovered ? "1.0" : isDimmed ? "0.15" : "0.55"}
                strokeWidth={isHovered ? "2.2" : "1.75"}
                className="transition-all duration-300 ease-out"
                markerEnd={isHovered ? "url(#arrowhead-active)" : "url(#arrowhead)"}
              />
            );
          })}
        </svg>

        {/* ── Labels (middle layer) ── */}
        {arrows.filter(isLabeledArrow).map((a) => {
          const isHovered = hoveredCardId !== null && (a.source === hoveredCardId || a.target === hoveredCardId);
          const isDimmed = hoveredCardId !== null && !isHovered;
          const { transition, opacity } = getHoverDimClasses(isDimmed, isHovered);

          return (
            <div
              key={`label-${a.id}`}
              className={`absolute font-inter font-semibold text-center leading-none select-none bg-surface-card border rounded-full px-2 py-0.5 shadow-sm ${transition} ${opacity} z-20 ${
                isHovered
                  ? "border-border-ui text-text-secondary scale-105 shadow-md bg-surface-card"
                  : isDimmed
                  ? "border-border-ui text-text-muted scale-95"
                  : "border-border-ui text-text-secondary"
              }`}
              style={{
                left: pct(a.labelX!, 960),
                top: pct(a.labelY!, 490),
                transform: 'translate(-50%, -50%)',
                fontSize: 'clamp(8px, 0.95cqw, 10.5px)',
              }}
            >
              {a.label}
            </div>
          );
        })}

        {/* ── Cards (top layer) ── */}
        {cards.map((c) => {
          const isHovered = hoveredCardId === c.id;
          const isDimmed = hoveredCardId !== null && hoveredCardId !== c.id && !isCardConnected(c.id);

          return (
            <AgentCard
              key={c.id}
              card={c}
              isHovered={isHovered}
              isDimmed={isDimmed}
              onMouseEnter={() => setHoveredCardId(c.id)}
              onMouseLeave={() => setHoveredCardId(null)}
            />
          );
        })}
        </div>
      </div>
    </div>
  );
}
