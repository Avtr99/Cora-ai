import * as React from "react"

// Mirrors the custom screens in tailwind.config.ts (`extend.screens`).
// Used where layout dimensions are computed in JS (e.g. the animated sidebar
// width) and therefore cannot use 3xl:/4xl: CSS variants.
const BREAKPOINT_3XL = 1920
const BREAKPOINT_4XL = 2400

export type WideBreakpoint = 'base' | '3xl' | '4xl'

function getBreakpoint(): WideBreakpoint {
  if (typeof window === "undefined") return 'base'
  if (window.matchMedia(`(min-width: ${BREAKPOINT_4XL}px)`).matches) return '4xl'
  if (window.matchMedia(`(min-width: ${BREAKPOINT_3XL}px)`).matches) return '3xl'
  return 'base'
}

export function useWideBreakpoint(): WideBreakpoint {
  const [breakpoint, setBreakpoint] = React.useState<WideBreakpoint>(getBreakpoint)

  React.useEffect(() => {
    const queries = [`(min-width: ${BREAKPOINT_4XL}px)`, `(min-width: ${BREAKPOINT_3XL}px)`]
    const mqls = queries.map((q) => window.matchMedia(q))
    const onChange = () => setBreakpoint(getBreakpoint())
    mqls.forEach((mql) => mql.addEventListener("change", onChange))
    onChange()
    return () => mqls.forEach((mql) => mql.removeEventListener("change", onChange))
  }, [])

  return breakpoint
}
