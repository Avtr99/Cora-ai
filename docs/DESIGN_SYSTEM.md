# Design System Documentation

Design system for the Cora VCM application. Single source of truth — one entry per concern. **`src/lib/colors.ts` is the canonical color module**; all components should import from it instead of hardcoding hex values.

---

## Design Tokens

### Typography

**Setup** — Google Fonts imported in `index.html`; Tailwind configured with `font-poppins` and `font-inter` utility classes.

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

```js
// tailwind.config.ts
fontFamily: { sans: ['Inter', ...], poppins: ['Poppins', 'sans-serif'], inter: ['Inter', 'sans-serif'] }
```

#### Type Scale

| Style | Font | Size | Weight | Line-height | Tracking | Tailwind |
|---|---|---|---|---|---|---|
| H1 | Poppins | 56px | 700 | 67px | -1.12px | `font-poppins font-bold text-[56px] leading-[67px] tracking-[-1.12px]` |
| H2 | Poppins | 40px | 600 | 52px | -0.4px | `font-poppins font-semibold text-[40px] leading-[52px] tracking-[-0.4px]` |
| H3 | Poppins | 32px | 600 | 45px | -0.16px | `font-poppins font-semibold text-[32px] leading-[45px] tracking-[-0.16px]` |
| H4 | Poppins | 24px | 500 | 34px | — | `font-poppins font-medium text-2xl leading-[34px]` |
| H5 | Poppins | 20px | 500 | 30px | — | `font-poppins font-medium text-xl leading-[30px]` |
| H6 | Poppins | 16px | 600 | 24px | 0.8px | `font-poppins font-semibold text-base leading-6 tracking-[0.8px]` |
| Body-Bold | Inter | 16px | 600 | 22px | — | `font-inter font-semibold text-base leading-[22px]` |
| Body-Medium | Inter | 16px | 500 | 26px | — | `font-inter font-medium text-base leading-[26px]` |
| Body-Regular | Inter | 16px | 400 | 26px | — | `font-inter font-normal text-base leading-[26px]` |
| Body-Small Bold | Inter | 12px | 600 | 16px | — | `font-inter font-semibold text-xs leading-4` |
| Body-Small | Inter | 12px | 400 | 16px | — | `font-inter font-normal text-xs leading-4` |
| Button Label | Inter | 10px | 600 | 9px | 0.1px | `font-inter font-semibold text-[10px] leading-[9px] tracking-[0.1px]` |
| Subtitle/Label | Poppins | 10px | 600 | normal | — | `font-poppins font-semibold text-[10px] uppercase` |

---

### Colors

All tokens live in **`src/lib/colors.ts`**. Never hardcode hex values in components — import from this module.

#### CSS Variables (shadcn/ui — `src/index.css`)

Several tokens intentionally share the same value in light mode but diverge in dark mode/custom themes:
- `--secondary` / `--muted` / `--accent` → all `hsl(210 40% 96.1%)` in light mode
- `--card` / `--popover` / `--background` → all `hsl(0 0% 100%)`

#### `colors.ts` Exports

