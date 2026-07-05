import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { Copy, ExternalLink } from 'lucide-react';
import type { Components } from 'react-markdown';
import { sanitizeInput, sanitizeUrl } from '@/lib/security';
import { CitationGroup, InlineCitationPill } from './chatMessageCitations';
import { preprocessContent, CITATION_INTERNAL_URL } from './chatMessageCitations.utils';
import { GlossaryHydrator } from './glossary/GlossaryHydrator';

type MarkdownLinkProps = React.AnchorHTMLAttributes<HTMLAnchorElement> & {
  href?: string;
  children?: React.ReactNode;
};

type MarkdownImgRendererProps = React.ImgHTMLAttributes<HTMLImageElement> & {
  src?: string;
  alt?: string;
};

// ── Static renderers hoisted to module scope (never recreated) ─────────
const StaticUl = (props: React.HTMLAttributes<HTMLUListElement>) => (
  <ul className="list-disc pl-6 space-y-1.5 mb-3" {...props} />
);
const StaticOl = (props: React.OlHTMLAttributes<HTMLOListElement>) => (
  <ol className="list-decimal pl-6 space-y-1.5 mb-3" {...props} />
);
const StaticLi = (props: React.LiHTMLAttributes<HTMLLIElement>) => (
  <li className="leading-relaxed" {...props} />
);
const StaticP = ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className="mb-2 last:mb-0 leading-relaxed" {...props}><GlossaryHydrator>{children}</GlossaryHydrator></p>
);
const StaticStrong = (props: React.HTMLAttributes<HTMLElement>) => (
  <strong className="font-semibold" {...props} />
);
const StaticImg = ({ src = '', alt = '', ...imgProps }: MarkdownImgRendererProps) => {
  const safeSrc = sanitizeUrl(src);
  const safeAlt = sanitizeInput(alt);
  if (!safeSrc) return null;
  const { referrerPolicy: ___, ...safeProps } = imgProps;
  return (
    <img
      src={safeSrc}
      alt={safeAlt}
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      className="max-w-full h-auto max-h-80 object-contain rounded-md border border-surface-subtle"
      {...safeProps}
    />
  );
};
const StaticTable = ({ children }: React.TableHTMLAttributes<HTMLTableElement>) => (
  <div className="my-5 overflow-x-auto rounded-xl border border-border-ui shadow-card-sm">
    <table className="w-full border-collapse text-sm">{children}</table>
  </div>
);
const StaticThead = ({ children }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className="bg-surface-subtle border-b border-border-ui">{children}</thead>
);
const StaticTbody = ({ children }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody className="divide-y divide-border-ui">{children}</tbody>
);
const StaticTr = (props: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className="even:bg-surface-subtle/60 transition-colors hover:bg-surface-subtle" {...props} />
);
const StaticTh = (props: React.ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className="px-4 py-2.5 text-left font-poppins font-semibold text-xs uppercase tracking-[0.08em] text-text-muted" {...props} />
);
const StaticTd = (props: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className="px-4 py-2.5 font-inter text-sm text-text-secondary leading-[1.5]" {...props} />
);
const StaticBlockquote = ({ children }: React.BlockquoteHTMLAttributes<HTMLQuoteElement>) => (
  <blockquote className="my-6 rounded-lg border border-border-ui bg-surface-card/50 px-5 py-4 text-text-secondary shadow-card-sm text-sm italic leading-relaxed [&>p]:mb-0 [&>p:last-child]:mb-0">
    {children}
  </blockquote>
);

const REMARK_PLUGINS = [remarkGfm];
const REHYPE_PLUGINS = [rehypeSanitize];
const DISALLOWED_ELEMENTS = ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'];

export interface CitationNumberMap {
  kb: number[];
  web: number[];
}

interface ChatMarkdownContentProps {
  content: string;
  messageId: string;
  mounted: boolean;
  copyText: (text: string) => Promise<void>;
  citationNumberMap?: CitationNumberMap;
}

