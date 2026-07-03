import React, { useEffect } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { getCaseStudyById } from '@/data/caseStudies';
import { getShortProjectName } from '@/lib/utils';

/**
 * Public site URL for canonical/OG/Twitter metadata.
 *
 * Set `VITE_PUBLIC_URL` in `frontend/.env.local` to your deployed URL
 * (e.g. `https://your-instance.example.com`). Defaults to the origin the
 * SPA is served from so it works correctly on any self-hosted deployment
 * without configuration. Trailing slash is stripped.
 */
const PUBLIC_URL = (import.meta.env.VITE_PUBLIC_URL ?? '').replace(/\/$/, '');
const SITE_AUTHOR = 'Cora AI Contributors';

/** Build a canonical/OG URL for the given pathname. */
function buildUrl(pathname: string): string {
  const path = pathname === '/' ? '' : pathname;
  if (PUBLIC_URL) return `${PUBLIC_URL}${path}/`;
  // Fallback: use the runtime origin so self-hosted instances get correct URLs.
  return `${window.location.origin}${path}/`;
}

interface PageMeta {
  title: string;
  description: string;
  keywords?: string;
  ogType?: string;
  structuredData?: Record<string, unknown>;
}

const pageMetaMap: Record<string, PageMeta> = {
  '/': {
    title: 'Cora | Carbon Credits & Voluntary Carbon Market AI',
    description:
      'Cora is an AI assistant for carbon credits and the voluntary carbon market. Learn about carbon credit pricing, methodologies, project types, and VCM trends.',
    keywords:
      'voluntary carbon market, carbon credits, carbon offsets, VCM, AI assistant, carbon pricing, sustainability, climate action',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: 'Cora',
      description: 'Cora is an AI assistant for carbon credits and the voluntary carbon market.',
      publisher: {
        '@type': 'Organization',
        name: SITE_AUTHOR,
      },
    },
  },
  '/pricing': {
    title: 'Carbon Credit Pricing | Cora',
    description:
      'Explore historical and current carbon credit pricing data across project types including REDD+, Renewable Energy, Agriculture, and Household Devices.',
    keywords:
      'carbon credit pricing, carbon market prices, VCM pricing, REDD+ prices, renewable energy credits, carbon offset costs',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Carbon Credit Pricing',
      description: 'Explore historical and current carbon credit pricing data across project types.',
    },
  },
  '/case-studies': {
    title: 'Case Studies | Cora',
    description:
      'Read in-depth case studies on voluntary carbon market projects, methodologies, and real-world applications of carbon offsetting.',
    keywords: 'carbon market case studies, VCM projects, carbon offset examples, sustainability case studies',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Case Studies',
      description: 'In-depth case studies on voluntary carbon market projects and methodologies.',
    },
  },
  '/case-study': {
    title: 'Case Study | Cora',
    description:
      'Read in-depth case studies on voluntary carbon market projects, methodologies, and real-world applications of carbon offsetting.',
    keywords: 'carbon market case studies, VCM projects, carbon offset examples, sustainability case studies',
    ogType: 'article',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Case Study',
      description: 'In-depth case studies on voluntary carbon market projects and methodologies.',
    },
  },
  '/about': {
    title: 'About Cora | VCM Educational AI',
    description:
      'Learn about Cora, the educational AI assistant designed to help you navigate the Voluntary Carbon Market with trusted data sources and insights.',
    keywords: 'about Cora, VCM AI assistant, carbon market education, sustainability tools',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'About Cora',
      description: 'Learn about Cora, the educational AI assistant for the Voluntary Carbon Market.',
    },
  },
  '/projects': {
    title: 'Carbon Projects | Cora',
    description:
      'Browse carbon offset projects across the Voluntary Carbon Market. Filter by category, standard, and country.',
    keywords: 'carbon projects, VCM projects, carbon offset registry, verified carbon units',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Carbon Projects',
      description: 'Browse carbon offset projects across the Voluntary Carbon Market.',
    },
  },
  '/documents': {
    title: 'Document Store | Cora',
    description:
      'Upload and manage documents that power Cora’s knowledge base for the Voluntary Carbon Market.',
    keywords: 'VCM documents, knowledge base, document ingestion, carbon market documents',
    ogType: 'website',
    structuredData: {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: 'Document Store',
      description: 'Upload and manage documents that power Cora’s knowledge base.',
    },
  },
  '/privacy-policy/': {
    title: 'Privacy Policy | Cora',
    description: 'Cora privacy policy. Learn how we handle your data and protect your privacy.',
  },
  '/terms-of-service/': {
    title: 'Terms of Service | Cora',
    description: 'Cora terms of service and usage conditions.',
  },
  '/cookie-policy/': {
    title: 'Cookie Policy | Cora',
    description: 'Cora cookie policy. Learn how we use cookies and tracking technologies.',
  },
};