| Export | Purpose |
|---|---|
| `BRAND` | Brand purple scale: `primary950` (#2E1065), `primary900` (#403D85), `primary700` (#4A2AA3), `primary500` (#6F4ECB), `primary300` (#C4B5FD), `primary200` (#E9D5FF), `primary100` (#F3E8FF), `primary50` (#FAF5FF) |
| `NEUTRAL` | Neutral gray scale: 0 (#FFFFFF), 25 (#FAFAFA), 50 (#F8F9FA), 100 (#F3F4F6), 150 (#E5E7EB), 200 (#D6D6D6), 300 (#B8BEC8), 400 (#6B7280), 600 (#4B5563), 800 (#525252), 900 (#171717) |
| `TEXT` | Semantic text: `primary` #171717, `body` #525252, `muted` #6B7280, `disabled` #B8BEC8, `inverse` #FFFFFF |
| `INTERACTIVE` | States: `default` #6B7280, `hover/active` #6F4ECB, `focusRing` rgba(74,42,163,0.35) |
| `ICON_STATE` | Icon states: `default` #6B7280, `active/selected` #6F4ECB |
| `getProjectTypeColor(type)` | Returns `{ accent, bg, text }` for Forest/REDD+, Renewable, Agriculture, Cookstove/Household, Landfill/Industrial, default purple |
| `getStatusStyle(status)` | Returns `{ bg, text, dot }` for registered/active (green), completed (blue), cancelled (red), under development (amber), crediting period ended (gray) |
| `TREND_COLORS` | Trend badges / icon colors: rising (green), declining (orange), note (amber) |

#### Semantic Quick Reference

| Role | Value | Usage |
|---|---|---|
| Text primary | `#171717` | Headings, key labels |
| Text body | `#525252` | Card content, descriptions |
| Text muted | `#6B7280` | Captions, metadata, section labels |
| Page bg | `#FAFAFA` (`surface-base`) | App shell background; data pages use `surface-page` `#F7F8FB` |
| Surface base | `#FAFAFA` | Panels, alt table rows |
| Surface subtle | `#F3F4F6` | Input bg, dividers |
| Border | `#E5E7EB` (`border-ui`) | All borders (unifies #E5E5E5, #ECECF0, #E7E7E7) |
| Brand primary | `#403D85` | Buttons, main actions |
| Brand secondary | `#6F4ECB` | Hover states, active icons |
| Brand link | `#4A2AA3` | Nav links, back buttons |
| Warning bg | `#FFFBEB` (`semantic-warning-bg`) | Alert / notice cards |
| Warning border | `#FEF3C7` (`semantic-warning-border`) | Alert / notice cards |
| Warning icon | `#F59E0B` (`semantic-warning-icon`) | Alert icons |

---

### Spacing & Sizing

- Base unit: `0.25rem` (4px)
- Standard button padding: `px-4 py-2`
- Flex gap: `gap-2.5` (10px)
- Pill padding: `px-4 py-2`

### Border Radius

CSS variable `--radius: 0.5rem` (8px). Derived:
- `rounded-lg` → 8px, `rounded-md` → 6px, `rounded-sm` → 4px, `rounded-xs` → 2px
- Custom: `rounded-[20px]` pills, `rounded-2xl` cards, `rounded-full` badges

### App Type Scale (`tailwind.config.ts` `fontSize`)

Marketing H1–H6 above are for hero/page titles. In-app UI uses these utilities instead:

| Token | Size / Line-height | Use |
|---|---|---|
| `text-display` | 28px / 1.10, -0.02em | Large in-app headings |
| `text-heading-1` | 22px / 1.20 | Panel / page headings |
| `text-heading-2` | 18px / 1.25 | Section headings |
| `text-heading-3` | 16px / 1.30 | Sub-section headings |
| `text-body` | 16px / 1.60 | Default body |
| `text-body-sm` | 14px / 1.50 | Compact body |
| `text-ui` | 13px / 1.35 | UI labels, table cells |
| `text-caption` | 12px / 1.40 | Captions, metadata |
| `text-overline` | 11px / 1.30 | Uppercase micro labels |
| `text-micro` / `text-2xs` | 10px / 1.25 | Superscripts, footnotes (`micro` adds 0.05em tracking; `2xs` is the legacy alias) |

### Elevation (Shadows)

Defined as CSS custom properties in `src/index.css` and Tailwind utilities in `tailwind.config.ts`.

| Class | Value | Use |
|---|---|---|
| `shadow-xs` | `0 1px 2px rgba(0,0,0,0.05)` | Base cards, pills |
| `shadow-card` | `0 2px 8px rgba(0,0,0,0.04)` | Prompt cards |
| `shadow-card-md` | `0 2px 8px rgba(0,0,0,0.06)` | SearchBar large |
| `shadow-card-sm` | `0 2px 6px rgba(0,0,0,0.04)` | SearchBar composer |
| `shadow-bottom-bar` | `0 -4px 16px rgba(0,0,0,0.08)` | Cookie consent bar |
| `shadow-modal` | `0 32px 64px -12px rgba(0,0,0,0.14)` | Modals |
| `shadow-scroll-btn` | `0 2px 8px rgba(0,0,0,0.08)` | Scroll-to-top button |

Glow effects (inline, single-use): send button large `0 0 20px rgba(111,78,203,0.25)`, composer `0 0 12px rgba(111,78,203,0.2)`.

### Focus Rings

Standard: `focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(74,42,163,0.35)] focus-visible:ring-offset-2 focus-visible:ring-offset-white`

Light variant (dropdowns): `focus-visible:ring-[rgba(74,42,163,0.25)]`

Placeholder text: `placeholder:text-muted-foreground/70`

### Motion & Animation

- Standard: `transition-colors duration-200`
- Layout/sidebar: Framer Motion `{ duration: 0.2, ease: 'easeOut' }`
- Reasoning panel expand: `.reasoning-content` fades/slides in ~200ms via `details[open]` CSS; respects `prefers-reduced-motion`
- Keyframes: `accordion-down`, `accordion-up` for expandable elements

---

## Components

### Sidebar
- **File**: `src/components/layout/Sidebar.tsx`
- **Collapsed**: 60px — icon-only nav items (`w-10 h-10`), compact New Chat button
- **Expanded**: 250px — icon + label nav items (`gap-2 px-3 py-2`)
- **Animation**: Framer Motion 200ms easeOut
- **Features**: TanStack Virtual for chat list, mobile hamburger menu
- **Nav items**: Chat, Knowledge Base, Pricing, Explore Projects, About

### SearchBar
- **File**: `src/components/ui/SearchBar.tsx`
- **Large variant** (main page): blurred gradient glow behind composer — `linear-gradient(135deg, rgba(147,51,234,0.15), rgba(236,72,153,0.15))` at `opacity-40 blur-2xl z-[-1]`; send button glow `shadow-[0_0_20px_rgba(111,78,203,0.25)]`; shadow `shadow-card-md`
- **Composer variant** (chat page): compact, no gradient bg; send button glow `shadow-[0_0_12px_rgba(111,78,203,0.2)]`; shadow `shadow-card-sm`
- **Textarea**: auto-grows up to 6 lines, `resize-none`; `Enter` sends, `Shift+Enter` newline
- **Send button**: switches to Stop action during generation (lighter purple `#9B87F5`, white square icon); remains actionable to cancel; disabled only when input is empty or rate-limited
- **Tooltips**: `"Enter to send • Shift+Enter for newline"` on textarea and button

### FilterDropdown
- **File**: `src/components/ui/FilterDropdown.tsx`
- **Keyboard**: ArrowUp/Down, Enter, Escape; ARIA: `listbox`, `option`, `aria-selected`
- **Button**: `h-8 px-3 rounded-lg font-inter text-[12px] font-medium`
- **Active**: `bg-[#403D85] text-white border-[#403D85]`
- **Inactive**: `bg-white text-[#525252] border-[#E5E7EB] hover:border-[#D1D5DB]`
- **Dropdown**: `rounded-xl shadow-lg max-h-[280px] min-w-[200px]`; option hover `bg-[#FAFAFA]`, focused `bg-[#F3F4F6]`

### Pills (Category Filters)
- Base: `bg-[rgba(47,45,90,1)] text-white rounded-full px-4 py-2 font-poppins`
- Hover: darken ~10%, `shadow-sm`, scale 1.03
- Active: `scale-[0.98]`; Focus: focus-primary ring; Motion: `transition-all duration-200 ease-out`

### Buttons

There is **no shadcn `Button` component** in this repo. `components.json` is present and the shadcn theme CSS variables are in `src/index.css`, but only the Radix primitives were generated (`dialog`, `popover`, `select`, `hover-card`). Every button is hand-written Tailwind. Two conventions cover nearly every call site.

**Toolbar button** — search rows, card headers, `FilterDropdown`:

`h-8 3xl:h-10 4xl:h-11 px-3 3xl:px-4 rounded-lg 3xl:rounded-xl border font-inter text-xs 3xl:text-[13px] 4xl:text-sm font-medium transition-all`

| State | Classes |
|---|---|
| Inactive | `bg-surface-card text-text-secondary border-border-ui hover:border-text-muted hover:bg-surface-subtle` |
| Active (filter applied) | `bg-brand-900 text-white border-brand-900` |
| Destructive | `bg-surface-card text-semantic-error-text border-semantic-error-border hover:bg-semantic-error-bg` |
| Emphasis (banner CTA) | Inactive classes with `text-text-primary` |

**Form button** — settings, onboarding, primary submit. Shared helpers in `src/components/settings/settingsPrimitives.tsx`:

| Role | Classes |
|---|---|
| Primary | `px-5 py-2.5 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-card-md hover:bg-brand-hover` |
| Secondary | `px-5 py-2.5 rounded-lg border border-border-ui text-text-secondary font-poppins text-sm font-medium hover:bg-surface-subtle` |
| Compact | `px-4 py-2 rounded-lg border border-border-ui bg-surface-card text-text-primary font-poppins text-sm font-medium hover:bg-surface-subtle` |
| Large CTA (full-width submit, e.g. document upload) | `h-10 3xl:h-12 4xl:h-14 w-full rounded-lg 3xl:rounded-xl bg-brand-700 px-4 3xl:px-6 font-inter text-body-sm 3xl:text-[15px] 4xl:text-base font-semibold text-white hover:bg-brand-hover` |

All buttons: `focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed`.

### CategoryCard
- Base: white bg, `border border-[rgba(224,224,224,1)]`, `shadow-xs`, `rounded-2xl`
- Hover: `shadow-sm`, `-translate-y-0.5`, icon `group-hover:scale-110`
- Accessibility: `role="button"`, Enter/Space activation, focus-primary ring

---

### ProjectKPIs
- **File**: `src/components/projects/ProjectKPIs.tsx`
- **Layout**: `grid-cols-2 lg:grid-cols-4 gap-3`; cards `bg-white rounded-2xl border border-[#E5E5E5] p-4 min-h-[120px]`
- **Metrics**: Total projects, Credits issued (retirement progress bar), Registry donut, Status donut
- **Donut**: 64×64px, innerRadius 18, outerRadius 30; Registry colors `['#403D85','#2098D8','#418045','#D97706','#A13D15','#6F4ECB']`; Status colors `['#418045','#6F4ECB','#0A558C','#D97706','#9CA3AF','#A13D15']`
- **Typography**: label Inter 11px semibold `#6B7280` uppercase; value Poppins 28px semibold `#1F1F1F`

---

### Chat Interface Layout

All messages are plain text (no bubbles), centered in a **680px** max-width container.

- **User questions**: Inter Semibold 20px/30px, `#1a1a1a`
- **Bot responses**: Inter Regular 14px/1.6, `#1a1a1a`; lists `list-disc pl-6 space-y-1.5 mb-3`; paragraphs `mb-2 leading-[1.6]`
- **Auto-scroll**: new user questions scroll to "eye level" — `eyeLevelOffset = sectionRect.height * 0.15`

### ChatMessage
- **File**: `src/components/chat/ChatMessage.tsx`

| State | Styling |
|---|---|
| User | `font-inter font-semibold text-lg md:text-xl` |
| Bot pending | Animated dots, `#6B7280` |
| Bot error | `bg-red-50 border border-red-200 rounded-md`; retry `bg-red-600 hover:bg-red-700` |
| Bot cancelled | `bg-brand-50 border border-brand-200 text-brand-900 rounded-md` |
| Bot success | Markdown via ChatMarkdownContent |

**Retry button** (error/cancelled): Poppins font, `text-[11px] px-2.5 py-1 rounded`; disabled with spinner while retrying (`Loader2 animate-spin`)

**Copy button**: right-aligned below response (`mt-3 flex justify-end`); default gray Copy icon → copied green Check icon (~1.5s); `h-3 w-3` icon

**Markdown lists**: `ul.list-disc.pl-6.space-y-2`; `ol.list-decimal.pl-6.space-y-2`; `li.leading-[1.6]`

### SuggestedPrompts
- **File**: `src/components/chat/SuggestedPrompts.tsx`
- **Layout**: Separated from message body/citations by a fine divider (`border-t border-surface-subtle mt-6 pt-5`) to resolve section density. Prompts flow horizontally (`flex flex-wrap gap-2`).
- **Header**: Custom brand Chat icon (`chat.svg?react`) within a soft brand-colored background badge (`w-5 h-5 rounded-md bg-brand-500/[0.08] text-brand-700`) and standard Inter uppercase text "Follow-up questions" (`font-inter text-[11px] font-semibold text-brand-700 uppercase tracking-wider`).
- **Cards (Chips)**: Wrap chips with a solid white background and clear borders:
  - Default: `border-border-ui bg-white hover:bg-gray-50 hover:shadow-sm hover:border-gray-300`
  - Disabled / Typing: `border-border-ui bg-gray-50/50 cursor-not-allowed opacity-50`
- **Hover/Tap Microinteractions**:
  - Hover matches the app's neutral card pattern (`RecommendationCard`, `CategoryCard`): subtle background shift to `gray-50`, neutral `shadow-sm`, and border darkens slightly to `gray-300`.
  - Active press triggers a physical scaling-down (`scale: 0.98`) for tactile feedback.
  - Text and arrow remain their default muted colors on hover; no brand-purple tinting, keeping the interaction subtle and consistent with surrounding UI.

### Agent Reasoning Panel
- Position: below user question, before bot response (`mb-4`)
- Trigger: plain accordion — summary Inter 11px `#6B7280`, purple lightning icon; chevron rotates 180° on open
- Content cards: white bg, `border border-[#E5E7EB]`; `rounded-md border border-gray-200 bg-white p-2.5`
- Step icon bg: `bg-[#F3F0FF]`; icon color `#6F4ECB`; bullet `w-1 h-1 rounded-full bg-[#6F4ECB]`
- Typography: 10px semibold labels, 11px regular content
- Collapsed by default; expand animation in `src/components/chat/chat-interface.css` via `details[open] .reasoning-content`; respects `prefers-reduced-motion`

### TypingIndicator
3 dots: `w-2 h-2 bg-[#6F4ECB] rounded-full animate-bounce`; delays 0ms / 150ms / 300ms; spacing `mt-4 mb-4`

### RecommendationCard
- **File**: `src/components/chat/RecommendationCard.tsx`
- **Uses React Router `Link`** to preserve chat state on navigation
- Card: `#FCFCFC bg`, black 1px border, `rounded-[6px]`; title Inter 12px semibold `#1F1F1F` line-clamp-2; meta Inter 12px `#555555`
- Tag badges: 8.5px semibold, `rounded-[15px]`; Project `#C8E6A5`/`#496731`; Methodology `#B4DBFF`/`#0A558C`; Pricing `#FFD8B4`/`#93370D`

### QuizWidget
- **File**: `src/components/chat/QuizWidget.tsx` — interactive quiz rendered inside chat

---

### Pricing Components

Page shell: `src/pages/PricingPage.tsx` — hero + `PricingFactorTabs` + `PricingExplorer`. No `react-query` on this route; no chart library. Data lives in `src/data/pricingData.ts` (order, labels, `TYPE_COLORS`) and `src/data/pricingFactorContent.ts` (sourced figures, methodology statuses, SBTi timeline copy, source links).

#### PricingFactorTabs
- **File**: `src/components/pricing/PricingFactorTabs.tsx`
- Text tabs (`role="tablist"`) with a single ink-filled active state, roving `tabIndex` + arrow keys, and horizontal scrolling on mobile.

#### PricingExplorer
- **File**: `src/components/pricing/PricingExplorer.tsx`
- Single `tabpanel` that switches the active factor with a reduced-motion-aware `AnimatePresence` transition.

#### FactorComparison
- **File**: `src/components/pricing/FactorComparison.tsx`
- One white `DataCard` per force, using open layout gaps instead of repeated internal divider rules:
  - **Type** — linear animated bar comparison plus a dark neutral context panel.
  - **Integrity** — balanced landfill-gas metrics, co-benefit premium, and CCP methodology status list.
  - **Claims** — SBTi V2.0 milestone timeline + open demand lanes without flow chips.
  - **Compliance** — CORSIA timeline + open authorized and unauthorized buyer pools without large tinted cards.
  - **Vintage** — linear animated bar comparison plus a dark neutral context panel.
- Statuses render as semantic text labels rather than capsules. Large values use tabular numerals.
- Shared primitives: `BandLabel`, `DataCard`, `SplitBand`, `BarComparison`, `StatusPill`.

---

### Explore Projects

**Layout hierarchy**: KPI Bar → Search + Filters → Split View (list 35% left / detail 65% right)

#### ProjectFiltersV2
- **File**: `src/components/projects/ProjectFiltersV2.tsx`
- Primary filters (always visible): Registry, Status, Type, and Activity. Each is a `FilterDropdown`.
- "Filters" button opens secondary filters in a drawer. It shows an active badge count.
- Active filter button: `bg-brand-900 text-white border-brand-900`. Inactive: `bg-surface-card text-text-secondary border-border-ui`.
- Result count: `font-inter text-[11px] text-text-muted` right-aligned.

#### FilterPanel
- **File**: `src/components/projects/FilterPanel.tsx`
- Mobile-first filter drawer. It supports `mode="drawer"` and `mode="popover"`.
- Tabs: `activeTab` shows a list. `FilterPillList` shows active pills with a remove action.
- A single global `FilterSearchInput` filters options inside each tab.

#### FilterDrawer
- **File**: `src/components/projects/FilterDrawer.tsx`
- Desktop right-side drawer for secondary filters. `max-w-[400px]`.
- It wraps `FilterPanel` with a fixed `mode="drawer"`.

#### FilterPillList
- **File**: `src/components/projects/FilterPillList.tsx`
- Horizontal list of selected filter pills. Each pill has a close icon.

#### FilterSearchInput
- **File**: `src/components/projects/FilterSearchInput.tsx`
- Search input for filter option lists. Clear button shows when the value is not empty.

#### ProjectListItem
- **File**: `src/components/projects/ProjectListItem.tsx`
- Active: `bg-[#F5F0FF] border-l-2 border-l-[#6F4ECB]`; Inactive: `bg-white border-l-transparent hover:bg-[#FAFAFA]`
- Layout: 3 rows — ID/Registry, Name, Type+Country+Credits
- Compare checkbox: `opacity-0 group-hover:opacity-100`, always visible when selected
- Typography: ID Inter 10px medium `#6B7280`; Name Poppins 13px medium line-clamp-2; Meta Inter 11px; Credits Poppins 12px semibold

#### ProjectDetailPanel
- **File**: `src/components/projects/ProjectDetailPanel.tsx`
- Full-height flex column: sticky header + scrollable content.
- Sections: Credits, Overview, Location, Stakeholders, Methodology, Timeline, Regulatory, Links, Description, Notes.
- Certification badges and a Cohort & Track Record card show below the header.
- Credit cards: `bg-surface-base rounded-xl p-3.5`; section headings Inter 10px semibold `text-text-muted` uppercase tracking-0.6px.

#### Cohort & Track Record
- **File**: `src/components/projects/ProjectDetailPanel.tsx`
- Card: `bg-surface-base rounded-xl p-4`.
- Shows percentiles by type, country, and type + country.
- Shows the project developer's total projects, total credits, and average retirement rate.

#### Split View Layout
- Container: `flex border border-[#E5E7EB] rounded-2xl overflow-hidden bg-white`
- Height: `calc(100vh - 260px)` min 520px
- Left panel: `w-[380px] flex-shrink-0 border-r border-[#E5E7EB] overflow-y-auto`; infinite scroll; `divide-y divide-[#F3F4F6]`
- Right panel: `flex-1 min-w-0`; hidden below `lg`
- Mobile: `fixed inset-0 z-50 bg-black/40` overlay; panel `max-w-[440px]` from right; opens on explicit tap only

#### Skeleton Components
- `KPISkeleton`: 4-column grid matching KPI bar
- `SplitViewSkeleton`: 8 list skeletons + right panel skeleton
- `ListItemSkeleton`: matches compact list item layout

---

### Case Study Components

#### CaseStudyHeader
- Back button with `useNavigate`; quality badge `bg-[#C8E6A5] rounded-full`; org text underlined linking to external registry

#### CaseStudyStrengths
- Lucide checkmarks instead of bullets; SDG boxes 55×41px — SDG 8: `#A41C43`, SDG 13: `#418045`, SDG 14: `#00689D`
- Font: Inter 10.5px / 13px line-height; `whitespace-normal` to prevent cutoff

#### ProjectStatistics
- Semi-circle chart from asset image
- Stat pills: 58×22px, `px-[10px] py-[6px] rounded-[17px]` — green `#DFFDD6`, purple `#E9D5FF`, blue `#B4DBFF`
- Font: Inter 10px values / 7.7px labels

#### ProjectDetails
- Responsive: column mobile → row desktop; map image `rounded-[14px]`; section headings uppercase `#616161`

---

### Modals & Overlays

#### ScrollToTop
- Fixed `bottom-6 right-6`; white circle, `shadow-scroll-btn`; brand purple `#4A2AA3` arrow; appears after 300px scroll; `aria-label` for accessibility

---

### IconWrapper
- **File**: `src/components/icons/IconWrapper.tsx`
- **Icons**: `src/assets/icons/` — 22 stroke-based (outline) SVGs
- **Props**: `Icon` (required), `size` (default 24), `color`, `state ('default'|'active'|'selected')`, `title`, `aria-hidden`, `onClick`
- **State colors** (from `ICON_STATE`): default `#6B7280`, active/selected `#6F4ECB`
- **Accessibility**: use `title` for meaningful icons OR `aria-hidden={true}` for decorative — never both

**Available icons**: arrow-up, book, calender, chat, chevron-left, cora, explore, file, globe, info, lightbulb, location, map, plus-circle, pricing, sidebar-close, target, trash, tree, trending-down, users, x

```tsx
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChatIcon from '@/assets/icons/chat.svg?react';

<IconWrapper Icon={ChatIcon} size={24} title="Chat" />           // meaningful
<IconWrapper Icon={ChatIcon} size={24} aria-hidden={true} />    // decorative
<IconWrapper Icon={ChatIcon} size={24} state="active" aria-hidden={true} />
```

---

### ProjectListItem
- **File**: `src/components/projects/ProjectListItem.tsx`
- **Background states**:
  - Default: `bg-surface-card`
  - Hover: `hover:bg-surface-base`
  - Active/selected: `bg-surface-subtle`
  - Country-synchronized highlight: `bg-surface-base`
  - Long-press flash: `bg-surface-subtle`
- **Compare checkbox**: appears on `group-hover`; selected `border-text-primary bg-text-primary`; unselected `border-border-ui bg-surface-card`

### Country Filter Chip
- **Files**: `src/components/projects/InlineSplitView.tsx`, `src/components/projects/FullscreenOverlay.tsx`
- **Active**: `bg-surface-card border border-border-ui text-text-primary`
- **Dot**: `bg-text-muted`
- **Clear icon**: `TEXT.muted` (`#6B7280`)
- **Hover**: `hover:bg-surface-subtle`

### Certification Badges
- **File**: `src/components/projects/ProjectDetailPanel.tsx`
- **Base**: `inline-flex items-center px-2.5 py-1 rounded-md font-inter text-xs font-medium`
- **ICVCM**: `bg-text-primary text-white border border-text-primary`
- **CORSIA**: `bg-surface-subtle text-text-primary border border-border-ui`
- **CCB**: `bg-surface-subtle text-text-primary border border-border-ui`
- **Other**: `bg-surface-subtle text-text-secondary border border-border-ui`

### IssuanceSparkline
- **File**: `src/components/projects/IssuanceSparkline.tsx`
- **Multi-year**: 64px flex bar chart
- **Issuance bars**: `bg-semantic-success-icon`, hover `bg-semantic-success-button`
- **Gap/empty years**: `bg-border-ui/50`, hover `bg-border-ui`
- **Single-year fallback**: `bg-surface-subtle` metric badge with `bg-semantic-success-icon` dot
- **Empty/no data**: `null`

## Patterns

### Accessibility
- Minimum tap target: **44×44px** for all interactive controls (`min-w-[44px] min-h-[44px]`)
- Focus rings: standard purple ring on all focusable elements (see Focus Rings token)
- After retry: scroll updated message into view — `scrollIntoView({ behavior: 'smooth', block: 'center' })`; bubble accepts `tabIndex={-1}`
- Motion: all transitions respect `@media (prefers-reduced-motion: reduce)`

### Responsive Design
- Container centered with `2rem` padding; custom `2xl` breakpoint at `1400px`; ultra-wide `3xl` at `1920px`, `4xl` at `2400px` (`tailwind.config.ts` `screens`)
- Split view right panel hidden below `lg`; mobile gets sheet-style drawer
- Sidebar collapses to icon-only on mobile (hamburger toggle)

### Mobile — Sticky Composer & Safe Areas
- Chat composer fixed to bottom: `paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))'`
- Scroll area: `paddingBottom: 'calc(6rem + env(safe-area-inset-bottom, 0px))'`

### Content Rendering (Markdown)
- **Links**: sanitized URLs; external open with `target="_blank" rel="noopener noreferrer"`; style `text-brand-700 underline break-words inline-flex items-center gap-1` + lucide `ExternalLink` icon
- **Images**: `loading="lazy" decoding="async" max-w-full h-auto max-h-80 object-contain rounded-md border border-gray-100`

---

**Last Updated**: March 2026
