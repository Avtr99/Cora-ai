import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react-swc";
import svgr from "vite-plugin-svgr";
import path from "path";
import { readFileSync } from "fs";
import type { ProxyOptions } from "vite";

// Read app version from package.json so it can be shown in the UI and used for cache-busting.
const pkg = JSON.parse(readFileSync("./package.json", "utf-8"));

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const isDev = mode === "development";
  // Default to localhost:8000 — the standard backend port. Users only need
  // frontend/.env.local if their backend runs on a different URL.
  const apiBase = (env.VITE_API_BASE || "http://localhost:8000").replace(/\/$/, "");
  const apiKey = env.VITE_API_KEY;
  const proxySecure = mode === "production" ? true : env.VITE_PROXY_SECURE !== "false";

  const normalizeOrigin = (value: string): string | null => {
    try {
      return new URL(value).origin;
    } catch {
      return null;
    }
  };

  const configuredProdOrigins = (env.PROD_ALLOWED_ORIGINS || "")
    .split(/[\s,]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map(normalizeOrigin)
    .filter((origin): origin is string => Boolean(origin));

  const apiOrigin = apiBase ? normalizeOrigin(apiBase) : null;
  const connectSrcOrigins = [
    "'self'",
    ...(apiOrigin ? [apiOrigin] : []),
    ...configuredProdOrigins,
  ];
  const connectSrcBase = Array.from(new Set(connectSrcOrigins)).join(" ");

  type ProxyServer = Parameters<NonNullable<ProxyOptions["configure"]>>[0];

  const setApiKeyOnProxy = (proxy: ProxyServer) => {
    proxy.on("proxyReq", (proxyReq) => {
      if (apiKey) {
        proxyReq.setHeader("X-API-Key", apiKey);
      }
    });
  };

  return {
    base: "/", // Important for SPA routing when served by FastAPI
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    server: {
      host: "::",
      port: 8080,
      proxy: apiBase
        ? {
            "/api/cora-query-stream": {
              target: apiBase,
              changeOrigin: true,
              secure: proxySecure,
              rewrite: () => "/v1/query/stream",
              configure: (proxy) => {
                setApiKeyOnProxy(proxy);
                // Disable buffering for SSE streaming
                proxy.on("proxyRes", (proxyRes) => {
                  // Prevent response buffering for SSE
                  proxyRes.headers["cache-control"] = "no-cache";
                  proxyRes.headers["x-accel-buffering"] = "no";
                });
              },
            },
            "/api/cora-query": {
              target: apiBase,
              changeOrigin: true,
              secure: proxySecure,
              rewrite: () => "/v1/query",
              configure: setApiKeyOnProxy,
            },
            "/api/documents": {
              target: apiBase,
              changeOrigin: true,
              secure: proxySecure,
              rewrite: (path) => path.replace(/^\/api\/documents/, "/v1/documents"),
              configure: setApiKeyOnProxy,
            },
            "/api/cora-health": {
              target: apiBase,
              changeOrigin: true,
              secure: proxySecure,
              rewrite: () => "/health",
              configure: setApiKeyOnProxy,
            },
            "/api/v1/settings": {
              target: apiBase,
              changeOrigin: true,
              secure: proxySecure,
              rewrite: (path) => path.replace(/^\/api\/v1\/settings/, "/v1/settings"),
              configure: setApiKeyOnProxy,
            },
          }
        : undefined,
      headers: {
        // Content Security Policy (CSP) Headers
        "Content-Security-Policy": [
          // Default sources restriction
          "default-src 'self'",
          // Allow scripts from self and specific CDNs. Keep unsafe-inline for dev only.
          `script-src 'self'${isDev ? " 'unsafe-inline'" : ""} https://cdn.jsdelivr.net`,
          // Allow styles from self and specific CDNs
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
          // Allow images from self and specific image CDNs
          "img-src 'self' data:",
          // Allow fonts from specific providers
          "font-src 'self' https://fonts.gstatic.com",
          // Allow connections to the API. Dev-only websocket/http relaxations.
          isDev
            ? `connect-src ${connectSrcBase} ws: http: https:`
            : `connect-src ${connectSrcBase}`,
          // Allow blob workers for dev tooling in development only.
          `worker-src 'self'${isDev ? " blob:" : ""}`,
          // Frame sources
          "frame-src 'self'",
          // Object sources
          "object-src 'none'",
          // Media sources
          "media-src 'self'"
        ].join("; "),
        // Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",
        // Prevent embedding in iframes on other domains
        "X-Frame-Options": "SAMEORIGIN"
      }
    },
    plugins: [
      react(),
      // SVGR plugin for importing SVGs as React components
      // Usage: import Icon from './icon.svg?react'
      svgr({
        svgrOptions: {
          // Don't use TypeScript syntax that causes esbuild issues
          typescript: false,
          // Keep it simple - let vite-plugin-svgr use defaults
          ref: true,
          svgoConfig: {
            plugins: [
              {
                name: 'preset-default',
                params: {
                  overrides: {
                    // Keep viewBox for responsive scaling
                    removeViewBox: false,
                  },
                },
              },
            ],
          },
        },
      }),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    build: {
      // Modern target to reduce unnecessary legacy transforms/polyfills for current browsers.
      target: 'es2022',
      // Generate hidden source maps in production for debugging without exposing map URLs publicly.
      sourcemap: mode === 'production' ? 'hidden' : true,
      rollupOptions: {
        output: {
          // Minimal manual chunks: only pin the small, shared utilities that
          // Rollup's auto-chunker otherwise absorbs into heavy library chunks
          // (e.g. clsx being dragged into the recharts chunk, which would then
          // force recharts to be <link rel="modulepreload">-loaded on every
          // page). Everything else auto-splits based on the dynamic-import
          // graph, which is what Vite is good at.
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined;
            // Eagerly-used React core + router + tiny radix primitives
            // consumed by `Button` (which `TermsOfServicePopup` imports).
            if (/[\\/]node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom|@remix-run[\\/]router|@radix-ui[\\/]react-(?:slot|compose-refs))[\\/]/.test(id)) {
              return 'react-vendor';
            }
            // Class-name / variant utilities used across every page.
            // Note: tailwindcss-animate is a build-time plugin, not a runtime dep — excluded.
            if (/[\\/]node_modules[\\/](clsx|tailwind-merge|class-variance-authority)[\\/]/.test(id)) {
              return 'vendor-utils';
            }
            // framer-motion is used by many components across eager + lazy boundaries.
            // Pin it so it doesn't bloat the main chunk or get duplicated.
            if (/[\\/]node_modules[\\/]framer-motion[\\/]/.test(id)) {
              return 'framer-motion';
            }
            // lucide-react is tree-shaken but still large when summed across many icons.
            if (/[\\/]node_modules[\\/]lucide-react[\\/]/.test(id)) {
              return 'lucide';
            }
            // recharts + d3 deps are huge and only used on the pricing page.
            // Pin them so they don't bloat whichever page chunk imports PricingChart.
            if (/[\\/]node_modules[\\/](recharts|d3-(?:array|color|format|interpolate|path|scale|shape|time|time-format|voronoi)|internmap|decimal\.js-light)[\\/]/.test(id)) {
              return 'recharts-vendor';
            }
            return undefined;
          },
        },
      },
    },
  };
});