export const ChatMarkdownContent: React.FC<ChatMarkdownContentProps> = ({
  content,
  messageId,
  mounted,
  copyText,
  citationNumberMap,
}) => {
  // Only renderers that depend on props need to live inside the component
  const components = useMemo<Components>(() => ({
    ul: StaticUl,
    ol: StaticOl,
    li: StaticLi,
    p: StaticP,
    strong: StaticStrong,
    img: StaticImg,
    table: StaticTable,
    thead: StaticThead,
    tbody: StaticTbody,
    tr: StaticTr,
    th: StaticTh,
    td: StaticTd,
    blockquote: StaticBlockquote,
    code: (props) => {
      const { children, className, ...rest } = props;
      const text = String(children ?? '');
      const inline =
        'inline' in props && typeof props.inline === 'boolean'
          ? props.inline
          : undefined;
      const isInlineCode = inline ?? !text.includes('\n');

      if (isInlineCode) {
        return <code className="px-1 py-0.5 rounded bg-surface-subtle text-sm" {...rest}>{children}</code>;
      }

      return (
        <div className="relative group">
          <button
            type="button"
            onClick={() => copyText(text)}
            className="absolute top-2 right-2 p-1.5 rounded bg-surface-card/80 hover:bg-surface-card text-text-muted shadow-sm"
            aria-label="Copy code"
            title="Copy code"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
          <pre className={className}>
            <code {...rest}>{children}</code>
          </pre>
        </div>
      );
    },
    a: ({ href = '', children, ...anchorProps }: MarkdownLinkProps) => {
      if (href && href.startsWith(CITATION_INTERNAL_URL)) {
        try {
          const urlObj = new URL(href);
          const pathParts = urlObj.pathname.split('/').filter(Boolean);
          const type = pathParts[0];
          const numsStr = pathParts[1];

          const cleanNumsStr = numsStr ? decodeURIComponent(numsStr) : '';
          const localNumbers = cleanNumsStr
            ? cleanNumsStr
                .split(',')
                .map((n: string) => parseInt(n, 10))
                .filter((n: number) => !isNaN(n) && n > 0)
            : [];

          if (localNumbers.length === 0) {
            return null;
          }

          // Map backend per-type numbers (KB 1..N, Web 1..M) to the single
          // global sequence used by the source list.
          const map = citationNumberMap;
          const globalNumbers = localNumbers
            .map((n: number) => {
              const list = type === 'kb' ? map?.kb : map?.web;
              return list && n >= 1 && n <= list.length ? list[n - 1] : undefined;
            })
            .filter((n: number | undefined): n is number => n !== undefined);

          if (globalNumbers.length === 0) {
            return null;
          }

          const group: CitationGroup = {
            numbers: globalNumbers,
          };

          return <InlineCitationPill group={group} messageId={messageId} />;
        } catch {
          // fall through to standard link handling
        }
      }

      const safeHref = sanitizeUrl(href);
      if (!safeHref) {
        return <span className="text-text-secondary underline decoration-dotted">{children}</span>;
      }
      let isExternal = false;
      if (safeHref.startsWith('/') && !safeHref.startsWith('//')) {
        isExternal = false;
      } else if (typeof window !== 'undefined') {
        try {
          const u = new URL(safeHref, window.location.origin);
          isExternal = u.host !== window.location.host;
        } catch {
          isExternal = true;
        }
      } else {
        isExternal = true;
      }
      const { target: __, rel: ___, ...safeProps } = anchorProps;
      return (
        <a
          href={safeHref}
          target={isExternal ? '_blank' : undefined}
          rel={isExternal ? 'noopener noreferrer' : undefined}
          className="text-brand-700 underline break-words inline-flex items-center gap-1"
          {...safeProps}
        >
          {children}
          {isExternal && <ExternalLink className="inline-block h-3.5 w-3.5" aria-hidden="true" />}
        </a>
      );
    },
  } as Components), [copyText, messageId, citationNumberMap]);

  return (
    <div className={`markdown-content font-inter font-normal text-sm leading-relaxed text-text-primary transition-opacity duration-300 ${mounted ? 'opacity-100' : 'opacity-0'}`}>
      <ReactMarkdown
        skipHtml={true}
        disallowedElements={DISALLOWED_ELEMENTS}
        unwrapDisallowed={true}
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_PLUGINS}
        components={components}
      >
        {preprocessContent(content)}
      </ReactMarkdown>
    </div>
  );
};
