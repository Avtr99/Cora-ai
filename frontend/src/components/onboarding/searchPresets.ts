/**
 * Shared web-search provider options.
 *
 * Used by both the onboarding SearchStep and the SettingsDialog search tab
 * so provider labels and descriptions stay in sync.
 */

export type SearchProvider = "tavily" | "none";

export const SEARCH_PROVIDER_PRESETS: Record<
  SearchProvider,
  { label: string; description: string }
> = {
  tavily: {
    label: "Tavily",
    description: "AI web search",
  },
  none: {
    label: "Disabled",
    description: "KB-only mode",
  },
};