function getPageMeta(pathname: string): PageMeta {
  const normalizedPath = pathname === '/' ? pathname : pathname.replace(/\/$/, '');
  
  // Check for exact match first
  if (pageMetaMap[normalizedPath]) {
    return pageMetaMap[normalizedPath];
  }
  
  // Check for case study detail pages (dynamic routes)
  if (normalizedPath.startsWith('/case-study/')) {
    return pageMetaMap['/case-study'] || pageMetaMap['/'];
  }
  
  // Default fallback
  return {
    title: 'Cora | Carbon Credits & Voluntary Carbon Market AI',
    description:
      'Cora is an AI assistant for carbon credits and the voluntary carbon market.',
  };
}

function ensureMetaTag(selector: string, attribute: 'name' | 'property', value: string): HTMLMetaElement {
  const existingMeta = document.querySelector(selector);
  if (existingMeta instanceof HTMLMetaElement) {
    return existingMeta;
  }

  const meta = document.createElement('meta');
  meta.setAttribute(attribute, value);
  document.head.appendChild(meta);
  return meta;
}

function ensureLinkTag(rel: string, href: string): HTMLLinkElement {
  const existing = document.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
  if (existing) {
    existing.href = href;
    return existing;
  }
  const link = document.createElement('link');
  link.rel = rel;
  link.href = href;
  document.head.appendChild(link);
  return link;
}

/**
 * DocumentHead component that dynamically updates document title, meta tags,
 * canonical URL, and OpenGraph tags based on the current route.
 *
 * Note: This runs client-side after hydration. For crawlers that do not execute
 * JavaScript, the static tags in index.html are what they see. For full SEO
 * coverage of dynamic meta tags, consider pre-rendering or SSR.
 */
const DocumentHead: React.FC = () => {
  const location = useLocation();
  const { id } = useParams<{ id: string }>();

  useEffect(() => {
    const pathname = location.pathname;
    let meta = getPageMeta(pathname);
    
    // Dynamic title for case study detail pages
    if (pathname.startsWith('/case-study/') && id) {
      const caseStudy = getCaseStudyById(id);
      if (caseStudy) {
        const shortName = getShortProjectName(caseStudy.title);
        meta = {
          ...meta,
          title: `${shortName} | Cora`,
          description: `Case study: ${caseStudy.title}. ${caseStudy.summary}`,
        };
      }
    }
    
    const canonicalUrl = buildUrl(pathname);

    document.title = meta.title;

    // Favicon
    ensureLinkTag('icon', '/cora.svg');

    // Canonical URL
    ensureLinkTag('canonical', canonicalUrl);

    // Description
    const descTag = ensureMetaTag('meta[name="description"]', 'name', 'description');
    descTag.setAttribute('content', meta.description);

    // Keywords
    const kwTag = document.querySelector('meta[name="keywords"]') as HTMLMetaElement | null;
    if (meta.keywords) {
      (kwTag ?? ensureMetaTag('meta[name="keywords"]', 'name', 'keywords')).setAttribute('content', meta.keywords);
    } else if (kwTag) {
      kwTag.remove();
    }

    // OpenGraph
    const ogTitle = ensureMetaTag('meta[property="og:title"]', 'property', 'og:title');
    ogTitle.setAttribute('content', meta.title);

    const ogDesc = ensureMetaTag('meta[property="og:description"]', 'property', 'og:description');
    ogDesc.setAttribute('content', meta.description);

    const ogUrl = ensureMetaTag('meta[property="og:url"]', 'property', 'og:url');
    ogUrl.setAttribute('content', canonicalUrl);

    const ogType = ensureMetaTag('meta[property="og:type"]', 'property', 'og:type');
    ogType.setAttribute('content', meta.ogType ?? 'website');

    // Twitter
    const twTitle = ensureMetaTag('meta[name="twitter:title"]', 'name', 'twitter:title');
    twTitle.setAttribute('content', meta.title);

    const twDesc = ensureMetaTag('meta[name="twitter:description"]', 'name', 'twitter:description');
    twDesc.setAttribute('content', meta.description);

    // Structured Data (JSON-LD)
    const existingLd = document.querySelector('script[data-seo="json-ld"]');
    if (existingLd) {
      existingLd.remove();
    }
    if (meta.structuredData) {
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.setAttribute('data-seo', 'json-ld');
      // Inject the canonical URL into structured data so it matches the page.
      script.textContent = JSON.stringify({ ...meta.structuredData, url: canonicalUrl });
      document.head.appendChild(script);
    }
  }, [location.pathname, id]);

  return null;
};

export { DocumentHead };
