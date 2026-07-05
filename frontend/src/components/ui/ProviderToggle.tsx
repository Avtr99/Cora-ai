import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { ChevronDown, Check, Zap } from "lucide-react";
import {
  getAvailableProviders,
  switchLLMProvider,
  type AvailableProvider,
} from "@/services/llmSettingsApi";

/**
 * ProviderToggle — compact badge + dropdown for switching LLM providers.
 *
 * Shows the current provider name as a small badge. Click opens a dropdown
 * listing all configured providers. Switching is instant (hot-swap, no restart).
 * Useful when a provider hits rate limits — the user can switch mid-conversation.
 *
 * Only renders if more than one provider is configured. If only one provider
 * has an API key, the toggle is hidden to avoid clutter.
 */
export const ProviderToggle: React.FC = () => {
  const [providers, setProviders] = useState<AvailableProvider[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const shouldReduceMotion = useReducedMotion();

  // Fetch available providers on mount
  useEffect(() => {
    getAvailableProviders()
      .then((data) => {
        setProviders(data.available);
        setCurrent(data.current);
      })
      .catch(() => {/* non-critical */});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen]);

  // Don't render if only one or zero providers are configured
  if (providers.length <= 1) return null;

  const currentProvider = providers.find((p) => p.slug === current);
  const currentLabel = currentProvider?.label ?? "Unknown";

  const handleSwitch = async (slug: string) => {
    if (slug === current || switching) return;
    setSwitching(true);
    setError(null);
    try {
      const result = await switchLLMProvider(slug);
      if (result.success) {
        setCurrent(result.label ?? slug);
        setIsOpen(false);
      } else {
        setError(result.error ?? "Switch failed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Switch failed");
    } finally {
      setSwitching(false);
    }
  };

  return (
    <div ref={dropdownRef} className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={switching}
        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium border transition-colors disabled:opacity-50"
        style={{
          borderColor: "var(--color-border-ui, #e5e7eb)",
          background: "var(--color-surface-subtle, #f9fafb)",
          color: "var(--color-text-secondary, #4b5563)",
        }}
        aria-label={`LLM provider: ${currentLabel}. Click to switch.`}
        title="Switch LLM provider"
      >
        <Zap className="w-3 h-3 opacity-60" />
        <span className="max-w-[100px] truncate">{currentLabel}</span>
        <ChevronDown
          className={`w-3 h-3 opacity-50 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={shouldReduceMotion ? { opacity: 1 } : { opacity: 0, y: -4 }}
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.15 }}
            className="absolute bottom-full left-0 mb-2 w-56 rounded-xl border shadow-lg overflow-hidden z-50"
            style={{
              borderColor: "var(--color-border-ui, #e5e7eb)",
              background: "var(--color-surface-card, #ffffff)",
            }}
          >
            <div className="px-3 py-2 border-b" style={{ borderColor: "var(--color-border-ui, #e5e7eb)" }}>
              <span className="text-xs font-semibold uppercase tracking-wide opacity-50">
                LLM Provider
              </span>
            </div>
            <div className="py-1">
              {providers.map((p) => (
                <button
                  key={p.slug}
                  onClick={() => handleSwitch(p.slug)}
                  disabled={switching}
                  className="w-full flex items-center justify-between px-3 py-2 text-left text-sm transition-colors hover:bg-surface-subtle disabled:opacity-50"
                >
                  <div className="flex flex-col min-w-0">
                    <span className="font-medium truncate" style={{ color: "var(--color-text-primary, #111827)" }}>
                      {p.label}
                    </span>
                    <span className="text-xs opacity-50 truncate">{p.model}</span>
                  </div>
                  {p.slug === current && (
                    <Check className="w-4 h-4 shrink-0 ml-2 text-brand-500" />
                  )}
                </button>
              ))}
            </div>
            {error && (
              <div className="px-3 py-2 text-xs text-red-500 border-t" style={{ borderColor: "var(--color-border-ui, #e5e7eb)" }}>
                {error}
              </div>
            )}
            {switching && (
              <div className="px-3 py-2 text-xs opacity-50 border-t" style={{ borderColor: "var(--color-border-ui, #e5e7eb)" }}>
                Switching...
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
